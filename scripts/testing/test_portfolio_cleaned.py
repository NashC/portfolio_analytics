#!/usr/bin/env python3

import pandas as pd
from app.analytics.portfolio import compute_portfolio_time_series_with_external_prices

def test_portfolio_with_cleaned_data():
    """Test portfolio calculation with cleaned normalized data."""
    
    print("=== TESTING PORTFOLIO CALCULATION WITH CLEANED DATA ===")
    
    # Load cleaned normalized data
    df = pd.read_csv('output/transactions_normalized.csv', parse_dates=['timestamp'])
    print(f"Input: {len(df)} transactions")
    print(f"Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    print(f"Institutions: {df['institution'].value_counts().to_dict()}")
    
    # Calculate portfolio value
    print("\nCalculating portfolio value...")
    portfolio_ts = compute_portfolio_time_series_with_external_prices(df)
    
    if not portfolio_ts.empty:
        latest_value = portfolio_ts['total'].iloc[-1]
        print(f"\n✅ Latest portfolio value: ${latest_value:,.2f}")
        print(f"Portfolio calculation shape: {portfolio_ts.shape}")
        
        print("\nTop 5 asset values:")
        asset_values = portfolio_ts.iloc[-1].drop('total').sort_values(ascending=False).head(5)
        for asset, value in asset_values.items():
            if value > 0:
                print(f"  {asset}: ${value:,.2f}")
        
        # Check for any extremely large values
        max_asset_value = asset_values.max()
        if max_asset_value > 10000000:  # $10M
            print(f"\n⚠️  WARNING: Large asset value detected: ${max_asset_value:,.2f}")
        
        # Show portfolio value over time (last 10 days)
        print("\nRecent portfolio values:")
        recent_values = portfolio_ts['total'].tail(10)
        for date, value in recent_values.items():
            print(f"  {date.strftime('%Y-%m-%d')}: ${value:,.2f}")
            
    else:
        print("❌ Portfolio calculation returned empty result")

if __name__ == "__main__":
    test_portfolio_with_cleaned_data() 