#!/usr/bin/env python3
"""
Portfolio Analytics Dashboard Demo Script

This script demonstrates the key features and improvements of the enhanced dashboard.
"""

import time
import pandas as pd
import sys
import os

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def demo_data_loading():
    """Demonstrate fast data loading capabilities"""
    print("🚀 DEMO: Fast Data Loading")
    print("-" * 40)
    
    start_time = time.time()
    transactions = pd.read_csv("output/transactions_normalized.csv", parse_dates=["timestamp"])
    load_time = time.time() - start_time
    
    print(f"✅ Loaded {len(transactions):,} transactions in {load_time:.3f}s")
    print(f"📊 Data covers {(transactions['timestamp'].max() - transactions['timestamp'].min()).days} days")
    print(f"💰 Tracking {transactions['asset'].nunique()} different assets")
    print(f"🏦 From {transactions['institution'].nunique()} institutions")
    print()

def demo_performance_metrics():
    """Demonstrate performance calculation capabilities"""
    print("📈 DEMO: Performance Calculations")
    print("-" * 40)
    
    transactions = pd.read_csv("output/transactions_normalized.csv", parse_dates=["timestamp"])
    
    # Quick portfolio value calculation
    start_time = time.time()
    
    # Calculate simple metrics
    total_volume = (transactions['quantity'] * transactions['price']).sum()
    total_fees = transactions['fees'].sum()
    avg_transaction_size = total_volume / len(transactions)
    
    calc_time = time.time() - start_time
    
    print(f"⚡ Calculated metrics in {calc_time:.3f}s:")
    print(f"   💵 Total Volume: ${total_volume:,.2f}")
    print(f"   💸 Total Fees: ${total_fees:,.2f}")
    print(f"   📊 Avg Transaction: ${avg_transaction_size:,.2f}")
    print(f"   📅 Date Range: {transactions['timestamp'].min().strftime('%Y-%m-%d')} to {transactions['timestamp'].max().strftime('%Y-%m-%d')}")
    print()

def demo_asset_analysis():
    """Demonstrate asset analysis capabilities"""
    print("🏗️ DEMO: Asset Analysis")
    print("-" * 40)
    
    transactions = pd.read_csv("output/transactions_normalized.csv", parse_dates=["timestamp"])
    
    # Asset breakdown
    asset_summary = transactions.groupby('asset').agg({
        'quantity': 'sum',
        'price': 'mean',
        'fees': 'sum'
    }).round(4)
    
    # Top assets by volume
    asset_volume = transactions.groupby('asset').apply(
        lambda x: (x['quantity'] * x['price']).sum()
    ).sort_values(ascending=False)
    
    print("🔝 Top 5 Assets by Volume:")
    for i, (asset, volume) in enumerate(asset_volume.head().items(), 1):
        print(f"   {i}. {asset}: ${volume:,.2f}")
    
    print(f"\n📊 Asset Statistics:")
    print(f"   🎯 Total Assets: {len(asset_summary)}")
    print(f"   📈 Most Active: {transactions.groupby('asset').size().idxmax()}")
    print(f"   💎 Highest Avg Price: {asset_summary['price'].idxmax()}")
    print()

def demo_transaction_types():
    """Demonstrate transaction type analysis"""
    print("📋 DEMO: Transaction Analysis")
    print("-" * 40)
    
    transactions = pd.read_csv("output/transactions_normalized.csv", parse_dates=["timestamp"])
    
    # Transaction type breakdown
    type_summary = transactions.groupby('type').agg({
        'quantity': 'count',
        'price': lambda x: (transactions.loc[x.index, 'quantity'] * x).sum()
    }).round(2)
    type_summary.columns = ['Count', 'Total_Value']
    
    print("📊 Transaction Types:")
    for tx_type, row in type_summary.iterrows():
        print(f"   {tx_type}: {row['Count']} transactions, ${row['Total_Value']:,.2f} volume")
    
    # Recent activity
    recent = transactions.sort_values('timestamp').tail(5)
    print(f"\n🕒 Recent Transactions:")
    for _, tx in recent.iterrows():
        print(f"   {tx['timestamp'].strftime('%Y-%m-%d')}: {tx['type']} {tx['quantity']:.4f} {tx['asset']} @ ${tx['price']:.2f}")
    print()

def demo_time_analysis():
    """Demonstrate time-based analysis"""
    print("📅 DEMO: Time-Based Analysis")
    print("-" * 40)
    
    transactions = pd.read_csv("output/transactions_normalized.csv", parse_dates=["timestamp"])
    
    # Monthly activity
    monthly_activity = transactions.groupby(transactions['timestamp'].dt.to_period('M')).agg({
        'quantity': 'count',
        'price': lambda x: (transactions.loc[x.index, 'quantity'] * x).sum()
    })
    monthly_activity.columns = ['Transactions', 'Volume']
    
    print("📈 Activity by Year:")
    yearly = transactions.groupby(transactions['timestamp'].dt.year).size()
    for year, count in yearly.items():
        print(f"   {year}: {count} transactions")
    
    print(f"\n🔥 Most Active Month: {monthly_activity['Transactions'].idxmax()}")
    print(f"💰 Highest Volume Month: {monthly_activity['Volume'].idxmax()}")
    print(f"📊 Average Monthly Transactions: {monthly_activity['Transactions'].mean():.1f}")
    print()

def demo_data_quality():
    """Demonstrate data quality checks"""
    print("✅ DEMO: Data Quality Assessment")
    print("-" * 40)
    
    transactions = pd.read_csv("output/transactions_normalized.csv", parse_dates=["timestamp"])
    
    # Data quality metrics
    total_records = len(transactions)
    missing_data = transactions.isnull().sum()
    duplicate_records = transactions.duplicated().sum()
    
    print(f"📊 Data Quality Report:")
    print(f"   📝 Total Records: {total_records:,}")
    print(f"   🔍 Duplicate Records: {duplicate_records}")
    print(f"   ❌ Missing Values:")
    
    for col, missing in missing_data.items():
        if missing > 0:
            print(f"      {col}: {missing} ({missing/total_records*100:.1f}%)")
    
    # Data completeness
    completeness = (1 - missing_data.sum() / (len(transactions) * len(transactions.columns))) * 100
    print(f"   ✅ Data Completeness: {completeness:.1f}%")
    
    # Date range validation
    date_range = transactions['timestamp'].max() - transactions['timestamp'].min()
    print(f"   📅 Date Range: {date_range.days} days")
    print()

def main():
    """Run the complete dashboard demo"""
    print("🎯 Portfolio Analytics Dashboard - Feature Demo")
    print("=" * 60)
    print()
    
    try:
        # Check if data exists
        if not os.path.exists("output/transactions_normalized.csv"):
            print("❌ Error: No transaction data found!")
            print("Please run the data pipeline first: python main.py")
            return 1
        
        # Run demo sections
        demo_data_loading()
        demo_performance_metrics()
        demo_asset_analysis()
        demo_transaction_types()
        demo_time_analysis()
        demo_data_quality()
        
        # Summary
        print("🎉 DEMO COMPLETE")
        print("=" * 60)
        print("✅ All features demonstrated successfully!")
        print()
        print("🚀 To see the enhanced dashboard in action:")
        print("   streamlit run ui/streamlit_app_v2.py --server.port 8502")
        print()
        print("📊 For performance benchmarking:")
        print("   python scripts/simple_benchmark.py")
        print()
        print("📖 For detailed improvements:")
        print("   cat DASHBOARD_IMPROVEMENTS.md")
        
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main()) 