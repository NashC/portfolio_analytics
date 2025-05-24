import pytest
import pandas as pd
import numpy as np
from datetime import datetime
import logging
from unittest.mock import patch

from app.ingestion.normalization import (
    normalize_data,
    normalize_transaction_types,
    normalize_numeric_columns,
    validate_normalized_data,
    validate_canonical_types,
    get_institution_from_columns,
    TRANSACTION_TYPE_MAP,
    CANONICAL_TYPES
)


class TestTransactionTypeMapping:
    """Test the transaction type mapping functionality."""
    
    def test_canonical_types_validation(self):
        """Test that all mapped types are valid canonical types."""
        assert validate_canonical_types() == True
        
        # Test that all values in the mapping are in canonical types
        mapped_types = set(TRANSACTION_TYPE_MAP.values())
        assert mapped_types.issubset(CANONICAL_TYPES)
    
    def test_binance_us_transaction_types(self):
        """Test Binance US specific transaction type mappings."""
        binance_data = pd.DataFrame({
            'type': ['Staking Rewards', 'Crypto Deposit', 'Crypto Withdrawal', 'Buy', 'USD Deposit'],
            'Operation': ['Staking Rewards', 'Crypto Deposit', 'Crypto Withdrawal', 'Buy', 'USD Deposit'],
            'Primary Asset': ['SOL', 'SOL', 'SOL', 'BTC', 'USD'],
            'quantity': [10.0, 5.0, -3.0, 0.1, 1000.0],
            'price': [50.0, 50.0, 50.0, 45000.0, 1.0],
            'timestamp': ['2024-01-01', '2024-01-02', '2024-01-03', '2024-01-04', '2024-01-05']
        })
        
        result = normalize_transaction_types(binance_data)
        
        expected_types = ['staking_reward', 'transfer_in', 'transfer_out', 'buy', 'deposit']
        assert result['type'].tolist() == expected_types
    
    def test_coinbase_transaction_types(self):
        """Test Coinbase specific transaction type mappings."""
        coinbase_data = pd.DataFrame({
            'type': ['Staking Income', 'Buy', 'Inflation Reward', 'Receive', 'Send'],
            'Transaction Type': ['Staking Income', 'Buy', 'Inflation Reward', 'Receive', 'Send'],
            'Asset': ['ETH', 'BTC', 'ATOM', 'ETH', 'BTC'],
            'Quantity Transacted': [0.1, 0.05, 100.0, 0.2, 0.03],
            'quantity': [0.1, 0.05, 100.0, 0.2, 0.03],
            'price': [3000.0, 45000.0, 10.0, 3000.0, 45000.0],
            'timestamp': ['2024-01-01', '2024-01-02', '2024-01-03', '2024-01-04', '2024-01-05']
        })
        
        result = normalize_transaction_types(coinbase_data)
        
        expected_types = ['staking_reward', 'buy', 'staking_reward', 'transfer_in', 'transfer_out']
        assert result['type'].tolist() == expected_types
    
    def test_interactive_brokers_transaction_types(self):
        """Test Interactive Brokers specific transaction type mappings."""
        ib_data = pd.DataFrame({
            'type': ['Dividend', 'Buy', 'Credit Interest', 'Sell', 'Deposit'],
            'Symbol': ['AAPL', 'AAPL', 'USD', 'AAPL', 'USD'],
            'Gross Amount': [100.0, 5000.0, 10.0, 4800.0, 1000.0],
            'Net Amount': [100.0, 5000.0, 10.0, 4800.0, 1000.0],
            'quantity': [0.0, 10.0, 0.0, -10.0, 1000.0],
            'price': [0.0, 500.0, 0.0, 480.0, 1.0],
            'timestamp': ['2024-01-01', '2024-01-02', '2024-01-03', '2024-01-04', '2024-01-05']
        })
        
        result = normalize_transaction_types(ib_data)
        
        expected_types = ['dividend', 'buy', 'interest', 'sell', 'deposit']
        assert result['type'].tolist() == expected_types
    
    def test_gemini_transaction_types(self):
        """Test Gemini specific transaction type mappings."""
        gemini_data = pd.DataFrame({
            'type': ['Buy', 'Sell', 'Credit', 'Debit', 'Interest Credit'],
            'Type': ['Buy', 'Sell', 'Credit', 'Debit', 'Interest Credit'],
            'Time (UTC)': ['12:00:00', '13:00:00', '14:00:00', '15:00:00', '16:00:00'],
            'quantity': [0.1, -0.05, 0.2, -0.1, 0.001],
            'price': [45000.0, 45000.0, 0.0, 0.0, 0.0],
            'timestamp': ['2024-01-01', '2024-01-02', '2024-01-03', '2024-01-04', '2024-01-05']
        })
        
        result = normalize_transaction_types(gemini_data)
        
        expected_types = ['buy', 'sell', 'transfer_in', 'transfer_out', 'staking_reward']
        assert result['type'].tolist() == expected_types


