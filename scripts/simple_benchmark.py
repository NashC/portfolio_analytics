#!/usr/bin/env python3
"""
Simplified Dashboard Performance Benchmark

This script benchmarks the basic performance metrics without complex price service calls.
"""

import time
import pandas as pd
import numpy as np
from datetime import datetime
import logging
import os
import sys

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def benchmark_data_loading():
    """Benchmark basic data loading performance"""
    logger.info("📊 Benchmarking data loading...")
    
    results = {}
    
    # Test CSV loading
    start_time = time.time()
    try:
        transactions = pd.read_csv("output/transactions_normalized.csv", parse_dates=["timestamp"])
        load_time = time.time() - start_time
        
        results['data_load_time'] = load_time
        results['transaction_count'] = len(transactions)
        results['data_size_mb'] = transactions.memory_usage(deep=True).sum() / 1024 / 1024
        results['date_range_days'] = (transactions['timestamp'].max() - transactions['timestamp'].min()).days
        results['unique_assets'] = transactions['asset'].nunique()
        
        logger.info(f"✅ Loaded {len(transactions):,} transactions in {load_time:.3f}s")
        logger.info(f"📊 Columns: {list(transactions.columns)}")
        
    except Exception as e:
        logger.error(f"❌ Error loading data: {e}")
        results['error'] = str(e)
    
    return results

def benchmark_data_processing():
    """Benchmark data processing operations"""
    logger.info("⚙️ Benchmarking data processing...")
    
    results = {}
    
    try:
        # Load data
        transactions = pd.read_csv("output/transactions_normalized.csv", parse_dates=["timestamp"])
        
        # Test grouping operations
        start_time = time.time()
        daily_summary = transactions.groupby(transactions['timestamp'].dt.date).agg({
            'quantity': 'sum',
            'price': 'mean',
            'fees': 'sum'
        })
        grouping_time = time.time() - start_time
        results['grouping_time'] = grouping_time
        
        # Test filtering operations
        start_time = time.time()
        recent_transactions = transactions[transactions['timestamp'] > transactions['timestamp'].max() - pd.Timedelta(days=30)]
        filtering_time = time.time() - start_time
        results['filtering_time'] = filtering_time
        
        # Test aggregation operations
        start_time = time.time()
        asset_summary = transactions.groupby('asset').agg({
            'quantity': ['sum', 'count'],
            'price': ['mean', 'std']
        }).round(4)
        aggregation_time = time.time() - start_time
        results['aggregation_time'] = aggregation_time
        
        # Test sorting operations
        start_time = time.time()
        sorted_transactions = transactions.sort_values(['timestamp', 'asset'])
        sorting_time = time.time() - start_time
        results['sorting_time'] = sorting_time
        
        logger.info(f"✅ Data processing completed in {sum([grouping_time, filtering_time, aggregation_time, sorting_time]):.3f}s")
        
    except Exception as e:
        logger.error(f"❌ Error in data processing: {e}")
        results['error'] = str(e)
    
    return results

def benchmark_calculations():
    """Benchmark portfolio calculations"""
    logger.info("🧮 Benchmarking calculations...")
    
    results = {}
    
    try:
        transactions = pd.read_csv("output/transactions_normalized.csv", parse_dates=["timestamp"])
        
        # Simple portfolio value calculation (without external prices)
        start_time = time.time()
        
        # Calculate cumulative holdings
        transactions_sorted = transactions.sort_values('timestamp')
        holdings = {}
        portfolio_values = []
        
        for _, tx in transactions_sorted.iterrows():
            asset = tx['asset']
            quantity = tx['quantity']
            price = tx['price']
            
            if asset not in holdings:
                holdings[asset] = 0
            
            if tx['type'] in ['buy', 'transfer_in', 'staking_reward']:
                holdings[asset] += quantity
            elif tx['type'] in ['sell', 'transfer_out']:
                holdings[asset] -= quantity
            
            # Simple portfolio value (using transaction prices)
            portfolio_value = sum(holdings[a] * price for a in holdings if holdings[a] > 0)
            portfolio_values.append({
                'timestamp': tx['timestamp'],
                'value': portfolio_value
            })
        
        calc_time = time.time() - start_time
        results['portfolio_calc_time'] = calc_time
        results['portfolio_data_points'] = len(portfolio_values)
        
        # Calculate basic statistics
        start_time = time.time()
        values = [pv['value'] for pv in portfolio_values]
        if values:
            results['max_value'] = max(values)
            results['min_value'] = min(values)
            results['avg_value'] = np.mean(values)
            results['std_value'] = np.std(values)
        
        stats_time = time.time() - start_time
        results['stats_calc_time'] = stats_time
        
        logger.info(f"✅ Calculations completed in {calc_time + stats_time:.3f}s")
        
    except Exception as e:
        logger.error(f"❌ Error in calculations: {e}")
        results['error'] = str(e)
    
    return results

