#!/usr/bin/env python3
"""
Dashboard Performance Benchmarking Script

This script benchmarks the performance of different Streamlit dashboard implementations
to measure load times, memory usage, and responsiveness.
"""

import time
import psutil
import pandas as pd
import numpy as np
import subprocess
import requests
import threading
from datetime import datetime
from typing import Dict, List, Tuple
import logging
import json
import os
import sys

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.analytics.portfolio import (
    compute_portfolio_time_series_with_external_prices,
    calculate_cost_basis_fifo,
    calculate_cost_basis_avg
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DashboardBenchmark:
    """Benchmark Streamlit dashboard performance"""
    
    def __init__(self):
        self.results = {}
        self.base_url = "http://localhost:8501"
        
    def measure_data_loading_performance(self) -> Dict:
        """Measure data loading and processing performance"""
        logger.info("🔍 Measuring data loading performance...")
        
        results = {}
        
        # Load transaction data
        start_time = time.time()
        try:
            transactions = pd.read_csv("output/transactions_normalized.csv", parse_dates=["timestamp"])
            data_load_time = time.time() - start_time
            results['data_load_time'] = data_load_time
            results['transaction_count'] = len(transactions)
            results['data_size_mb'] = transactions.memory_usage(deep=True).sum() / 1024 / 1024
        except Exception as e:
            logger.error(f"Error loading data: {e}")
            return {'error': str(e)}
        
        # Measure portfolio computation
        start_time = time.time()
        try:
            portfolio_ts = compute_portfolio_time_series_with_external_prices(transactions)
            portfolio_compute_time = time.time() - start_time
            results['portfolio_compute_time'] = portfolio_compute_time
            results['portfolio_data_points'] = len(portfolio_ts)
        except Exception as e:
            logger.error(f"Error computing portfolio: {e}")
            results['portfolio_compute_error'] = str(e)
        
        # Measure cost basis calculations
        start_time = time.time()
        try:
            fifo_basis = calculate_cost_basis_fifo(transactions)
            fifo_time = time.time() - start_time
            results['fifo_compute_time'] = fifo_time
            results['fifo_lots'] = len(fifo_basis)
        except Exception as e:
            logger.error(f"Error computing FIFO: {e}")
            results['fifo_compute_error'] = str(e)
        
        start_time = time.time()
        try:
            avg_basis = calculate_cost_basis_avg(transactions)
            avg_time = time.time() - start_time
            results['avg_compute_time'] = avg_time
            results['avg_lots'] = len(avg_basis)
        except Exception as e:
            logger.error(f"Error computing average cost: {e}")
            results['avg_compute_error'] = str(e)
        
        return results
    
    def measure_memory_usage(self) -> Dict:
        """Measure memory usage during operations"""
        logger.info("🧠 Measuring memory usage...")
        
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Load data and measure memory
        transactions = pd.read_csv("output/transactions_normalized.csv", parse_dates=["timestamp"])
        after_load_memory = process.memory_info().rss / 1024 / 1024
        
        # Compute portfolio and measure memory
        portfolio_ts = compute_portfolio_time_series_with_external_prices(transactions)
        after_compute_memory = process.memory_info().rss / 1024 / 1024
        
        return {
            'initial_memory_mb': initial_memory,
            'after_load_memory_mb': after_load_memory,
            'after_compute_memory_mb': after_compute_memory,
            'memory_increase_mb': after_compute_memory - initial_memory,
            'data_to_memory_ratio': len(transactions) / (after_compute_memory - initial_memory)
        }
    
    def start_streamlit_app(self, app_file: str, port: int) -> subprocess.Popen:
        """Start a Streamlit app and return the process"""
        cmd = [
            "streamlit", "run", app_file,
            "--server.port", str(port),
            "--server.headless", "true",
            "--browser.gatherUsageStats", "false"
        ]
        
        logger.info(f"🚀 Starting Streamlit app: {app_file} on port {port}")
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        
        # Wait for app to start
        time.sleep(10)
        return process
    
    def measure_app_response_time(self, port: int) -> Dict:
        """Measure app response times"""
        base_url = f"http://localhost:{port}"
        results = {}
        
        try:
            # Measure initial page load
            start_time = time.time()
            response = requests.get(base_url, timeout=30)
            initial_load_time = time.time() - start_time
            
            results['initial_load_time'] = initial_load_time
            results['status_code'] = response.status_code
            results['response_size_kb'] = len(response.content) / 1024
            
            # Measure subsequent requests (cached)
            times = []
            for i in range(5):
                start_time = time.time()
                response = requests.get(base_url, timeout=10)
                request_time = time.time() - start_time
                times.append(request_time)
                time.sleep(1)
            
            results['avg_cached_load_time'] = np.mean(times)
            results['min_cached_load_time'] = np.min(times)
            results['max_cached_load_time'] = np.max(times)
            
        except Exception as e:
            logger.error(f"Error measuring response time: {e}")
            results['error'] = str(e)
        
        return results
    
    def benchmark_app(self, app_file: str, app_name: str, port: int) -> Dict:
        """Benchmark a specific Streamlit app"""
        logger.info(f"📊 Benchmarking {app_name}...")
        
        results = {'app_name': app_name, 'app_file': app_file}
        
        # Start the app
        process = None
        try:
            process = self.start_streamlit_app(app_file, port)
            
            # Measure response times
            response_results = self.measure_app_response_time(port)
            results.update(response_results)
            
            # Measure memory usage of the Streamlit process
            try:
                streamlit_process = None
                for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                    if 'streamlit' in proc.info['name'].lower():
                        if str(port) in ' '.join(proc.info['cmdline']):
                            streamlit_process = proc
                            break
                
                if streamlit_process:
                    memory_info = streamlit_process.memory_info()
                    results['app_memory_mb'] = memory_info.rss / 1024 / 1024
                    results['app_cpu_percent'] = streamlit_process.cpu_percent()
                
            except Exception as e:
                logger.warning(f"Could not measure app memory: {e}")
            
        except Exception as e:
            logger.error(f"Error benchmarking {app_name}: {e}")
            results['error'] = str(e)
        
        finally:
            # Clean up
            if process:
                process.terminate()
                time.sleep(2)
                if process.poll() is None:
                    process.kill()
        
        return results
    
    def run_comprehensive_benchmark(self) -> Dict:
        """Run comprehensive benchmark of all dashboard versions"""
        logger.info("🏁 Starting comprehensive dashboard benchmark...")
        
        benchmark_results = {
            'timestamp': datetime.now().isoformat(),
            'system_info': {
                'cpu_count': psutil.cpu_count(),
                'memory_gb': psutil.virtual_memory().total / 1024 / 1024 / 1024,
                'python_version': sys.version
            }
        }
        
        # Measure data processing performance
        benchmark_results['data_performance'] = self.measure_data_loading_performance()
        benchmark_results['memory_usage'] = self.measure_memory_usage()
        
        # Benchmark different app versions
        apps_to_test = [
            ('ui/streamlit_app.py', 'Original Dashboard', 8501),
            ('ui/streamlit_app_v2.py', 'Enhanced Dashboard', 8502)
        ]
        
        app_results = []
        for app_file, app_name, port in apps_to_test:
            if os.path.exists(app_file):
                result = self.benchmark_app(app_file, app_name, port)
                app_results.append(result)
            else:
                logger.warning(f"App file not found: {app_file}")
        
        benchmark_results['app_performance'] = app_results
        
        return benchmark_results
    
    def generate_performance_report(self, results: Dict) -> str:
        """Generate a human-readable performance report"""
        report = []
        report.append("=" * 60)
        report.append("📊 DASHBOARD PERFORMANCE BENCHMARK REPORT")
        report.append("=" * 60)
        report.append(f"Timestamp: {results['timestamp']}")
        report.append(f"System: {results['system_info']['cpu_count']} CPUs, {results['system_info']['memory_gb']:.1f}GB RAM")
        report.append("")
        
        # Data Performance
        if 'data_performance' in results:
            data_perf = results['data_performance']
            report.append("📈 DATA PROCESSING PERFORMANCE")
            report.append("-" * 40)
            report.append(f"Data Load Time: {data_perf.get('data_load_time', 'N/A'):.3f}s")
            report.append(f"Transaction Count: {data_perf.get('transaction_count', 'N/A'):,}")
            report.append(f"Data Size: {data_perf.get('data_size_mb', 'N/A'):.2f}MB")
            report.append(f"Portfolio Compute Time: {data_perf.get('portfolio_compute_time', 'N/A'):.3f}s")
            report.append(f"FIFO Compute Time: {data_perf.get('fifo_compute_time', 'N/A'):.3f}s")
            report.append(f"Avg Cost Compute Time: {data_perf.get('avg_compute_time', 'N/A'):.3f}s")
            report.append("")
        
        # Memory Usage
        if 'memory_usage' in results:
            mem_usage = results['memory_usage']
            report.append("🧠 MEMORY USAGE")
            report.append("-" * 40)
            report.append(f"Initial Memory: {mem_usage.get('initial_memory_mb', 'N/A'):.1f}MB")
            report.append(f"After Data Load: {mem_usage.get('after_load_memory_mb', 'N/A'):.1f}MB")
            report.append(f"After Computation: {mem_usage.get('after_compute_memory_mb', 'N/A'):.1f}MB")
            report.append(f"Memory Increase: {mem_usage.get('memory_increase_mb', 'N/A'):.1f}MB")
            report.append("")
        
        # App Performance Comparison
        if 'app_performance' in results:
            report.append("🚀 APP PERFORMANCE COMPARISON")
            report.append("-" * 40)
            
            for app_result in results['app_performance']:
                report.append(f"\n{app_result['app_name']}:")
                report.append(f"  Initial Load Time: {app_result.get('initial_load_time', 'N/A'):.3f}s")
                report.append(f"  Avg Cached Load Time: {app_result.get('avg_cached_load_time', 'N/A'):.3f}s")
                report.append(f"  App Memory Usage: {app_result.get('app_memory_mb', 'N/A'):.1f}MB")
                report.append(f"  Response Size: {app_result.get('response_size_kb', 'N/A'):.1f}KB")
                
                if 'error' in app_result:
                    report.append(f"  ❌ Error: {app_result['error']}")
        
        # Performance Recommendations
        report.append("\n🎯 PERFORMANCE RECOMMENDATIONS")
        report.append("-" * 40)
        
        if 'data_performance' in results:
            data_perf = results['data_performance']
            if data_perf.get('data_load_time', 0) > 1.0:
                report.append("• Consider implementing data caching for faster load times")
            if data_perf.get('portfolio_compute_time', 0) > 2.0:
                report.append("• Portfolio computation is slow - consider optimization")
        
        if 'app_performance' in results and len(results['app_performance']) >= 2:
            apps = results['app_performance']
            if len(apps) >= 2:
                original_time = apps[0].get('initial_load_time', float('inf'))
                enhanced_time = apps[1].get('initial_load_time', float('inf'))
                
                if enhanced_time < original_time:
                    improvement = ((original_time - enhanced_time) / original_time) * 100
                    report.append(f"• Enhanced dashboard is {improvement:.1f}% faster than original")
                else:
                    degradation = ((enhanced_time - original_time) / original_time) * 100
                    report.append(f"• Enhanced dashboard is {degradation:.1f}% slower - needs optimization")
        
        report.append("\n" + "=" * 60)
        
        return "\n".join(report)
    
    def save_results(self, results: Dict, filename: str = None):
        """Save benchmark results to file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"output/benchmark_results_{timestamp}.json"
        
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        logger.info(f"📁 Results saved to: {filename}")
        return filename

def main():
    """Main benchmarking function"""
    print("🚀 Starting Dashboard Performance Benchmark...")
    
    benchmark = DashboardBenchmark()
    
    try:
        # Run comprehensive benchmark
        results = benchmark.run_comprehensive_benchmark()
        
        # Generate and display report
        report = benchmark.generate_performance_report(results)
        print(report)
        
        # Save results
        results_file = benchmark.save_results(results)
        
        # Save report
        report_file = results_file.replace('.json', '_report.txt')
        with open(report_file, 'w') as f:
            f.write(report)
        
        print(f"\n📁 Detailed results saved to: {results_file}")
        print(f"📁 Report saved to: {report_file}")
        
    except Exception as e:
        logger.error(f"Benchmark failed: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main()) 