class TestInstitutionDetection:
    """Test institution detection from column patterns."""
    
    def test_detect_binance_us(self):
        """Test detection of Binance US data."""
        df = pd.DataFrame({
            'Operation': ['Buy'],
            'Primary Asset': ['BTC'],
            'Time': ['2024-01-01']
        })
        assert get_institution_from_columns(df) == 'binance_us'
    
    def test_detect_coinbase(self):
        """Test detection of Coinbase data."""
        df = pd.DataFrame({
            'Transaction Type': ['Buy'],
            'Asset': ['BTC'],
            'Quantity Transacted': [0.1]
        })
        assert get_institution_from_columns(df) == 'coinbase'
    
    def test_detect_interactive_brokers(self):
        """Test detection of Interactive Brokers data."""
        df = pd.DataFrame({
            'Symbol': ['AAPL'],
            'Gross Amount': [1000.0],
            'Net Amount': [995.0]
        })
        assert get_institution_from_columns(df) == 'interactive_brokers'
    
    def test_detect_gemini(self):
        """Test detection of Gemini data."""
        df = pd.DataFrame({
            'Type': ['Buy'],
            'Time (UTC)': ['12:00:00']
        })
        assert get_institution_from_columns(df) == 'gemini'
    
    def test_detect_unknown(self):
        """Test detection of unknown institution."""
        df = pd.DataFrame({
            'random_column': ['value'],
            'another_column': ['value2']
        })
        assert get_institution_from_columns(df) == 'unknown'


class TestNumericNormalization:
    """Test numeric column normalization."""
    
    def test_basic_numeric_cleaning(self):
        """Test basic numeric column cleaning."""
        data = pd.DataFrame({
            'type': ['buy', 'sell', 'deposit'],
            'quantity': ['$1,000.50', '-500.25', '2,000'],
            'price': ['$45,000.00', '$46,000', '1.0'],
            'fees': ['$10.50', '$5.00', '0'],
            'timestamp': ['2024-01-01', '2024-01-02', '2024-01-03']
        })
        
        result = normalize_numeric_columns(data)
        
        # Sell quantities should be negative after normalization
        assert result['quantity'].tolist() == [1000.50, -500.25, 2000.0]  # Sell is already negative, made more negative
        assert result['price'].tolist() == [45000.0, 46000.0, 1.0]
        assert result['fees'].tolist() == [10.50, 5.0, 0.0]
    
    def test_sell_quantity_negation(self):
        """Test that sell quantities are made negative."""
        data = pd.DataFrame({
            'type': ['buy', 'sell', 'sell'],
            'quantity': [100.0, 50.0, -25.0],  # Mix of positive and negative
            'price': [100.0, 100.0, 100.0],
            'timestamp': ['2024-01-01', '2024-01-02', '2024-01-03']
        })
        
        result = normalize_numeric_columns(data)
        
        assert result['quantity'].tolist() == [100.0, -50.0, -25.0]
    
    def test_fees_normalization(self):
        """Test that fees are always positive and NaN values are filled."""
        data = pd.DataFrame({
            'type': ['buy', 'sell', 'deposit'],
            'quantity': [100.0, -50.0, 1000.0],
            'fees': [-10.0, 5.0, np.nan],
            'timestamp': ['2024-01-01', '2024-01-02', '2024-01-03']
        })
        
        result = normalize_numeric_columns(data)
        
        assert result['fees'].tolist() == [10.0, 5.0, 0.0]
    
    def test_invalid_numeric_values(self):
        """Test handling of invalid numeric values."""
        data = pd.DataFrame({
            'type': ['buy', 'sell'],
            'quantity': ['invalid', '100.0'],
            'price': ['50.0', 'also_invalid'],
            'timestamp': ['2024-01-01', '2024-01-02']
        })
        
        result = normalize_numeric_columns(data)
        
        assert pd.isna(result['quantity'].iloc[0])
        assert result['quantity'].iloc[1] == -100.0  # Sell made negative
        assert result['price'].iloc[0] == 50.0
        assert pd.isna(result['price'].iloc[1])


