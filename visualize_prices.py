import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import os
from datetime import datetime

def connect_to_db():
    """Connect to the database"""
    db_path = os.path.abspath("data/historical_price_data/prices.db")
    return sqlite3.connect(db_path)

def get_price_data():
    """Fetch price data from the database"""
    conn = connect_to_db()
    query = """
    SELECT 
        a.symbol,
        p.date,
        p.close,
        ds.name as source
    FROM price_data p
    JOIN assets a ON p.asset_id = a.asset_id
    JOIN data_sources ds ON p.source_id = ds.source_id
    ORDER BY a.symbol, p.date
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def create_price_charts():
    """Create line charts for each asset's price data"""
    # Create output directory if it doesn't exist
    output_dir = "data/visualizations"
    os.makedirs(output_dir, exist_ok=True)
    
    # Get price data
    df = get_price_data()
    
    # Create a figure for each asset
    for symbol in df['symbol'].unique():
        # Filter data for this asset
        asset_data = df[df['symbol'] == symbol].copy()
        
        # Convert date to datetime
        asset_data['date'] = pd.to_datetime(asset_data['date'])
        
        # Create figure
        plt.figure(figsize=(12, 6))
        
        # Plot price data
        plt.plot(asset_data['date'], asset_data['close'], label='Close Price', color='#1f77b4')
        
        # Customize the plot
        plt.title(f'{symbol} Daily Close Price', pad=20)
        plt.xlabel('Date')
        plt.ylabel('Price (USD)')
        plt.grid(True, alpha=0.3)
        plt.legend()
        
        # Rotate x-axis labels for better readability
        plt.xticks(rotation=45)
        
        # Adjust layout to prevent label cutoff
        plt.tight_layout()
        
        # Save the plot
        plt.savefig(os.path.join(output_dir, f'{symbol.replace("/", "")}_price_chart.png'))
        plt.close()
        
        print(f"Created chart for {symbol}")

def create_combined_chart():
    """Create a combined chart with multiple assets"""
    # Get price data
    df = get_price_data()
    
    # Create figure
    plt.figure(figsize=(15, 8))
    
    # Plot data for each asset
    for symbol in df['symbol'].unique():
        # Filter data for this asset
        asset_data = df[df['symbol'] == symbol].copy()
        
        # Convert date to datetime
        asset_data['date'] = pd.to_datetime(asset_data['date'])
        
        # Plot price data
        plt.plot(asset_data['date'], asset_data['close'], label=symbol, alpha=0.7)
    
    # Customize the plot
    plt.title('Combined Daily Close Prices', pad=20)
    plt.xlabel('Date')
    plt.ylabel('Price (USD)')
    plt.grid(True, alpha=0.3)
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    
    # Rotate x-axis labels for better readability
    plt.xticks(rotation=45)
    
    # Adjust layout to prevent label cutoff
    plt.tight_layout()
    
    # Save the plot
    output_dir = "data/visualizations"
    os.makedirs(output_dir, exist_ok=True)
    plt.savefig(os.path.join(output_dir, 'combined_price_chart.png'), bbox_inches='tight')
    plt.close()
    
    print("Created combined price chart")

def create_normalized_chart():
    """Create a normalized chart showing relative price changes"""
    # Get price data
    df = get_price_data()
    
    # Create figure
    plt.figure(figsize=(15, 8))
    
    # Plot normalized data for each asset
    for symbol in df['symbol'].unique():
        # Filter data for this asset
        asset_data = df[df['symbol'] == symbol].copy()
        
        # Skip assets with very few records
        if len(asset_data) < 10:
            continue
            
        # Convert date to datetime
        asset_data['date'] = pd.to_datetime(asset_data['date'])
        
        # Normalize prices to start at 100
        normalized_price = asset_data['close'] / asset_data['close'].iloc[0] * 100
        
        # Plot normalized price data
        plt.plot(asset_data['date'], normalized_price, label=symbol, alpha=0.7)
    
    # Customize the plot
    plt.title('Normalized Daily Close Prices (Base 100)', pad=20)
    plt.xlabel('Date')
    plt.ylabel('Normalized Price (100 = Start)')
    plt.grid(True, alpha=0.3)
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    
    # Rotate x-axis labels for better readability
    plt.xticks(rotation=45)
    
    # Adjust layout to prevent label cutoff
    plt.tight_layout()
    
    # Save the plot
    output_dir = "data/visualizations"
    os.makedirs(output_dir, exist_ok=True)
    plt.savefig(os.path.join(output_dir, 'normalized_price_chart.png'), bbox_inches='tight')
    plt.close()
    
    print("Created normalized price chart")

if __name__ == "__main__":
    print("Creating individual price charts...")
    create_price_charts()
    
    print("\nCreating combined price chart...")
    create_combined_chart()
    
    print("\nCreating normalized price chart...")
    create_normalized_chart()
    
    print("\nAll charts have been created in the data/visualizations directory") 