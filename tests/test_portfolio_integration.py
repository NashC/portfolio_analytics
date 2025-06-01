#!/usr/bin/env python3

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import tempfile
import os

from app.ingestion.loader import process_transactions
from app.ingestion.normalization import normalize_data
from app.analytics.portfolio import compute_portfolio_time_series_with_external_prices


class TestPortfolioIntegration:
    """Integration tests for the complete portfolio analytics pipeline."""
    
    def test_complete_pipeline_realistic_scenario(self):
        """Test the complete pipeline with a realistic trading scenario."""
        
        # Create simpler test data with clear date separation
        normalized_data = pd.DataFrame({
            'timestamp': pd.to_datetime([
                '2024-01-01',  # Day 1: Buy BTC
                '2024-01-02',  # Day 2: Staking reward ETH
                '2024-01-03',  # Day 3: Sell some BTC
                '2024-01-04'   # Day 4: Buy more ETH
            ]),
            'type': ['buy', 'staking_reward', 'sell', 'buy'],
            'asset': ['BTC', 'ETH', 'BTC', 'ETH'],
            'quantity': [1.0, 2.0, -0.5, 1.0],  # Simple quantities
            'price': [50000, 3000, 52000, 3100],
            'fees': [10, 0, 10, 5],
            'institution': ['coinbase', 'coinbase', 'coinbase', 'coinbase']
        })
        
        # Validate normalized data structure
        assert len(normalized_data) == 4
        assert 'timestamp' in normalized_data.columns
        assert 'type' in normalized_data.columns
        assert 'asset' in normalized_data.columns
        assert 'quantity' in normalized_data.columns
        
        # Test portfolio calculation with mocked prices
        with patch('app.analytics.portfolio.fetch_historical_prices') as mock_fetch:
            mock_prices = pd.DataFrame({
                'BTC': [50000, 51000, 52000, 53000],
                'ETH': [3000, 3050, 3100, 3150]
            }, index=pd.date_range('2024-01-01', periods=4, freq='D'))
            mock_fetch.return_value = mock_prices
            
            portfolio_ts = compute_portfolio_time_series_with_external_prices(normalized_data)
            
            if not portfolio_ts.empty:
                # Final holdings should be: BTC: 0.5 (1.0 - 0.5), ETH: 3.0 (2.0 + 1.0)
                final_btc_holdings = portfolio_ts['BTC'].iloc[-1] / 53000
                final_eth_holdings = portfolio_ts['ETH'].iloc[-1] / 3150
                
                assert abs(final_btc_holdings - 0.5) < 0.01
                assert abs(final_eth_holdings - 3.0) < 0.01
                
                # Portfolio value should be reasonable
                final_value = portfolio_ts['total'].iloc[-1]
                expected_value = (0.5 * 53000) + (3.0 * 3150)  # 26,500 + 9,450 = 35,950
                assert abs(final_value - expected_value) < 1000
    
    def test_transfer_inflation_prevention(self):
        """Test that the pipeline prevents portfolio inflation from internal transfers."""
        
        # Create data with large internal transfers that should NOT affect portfolio value
        test_data = pd.DataFrame({
            'timestamp': [
                datetime(2024, 1, 1),
                datetime(2024, 1, 2),  # Large transfer in
                datetime(2024, 1, 3),  # Large transfer out
                datetime(2024, 1, 4)
            ],
            'type': ['buy', 'transfer_in', 'transfer_out', 'sell'],
            'asset': ['ETH', 'ETH', 'ETH', 'ETH'],
            'quantity': [10.0, 100.0, 50.0, -5.0],  # FIXED: Sell should be negative
            'price': [3000, 3100, 3200, 3300],
            'fees': [10, 0, 0, 15],
            'institution': ['coinbase', 'coinbase', 'coinbase', 'coinbase']
        })
        
        with patch('app.analytics.portfolio.fetch_historical_prices') as mock_fetch:
            mock_prices = pd.DataFrame({
                'ETH': [3000, 3100, 3200, 3300]
            }, index=pd.date_range('2024-01-01', periods=4, freq='D'))
            mock_fetch.return_value = mock_prices
            
            portfolio_ts = compute_portfolio_time_series_with_external_prices(test_data)
            
            if not portfolio_ts.empty:
                # Should only account for buy/sell, not transfers
                final_eth_holdings = portfolio_ts['ETH'].iloc[-1] / 3300
                assert abs(final_eth_holdings - 5.0) < 0.01  # 10 bought - 5 sold = 5 ETH
                
                # Portfolio should NOT be inflated by the 100 ETH transfer_in
                final_value = portfolio_ts['total'].iloc[-1]
                assert final_value < 20000  # Should be ~16,500 (5 ETH * 3300), not 330,000+
    
    def test_duplicate_removal_integration(self):
        """Test that duplicates are properly removed in the complete pipeline."""
        
        # Create data with exact duplicates
        test_data = pd.DataFrame({
            'timestamp': [
                datetime(2024, 1, 1),
                datetime(2024, 1, 1),  # Exact duplicate
                datetime(2024, 1, 2),
                datetime(2024, 1, 2)   # Another exact duplicate
            ],
            'type': ['buy', 'buy', 'sell', 'sell'],
            'asset': ['BTC', 'BTC', 'BTC', 'BTC'],
            'quantity': [1.0, 1.0, 0.5, 0.5],
            'price': [50000, 50000, 52000, 52000],
            'fees': [10, 10, 15, 15],
            'institution': ['coinbase', 'coinbase', 'coinbase', 'coinbase']
        })
        
        # Normalize data (should remove duplicates)
        normalized_data = normalize_data(test_data)
        
        # Should have 2 transactions (duplicates removed)
        assert len(normalized_data) == 2
        
        with patch('app.analytics.portfolio.fetch_historical_prices') as mock_fetch:
            mock_prices = pd.DataFrame({
                'BTC': [50000, 52000]
            }, index=pd.date_range('2024-01-01', periods=2, freq='D'))
            mock_fetch.return_value = mock_prices
            
            portfolio_ts = compute_portfolio_time_series_with_external_prices(normalized_data)
            
            if not portfolio_ts.empty:
                # Should have 0.5 BTC (1.0 - 0.5), not 1.0 BTC from duplicates
                final_btc_holdings = portfolio_ts['BTC'].iloc[-1] / 52000
                assert abs(final_btc_holdings - 0.5) < 0.01
    
    def test_large_transaction_validation(self):
        """Test that extremely large transactions are handled appropriately."""
        
        # Create data with suspiciously large transactions
        test_data = pd.DataFrame({
            'timestamp': [
                datetime(2024, 1, 1),
                datetime(2024, 1, 2),
                datetime(2024, 1, 3)
            ],
            'type': ['deposit', 'buy', 'withdrawal'],
            'asset': ['USD', 'BTC', 'USD'],
            'quantity': [1000000, 1.0, -500000],  # FIXED: Withdrawal should be negative
            'price': [1.0, 50000, 1.0],
            'fees': [0, 25, 0],
            'institution': ['coinbase', 'coinbase', 'coinbase']
        })
        
        # Normalize data (large transactions should be flagged but not removed)
        normalized_data = normalize_data(test_data)
        
        # All transactions should still be present
        assert len(normalized_data) == 3
        
        with patch('app.analytics.portfolio.fetch_historical_prices') as mock_fetch:
            mock_prices = pd.DataFrame({
                'USD': [1.0, 1.0, 1.0],
                'BTC': [50000, 50000, 50000]
            }, index=pd.date_range('2024-01-01', periods=3, freq='D'))
            mock_fetch.return_value = mock_prices
            
            portfolio_ts = compute_portfolio_time_series_with_external_prices(normalized_data)
            
            if not portfolio_ts.empty:
                # Should have reasonable values
                final_value = portfolio_ts['total'].iloc[-1]
                
                # Net USD: 1M - 500K = 500K, plus 1 BTC = 50K = 550K total
                expected_value = 500000 + 50000
                assert abs(final_value - expected_value) < 10000
    
    def test_mixed_institution_data(self):
        """Test processing data from multiple institutions."""
        
        # Simulate data from different institutions with different formats
        binance_data = pd.DataFrame({
            'timestamp': [datetime(2024, 1, 1), datetime(2024, 1, 2)],
            'type': ['Buy', 'Staking Rewards'],
            'asset': ['BTC', 'BTC'],
            'quantity': [0.5, 0.001],
            'price': [50000, 0],  # Staking rewards have no price
            'fees': [25, 0],
            'institution': ['binanceus', 'binanceus']
        })
        
        coinbase_data = pd.DataFrame({
            'timestamp': [datetime(2024, 1, 3), datetime(2024, 1, 4)],
            'type': ['Advanced Trade Sell', 'Staking Income'],
            'asset': ['BTC', 'ETH'],
            'quantity': [0.2, 1.0],
            'price': [52000, 0],  # Staking income has no price
            'fees': [20, 0],
            'institution': ['coinbase', 'coinbase']
        })
        
        # Combine data
        combined_data = pd.concat([binance_data, coinbase_data], ignore_index=True)
        
        # Normalize
        normalized_data = normalize_data(combined_data)
        
        # Should have all 4 transactions
        assert len(normalized_data) == 4
        
        # Should have both institutions
        assert 'binanceus' in normalized_data['institution'].values
        assert 'coinbase' in normalized_data['institution'].values
        
        # Transaction types should be normalized
        assert 'buy' in normalized_data['type'].values
        assert 'sell' in normalized_data['type'].values
        assert 'staking_reward' in normalized_data['type'].values
    
    def test_portfolio_value_bounds_checking(self):
        """Test that portfolio values stay within reasonable bounds."""
        
        # Create realistic trading data
        test_data = pd.DataFrame({
            'timestamp': [
                datetime(2024, 1, 1),
                datetime(2024, 1, 15),
                datetime(2024, 2, 1),
                datetime(2024, 2, 15)
            ],
            'type': ['buy', 'buy', 'sell', 'staking_reward'],
            'asset': ['ETH', 'BTC', 'ETH', 'ETH'],
            'quantity': [10.0, 0.5, -3.0, 0.1],  # FIXED: Sell should be negative
            'price': [3000, 50000, 3500, 0],
            'fees': [15, 25, 12, 0],
            'institution': ['coinbase', 'coinbase', 'coinbase', 'coinbase']
        })
        
        with patch('app.analytics.portfolio.fetch_historical_prices') as mock_fetch:
            mock_prices = pd.DataFrame({
                'ETH': [3000, 3200, 3500, 3600],
                'BTC': [50000, 52000, 55000, 56000]
            }, index=pd.date_range('2024-01-01', periods=4, freq='2W'))
            mock_fetch.return_value = mock_prices
            
            portfolio_ts = compute_portfolio_time_series_with_external_prices(test_data)
            
            if not portfolio_ts.empty:
                final_value = portfolio_ts['total'].iloc[-1]
                
                # Final holdings: ETH: 7.1 (10 - 3 + 0.1), BTC: 0.5
                # Expected value: (7.1 * 3600) + (0.5 * 56000) = 25,560 + 28,000 = 53,560
                expected_value = (7.1 * 3600) + (0.5 * 56000)
                
                # Value should be within reasonable bounds
                assert 50000 < final_value < 60000
                assert abs(final_value - expected_value) < 5000
                
                # Should NOT be inflated to millions
                assert final_value < 1000000
    
    def test_cumulative_holdings_accuracy(self):
        """Test that cumulative holdings are calculated accurately over time."""
        
        test_data = pd.DataFrame({
            'timestamp': [
                datetime(2024, 1, 1),   # Day 1: Buy 1 BTC
                datetime(2024, 1, 5),   # Day 5: Buy 2 more BTC (total: 3)
                datetime(2024, 1, 10),  # Day 10: Sell 1 BTC (total: 2)
                datetime(2024, 1, 15)   # Day 15: Staking reward 0.1 BTC (total: 2.1)
            ],
            'type': ['buy', 'buy', 'sell', 'staking_reward'],
            'asset': ['BTC', 'BTC', 'BTC', 'BTC'],
            'quantity': [1.0, 2.0, -1.0, 0.1],  # FIXED: Sell should be negative
            'price': [50000, 51000, 52000, 0],
            'fees': [25, 50, 25, 0],
            'institution': ['coinbase', 'coinbase', 'coinbase', 'coinbase']
        })
        
        with patch('app.analytics.portfolio.fetch_historical_prices') as mock_fetch:
            # Create price data for the full date range
            date_range = pd.date_range('2024-01-01', '2024-01-15', freq='D')
            mock_prices = pd.DataFrame({
                'BTC': [50000 + i*100 for i in range(len(date_range))]
            }, index=date_range)
            mock_fetch.return_value = mock_prices
            
            portfolio_ts = compute_portfolio_time_series_with_external_prices(test_data)
            
            if not portfolio_ts.empty:
                # Check holdings at specific dates
                # Day 1: 1 BTC
                day1_holdings = portfolio_ts['BTC'].iloc[0] / mock_prices['BTC'].iloc[0]
                assert abs(day1_holdings - 1.0) < 0.01
                
                # Day 5: 3 BTC
                day5_holdings = portfolio_ts['BTC'].iloc[4] / mock_prices['BTC'].iloc[4]
                assert abs(day5_holdings - 3.0) < 0.01
                
                # Day 10: 2 BTC
                day10_holdings = portfolio_ts['BTC'].iloc[9] / mock_prices['BTC'].iloc[9]
                assert abs(day10_holdings - 2.0) < 0.01
                
                # Day 15: 2.1 BTC
                day15_holdings = portfolio_ts['BTC'].iloc[-1] / mock_prices['BTC'].iloc[-1]
                assert abs(day15_holdings - 2.1) < 0.01
    
    def test_data_quality_regression(self):
        """Regression test to ensure data quality issues don't reoccur."""
        
        # Create data that previously caused issues
        problematic_data = pd.DataFrame({
            'timestamp': [
                datetime(2024, 1, 1),
                datetime(2024, 1, 1),  # Duplicate
                datetime(2024, 1, 2),
                datetime.now() + timedelta(days=500),  # Future date
                datetime(2024, 1, 3)
            ],
            'type': ['buy', 'buy', 'transfer_in', 'buy', 'unknown_type'],
            'asset': ['ETH', 'ETH', 'ETH', 'ETH', None],
            'quantity': [26.14, 26.14, 75.66, 1.0, 0.0],  # Large transfer that caused inflation
            'price': [3500, 3500, 3500, 3500, 0],
            'fees': [10, 10, 0, 10, 0],
            'institution': ['coinbase', 'coinbase', 'coinbase', 'coinbase', 'coinbase'],
            'extra_column': ['a', 'b', 'c', 'd', 'e']
        })
        
        # Normalize data
        normalized_data = normalize_data(problematic_data)
        
        # Validate fixes
        assert len(normalized_data) < len(problematic_data)  # Some rows should be removed
        assert not normalized_data.duplicated().any()  # No duplicates
        assert normalized_data['asset'].notna().all()  # No null assets
        assert 'extra_column' not in normalized_data.columns  # Extra columns removed
        
        # Test portfolio calculation
        with patch('app.analytics.portfolio.fetch_historical_prices') as mock_fetch:
            mock_prices = pd.DataFrame({
                'ETH': [3500, 3600, 3700]
            }, index=pd.date_range('2024-01-01', periods=3, freq='D'))
            mock_fetch.return_value = mock_prices
            
            portfolio_ts = compute_portfolio_time_series_with_external_prices(normalized_data)
            
            if not portfolio_ts.empty:
                final_value = portfolio_ts['total'].iloc[-1]
                
                # Should NOT be inflated to $100M+ like before
                assert final_value < 1000000  # Less than $1M
                
                # Should be reasonable based on actual buy transactions
                # (excluding the large transfer_in that was causing inflation)
                assert final_value > 50000  # More than $50K (reasonable for ETH holdings)


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 