def benchmark_memory_usage():
    """Benchmark memory usage"""
    logger.info("🧠 Benchmarking memory usage...")
    
    try:
        import psutil
        process = psutil.Process()
        
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Load data
        transactions = pd.read_csv("output/transactions_normalized.csv", parse_dates=["timestamp"])
        after_load_memory = process.memory_info().rss / 1024 / 1024
        
        # Create some derived data
        daily_data = transactions.groupby(transactions['timestamp'].dt.date).agg({
            'quantity': 'sum',
            'price': 'mean'
        })
        
        asset_data = transactions.groupby('asset').agg({
            'quantity': ['sum', 'count', 'mean'],
            'price': ['mean', 'std', 'min', 'max']
        })
        
        after_processing_memory = process.memory_info().rss / 1024 / 1024
        
        return {
            'initial_memory_mb': initial_memory,
            'after_load_memory_mb': after_load_memory,
            'after_processing_memory_mb': after_processing_memory,
            'memory_increase_mb': after_processing_memory - initial_memory,
            'memory_efficiency': len(transactions) / (after_processing_memory - initial_memory) if (after_processing_memory - initial_memory) > 0 else 0
        }
        
    except ImportError:
        logger.warning("psutil not available, skipping memory benchmark")
        return {'error': 'psutil not available'}
    except Exception as e:
        logger.error(f"❌ Error in memory benchmark: {e}")
        return {'error': str(e)}