class TestTypeInference:
    """Test transaction type inference from data patterns."""
    
    def test_buy_sell_inference(self):
        """Test inference of buy/sell from quantity and price patterns."""
        data = pd.DataFrame({
            'type': ['unknown', 'unknown', 'unknown', 'unknown'],
            'quantity': [100.0, -50.0, 1000.0, -500.0],
            'price': [50.0, 50.0, 1.0, 1.0],
            'asset': ['BTC', 'BTC', 'USD', 'USD'],
            'timestamp': ['2024-01-01', '2024-01-02', '2024-01-03', '2024-01-04']
        })
        
        result = normalize_transaction_types(data)
        
        expected_types = ['buy', 'sell', 'deposit', 'withdrawal']
        assert result['type'].tolist() == expected_types
    
    def test_stablecoin_handling(self):
        """Test that stablecoins are treated as cash equivalents."""
        data = pd.DataFrame({
            'type': ['unknown', 'unknown', 'unknown'],
            'quantity': [1000.0, -500.0, 100.0],
            'price': [1.0, 1.0, 1.0],
            'asset': ['USDC', 'USDT', 'DAI'],
            'timestamp': ['2024-01-01', '2024-01-02', '2024-01-03']
        })
        
        result = normalize_transaction_types(data)
        
        expected_types = ['deposit', 'withdrawal', 'deposit']
        assert result['type'].tolist() == expected_types


class TestDataValidation:
    """Test data validation functionality."""
    
    def test_valid_data_passes(self):
        """Test that valid data passes validation."""
        data = pd.DataFrame({
            'timestamp': pd.to_datetime(['2024-01-01', '2024-01-02']),
            'type': ['buy', 'sell'],
            'asset': ['BTC', 'BTC'],
            'quantity': [1.0, -0.5],
            'price': [45000.0, 46000.0]
        })
        
        assert validate_normalized_data(data) == True
    
    def test_missing_required_columns(self):
        """Test validation fails with missing required columns."""
        data = pd.DataFrame({
            'timestamp': pd.to_datetime(['2024-01-01']),
            'type': ['buy'],
            # Missing 'asset' and 'quantity'
        })
        
        assert validate_normalized_data(data) == False
    
    def test_invalid_transaction_types(self):
        """Test validation fails with invalid transaction types."""
        data = pd.DataFrame({
            'timestamp': pd.to_datetime(['2024-01-01']),
            'type': ['invalid_type'],
            'asset': ['BTC'],
            'quantity': [1.0]
        })
        
        assert validate_normalized_data(data) == False
    
    def test_null_timestamps(self):
        """Test validation detects null timestamps."""
        data = pd.DataFrame({
            'timestamp': [pd.NaT, pd.to_datetime('2024-01-01')],
            'type': ['buy', 'sell'],
            'asset': ['BTC', 'BTC'],
            'quantity': [1.0, -0.5]
        })
        
        assert validate_normalized_data(data) == False
    
    def test_zero_quantities_in_trades(self):
        """Test validation detects zero quantities in non-fee transactions."""
        data = pd.DataFrame({
            'timestamp': pd.to_datetime(['2024-01-01', '2024-01-02']),
            'type': ['buy', 'fee'],
            'asset': ['BTC', 'USD'],
            'quantity': [0.0, 0.0]  # Zero quantity buy should fail, zero quantity fee should pass
        })
        
        assert validate_normalized_data(data) == False


