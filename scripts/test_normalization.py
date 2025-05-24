#!/usr/bin/env python3
"""
Quick test runner for normalization functionality.
This script runs the comprehensive normalization tests and provides a summary.
"""

import subprocess
import sys
import time
import os
from pathlib import Path

def run_normalization_tests():
    """Run the comprehensive normalization test suite."""
    print("🧪 Running Comprehensive Normalization Tests")
    print("=" * 50)
    
    start_time = time.time()
    
    # Set up environment
    project_root = Path(__file__).parent.parent
    env = os.environ.copy()
    env['PYTHONPATH'] = str(project_root)
    
    # Run the tests
    cmd = [
        sys.executable, "-m", "pytest", 
        "tests/test_normalization_comprehensive.py",
        "-v", "--tb=short"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=project_root, env=env)
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"\n⏱️  Test Duration: {duration:.2f} seconds")
        
        if result.returncode == 0:
            print("✅ All normalization tests passed!")
            
            # Extract test count from output
            lines = result.stdout.split('\n')
            for line in lines:
                if 'passed' in line and 'in' in line:
                    print(f"📊 {line.strip()}")
                    break
        else:
            print("❌ Some tests failed!")
            print("\nSTDOUT:")
            print(result.stdout)
            print("\nSTDERR:")
            print(result.stderr)
            
        return result.returncode == 0
        
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return False

def test_with_real_data():
    """Test normalization with real data files."""
    print("\n🔍 Testing with Real Data")
    print("=" * 30)
    
    try:
        # Add project root to Python path
        project_root = Path(__file__).parent.parent
        sys.path.insert(0, str(project_root))
        
        from app.ingestion.normalization import normalize_data
        import pandas as pd
        
        # Test with Interactive Brokers data if available
        ib_file = project_root / "output" / "interactive_brokers_processed.csv"
        if ib_file.exists():
            print(f"📁 Testing with {ib_file}")
            df = pd.read_csv(ib_file)
            
            print(f"   Input: {len(df)} transactions")
            
            normalized = normalize_data(df)
            
            print(f"   Output: {len(normalized)} transactions")
            print(f"   Transaction types: {list(normalized['type'].value_counts().index)}")
            print("   ✅ Real data test passed")
        else:
            print("   ⚠️  No real data file found, skipping real data test")
            
    except Exception as e:
        print(f"   ❌ Real data test failed: {e}")

def main():
    """Main test runner."""
    print("🚀 Portfolio Analytics - Normalization Test Suite")
    print("=" * 60)
    
    # Run comprehensive tests
    tests_passed = run_normalization_tests()
    
    # Test with real data
    test_with_real_data()
    
    print("\n" + "=" * 60)
    if tests_passed:
        print("🎉 All tests completed successfully!")
        sys.exit(0)
    else:
        print("💥 Some tests failed. Please check the output above.")
        sys.exit(1)

if __name__ == "__main__":
    main() 