def generate_performance_report(results):
    """Generate a performance report"""
    
    report = []
    report.append("=" * 60)
    report.append("📊 SIMPLIFIED DASHBOARD PERFORMANCE REPORT")
    report.append("=" * 60)
    report.append(f"Timestamp: {datetime.now().isoformat()}")
    report.append("")
    
    # Data Loading Performance
    if 'data_loading' in results:
        data = results['data_loading']
        report.append("📈 DATA LOADING PERFORMANCE")
        report.append("-" * 40)
        
        load_time = data.get('data_load_time', 'N/A')
        if isinstance(load_time, (int, float)):
            report.append(f"Load Time: {load_time:.3f}s")
        else:
            report.append(f"Load Time: {load_time}")
            
        report.append(f"Transaction Count: {data.get('transaction_count', 'N/A'):,}")
        
        data_size = data.get('data_size_mb', 'N/A')
        if isinstance(data_size, (int, float)):
            report.append(f"Data Size: {data_size:.2f}MB")
        else:
            report.append(f"Data Size: {data_size}")
            
        report.append(f"Date Range: {data.get('date_range_days', 'N/A')} days")
        report.append(f"Unique Assets: {data.get('unique_assets', 'N/A')}")
        
        # Performance rating
        if isinstance(load_time, (int, float)):
            if load_time < 0.1:
                rating = "🟢 Excellent"
            elif load_time < 0.5:
                rating = "🟡 Good"
            elif load_time < 1.0:
                rating = "🟠 Fair"
            else:
                rating = "🔴 Slow"
            report.append(f"Performance Rating: {rating}")
        report.append("")
    
    # Data Processing Performance
    if 'data_processing' in results:
        proc = results['data_processing']
        report.append("⚙️ DATA PROCESSING PERFORMANCE")
        report.append("-" * 40)
        
        for metric in ['grouping_time', 'filtering_time', 'aggregation_time', 'sorting_time']:
            value = proc.get(metric, 'N/A')
            if isinstance(value, (int, float)):
                report.append(f"{metric.replace('_', ' ').title()}: {value:.3f}s")
            else:
                report.append(f"{metric.replace('_', ' ').title()}: {value}")
        
        # Calculate total time
        times = [proc.get(metric, 0) for metric in ['grouping_time', 'filtering_time', 'aggregation_time', 'sorting_time']]
        numeric_times = [t for t in times if isinstance(t, (int, float))]
        if numeric_times:
            total_time = sum(numeric_times)
            report.append(f"Total Processing Time: {total_time:.3f}s")
        report.append("")
    
    # Calculation Performance
    if 'calculations' in results:
        calc = results['calculations']
        report.append("🧮 CALCULATION PERFORMANCE")
        report.append("-" * 40)
        
        portfolio_time = calc.get('portfolio_calc_time', 'N/A')
        stats_time = calc.get('stats_calc_time', 'N/A')
        
        if isinstance(portfolio_time, (int, float)):
            report.append(f"Portfolio Calc Time: {portfolio_time:.3f}s")
        else:
            report.append(f"Portfolio Calc Time: {portfolio_time}")
            
        if isinstance(stats_time, (int, float)):
            report.append(f"Statistics Calc Time: {stats_time:.3f}s")
        else:
            report.append(f"Statistics Calc Time: {stats_time}")
            
        report.append(f"Data Points Generated: {calc.get('portfolio_data_points', 'N/A'):,}")
        
        if 'max_value' in calc:
            report.append(f"Portfolio Value Range: ${calc.get('min_value', 0):,.2f} - ${calc.get('max_value', 0):,.2f}")
        report.append("")
    
    # Memory Usage
    if 'memory' in results:
        mem = results['memory']
        report.append("🧠 MEMORY USAGE")
        report.append("-" * 40)
        
        for metric in ['initial_memory_mb', 'after_load_memory_mb', 'after_processing_memory_mb', 'memory_increase_mb']:
            value = mem.get(metric, 'N/A')
            if isinstance(value, (int, float)):
                report.append(f"{metric.replace('_', ' ').title()}: {value:.1f}MB")
            else:
                report.append(f"{metric.replace('_', ' ').title()}: {value}")
        
        efficiency = mem.get('memory_efficiency', 'N/A')
        if isinstance(efficiency, (int, float)):
            report.append(f"Memory Efficiency: {efficiency:.1f} records/MB")
        else:
            report.append(f"Memory Efficiency: {efficiency}")
        report.append("")
    
    # Recommendations
    report.append("🎯 PERFORMANCE RECOMMENDATIONS")
    report.append("-" * 40)
    
    if 'data_loading' in results:
        load_time = results['data_loading'].get('data_load_time', 0)
        if isinstance(load_time, (int, float)):
            if load_time > 1.0:
                report.append("• Consider implementing data caching for faster load times")
            if load_time > 2.0:
                report.append("• Consider using more efficient file formats (Parquet, HDF5)")
    
    if 'memory' in results:
        memory_increase = results['memory'].get('memory_increase_mb', 0)
        if isinstance(memory_increase, (int, float)):
            if memory_increase > 100:
                report.append("• High memory usage detected - consider data chunking")
            if memory_increase > 500:
                report.append("• Very high memory usage - implement streaming processing")
    
    if 'calculations' in results:
        calc_time = results['calculations'].get('portfolio_calc_time', 0)
        if isinstance(calc_time, (int, float)) and calc_time > 2.0:
            report.append("• Portfolio calculations are slow - consider vectorization")
    
    report.append("• Implement caching for frequently accessed calculations")
    report.append("• Use lazy loading for charts and visualizations")
    report.append("• Consider pagination for large datasets")
    
    report.append("\n" + "=" * 60)
    
    return "\n".join(report)

def main():
    """Main benchmark function"""
    print("🚀 Starting Simplified Dashboard Performance Benchmark...")
    
    results = {}
    
    # Run benchmarks
    results['data_loading'] = benchmark_data_loading()
    results['data_processing'] = benchmark_data_processing()
    results['calculations'] = benchmark_calculations()
    results['memory'] = benchmark_memory_usage()
    
    # Generate report
    report = generate_performance_report(results)
    print(report)
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save detailed results
    import json
    os.makedirs("output", exist_ok=True)
    results_file = f"output/simple_benchmark_{timestamp}.json"
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    # Save report
    report_file = f"output/simple_benchmark_report_{timestamp}.txt"
    with open(report_file, 'w') as f:
        f.write(report)
    
    print(f"\n📁 Results saved to: {results_file}")
    print(f"📁 Report saved to: {report_file}")
    
    return 0

if __name__ == "__main__":
    exit(main()) 