class TestCompleteNormalization:
    """Test the complete normalization pipeline."""
    
    def test_complete_pipeline_interactive_brokers(self):
        """Test complete normalization pipeline with Interactive Brokers data."""
        data = pd.DataFrame({
            'type': ['Dividend', 'Buy', 'Sell'],
            'Symbol': ['AAPL', 'AAPL', 'AAPL'],
            'Gross Amount': [100.0, 5000.0, 4800.0],
            'quantity': ['0', '10.0', '-10'],
            'price': ['0', '$500.00', '$480'],
            'fees': ['0', '$1.00', '$1.00'],
            'timestamp': ['2024-01-01 10:00:00', '2024-01-02 11:00:00', '2024-01-03 12:00:00']
        })
        
        result = normalize_data(data)
        
        # Check transaction types
        assert result['type'].tolist() == ['dividend', 'buy', 'sell']
        
        # Check numeric normalization
        assert result['quantity'].tolist() == [0.0, 10.0, -10.0]
        assert result['price'].tolist() == [0.0, 500.0, 480.0]
        assert result['fees'].tolist() == [0.0, 1.0, 1.0]
        
        # Check timestamps
        assert all(pd.notna(result['timestamp']))
        assert isinstance(result['timestamp'].iloc[0], pd.Timestamp)
    
    def test_complete_pipeline_coinbase(self):
        """Test complete normalization pipeline with Coinbase data."""
        data = pd.DataFrame({
            'type': ['Staking Income', 'Buy', 'Send'],
            'Transaction Type': ['Staking Income', 'Buy', 'Send'],
            'Asset': ['ETH', 'BTC', 'ETH'],
            'Quantity Transacted': [0.1, 0.05, 0.2],
            'quantity': ['0.1', '0.05', '0.2'],
            'price': ['$3,000.00', '$45,000', '$3,100'],
            'timestamp': ['2024-01-01T10:00:00Z', '2024-01-02T11:00:00Z', '2024-01-03T12:00:00Z']
        })
        
        result = normalize_data(data)
        
        # Check transaction types
        assert result['type'].tolist() == ['staking_reward', 'buy', 'transfer_out']
        
        # Check numeric normalization
        assert result['quantity'].tolist() == [0.1, 0.05, 0.2]
        assert result['price'].tolist() == [3000.0, 45000.0, 3100.0]
    
    def test_non_transactional_filtering(self):
        """Test that non-transactional rows are filtered out."""
        data = pd.DataFrame({
            'type': ['Buy', 'Monthly Interest Summary', 'Sell'],
            'quantity': [1.0, 0.0, -0.5],
            'price': [100.0, 0.0, 105.0],
            'timestamp': ['2024-01-01', '2024-01-02', '2024-01-03']
        })
        
        result = normalize_data(data)
        
        # Should filter out the summary row
        assert len(result) == 2
        assert result['type'].tolist() == ['buy', 'sell']


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_empty_dataframe(self):
        """Test normalization with empty DataFrame."""
        data = pd.DataFrame()
        result = normalize_data(data)
        assert len(result) == 0
        assert result.empty
    
    def test_missing_type_column(self):
        """Test handling of missing type column."""
        data = pd.DataFrame({
            'quantity': [1.0],
            'price': [100.0],
            'timestamp': ['2024-01-01']
        })
        
        # Should handle gracefully without crashing
        with pytest.raises(KeyError):
            normalize_transaction_types(data)
    
    def test_all_unknown_types(self):
        """Test handling when all transaction types are unknown."""
        data = pd.DataFrame({
            'type': ['completely_unknown', 'also_unknown'],
            'quantity': [1.0, -0.5],
            'price': [100.0, 105.0],
            'asset': ['UNKNOWN', 'UNKNOWN'],
            'timestamp': ['2024-01-01', '2024-01-02']
        })
        
        result = normalize_transaction_types(data)
        
        # With inference logic, these should be mapped to buy/sell based on quantity/price patterns
        expected_types = ['buy', 'sell']  # Positive quantity + price = buy, negative quantity + price = sell
        assert result['type'].tolist() == expected_types
    
    def test_mixed_case_transaction_types(self):
        """Test handling of mixed case transaction types."""
        data = pd.DataFrame({
            'type': ['BUY', 'sell', 'DEPOSIT', 'Withdrawal'],
            'quantity': [1.0, -0.5, 1000.0, -500.0],
            'timestamp': ['2024-01-01', '2024-01-02', '2024-01-03', '2024-01-04']
        })
        
        result = normalize_transaction_types(data)
        
        expected_types = ['buy', 'sell', 'deposit', 'withdrawal']
        assert result['type'].tolist() == expected_types


class TestLogging:
    """Test logging functionality."""
    
    def test_logging_output(self, caplog):
        """Test that appropriate log messages are generated."""
        with caplog.at_level(logging.INFO):
            data = pd.DataFrame({
                'type': ['Buy', 'Unknown_Type'],
                'quantity': [1.0, -0.5],
                'timestamp': ['2024-01-01', '2024-01-02']
            })
            
            normalize_transaction_types(data)
            
            # Check that logging messages are present
            assert "Starting Transaction Type Normalization" in caplog.text
            assert "Transaction Type Normalization Complete" in caplog.text
    
    def test_warning_for_unknown_types(self, caplog):
        """Test that warnings are logged for unknown transaction types."""
        with caplog.at_level(logging.WARNING):
            data = pd.DataFrame({
                'type': ['completely_unknown_type'],
                'quantity': [1.0],
                'timestamp': ['2024-01-01']
            })
            
            normalize_transaction_types(data)
            
            assert "Found 1 unknown transaction types" in caplog.text
            assert "completely_unknown_type" in caplog.text


# Integration test with real-world-like data
class TestRealWorldScenarios:
    """Test with realistic data scenarios."""
    
    def test_mixed_institution_data(self):
        """Test normalization with mixed data from different institutions."""
        # Simulate data that might come from multiple sources
        mixed_data = pd.DataFrame({
            'type': [
                'Staking Income',  # Coinbase
                'Dividend',        # Interactive Brokers
                'Crypto Deposit',  # Binance US
                'Buy',            # Generic
                'Credit Interest' # Interactive Brokers
            ],
            'quantity': [0.1, 0.0, 5.0, 1.0, 0.0],
            'price': [3000.0, 0.0, 50.0, 45000.0, 0.0],
            'asset': ['ETH', 'AAPL', 'SOL', 'BTC', 'USD'],
            'timestamp': [
                '2024-01-01T10:00:00Z',
                '2024-01-02 10:00:00',
                '2024-01-03 10:00:00',
                '2024-01-04T10:00:00Z',
                '2024-01-05 10:00:00'
            ]
        })
        
        result = normalize_data(mixed_data)
        
        expected_types = ['staking_reward', 'dividend', 'transfer_in', 'buy', 'interest']
        assert result['type'].tolist() == expected_types
        
        # Check that at least some timestamps were parsed successfully
        parsed_timestamps = result['timestamp'].notna().sum()
        assert parsed_timestamps >= 2  # At least the ISO format timestamps should parse
        
        # Check that all parsed timestamps are proper Timestamp objects
        for ts in result['timestamp'].dropna():
            assert isinstance(ts, pd.Timestamp)
    
    def test_large_dataset_performance(self):
        """Test normalization performance with larger dataset."""
        # Create a larger dataset to test performance
        n_rows = 10000
        data = pd.DataFrame({
            'type': np.random.choice(['Buy', 'Sell', 'Staking Income', 'Dividend'], n_rows),
            'quantity': np.random.uniform(-1000, 1000, n_rows),
            'price': np.random.uniform(1, 50000, n_rows),
            'asset': np.random.choice(['BTC', 'ETH', 'AAPL', 'USD'], n_rows),
            'timestamp': pd.date_range('2024-01-01', periods=n_rows, freq='1h')  # Use lowercase 'h'
        })
        
        # Should complete without errors
        result = normalize_data(data)
        
        assert len(result) == n_rows
        assert all(result['type'].isin(CANONICAL_TYPES))


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"]) 