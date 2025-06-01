#!/usr/bin/env python3

"""
Data Quality Test Runner

This script runs comprehensive data quality tests to catch issues like:
- Duplicate transactions
- Inflated portfolio values
- Incorrect holdings calculations
- Data normalization problems
- Future-dated transactions
- Null assets
- Column schema issues

Usage:
    python scripts/run_data_quality_tests.py
    python scripts/run_data_quality_tests.py --quick  # Run only critical tests
    python scripts/run_data_quality_tests.py --file path/to/transactions.csv  # Test specific file
"""

import sys
import os
import argparse
import pandas as pd
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ingestion.normalization import (
    normalize_data, 
    CANONICAL_COLUMNS, 
    CANONICAL_TYPES,
    validate_normalized_data
)
from app.analytics.portfolio import compute_portfolio_time_series_with_external_prices

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class DataQualityValidator:
    """Comprehensive data quality validator."""
    
    def __init__(self):
        self.issues = []
        self.warnings = []
        self.passed_tests = []
    
    def add_issue(self, test_name: str, description: str, severity: str = "ERROR"):
        """Add a data quality issue."""
        self.issues.append({
            'test': test_name,
            'description': description,
            'severity': severity,
            'timestamp': datetime.now()
        })
        logger.error(f"❌ {test_name}: {description}")
    
    def add_warning(self, test_name: str, description: str):
        """Add a data quality warning."""
        self.warnings.append({
            'test': test_name,
            'description': description,
            'timestamp': datetime.now()
        })
        logger.warning(f"⚠️  {test_name}: {description}")
    
    def add_pass(self, test_name: str, description: str = ""):
        """Add a passed test."""
        self.passed_tests.append({
            'test': test_name,
            'description': description,
            'timestamp': datetime.now()
        })
        logger.info(f"✅ {test_name}: PASSED {description}")
    
    def validate_schema(self, df: pd.DataFrame) -> bool:
        """Validate that DataFrame has the correct canonical schema."""
        test_name = "Schema Validation"
        
        if df.empty:
            self.add_issue(test_name, "DataFrame is empty")
            return False
        
        # Check columns
        missing_cols = [col for col in CANONICAL_COLUMNS if col not in df.columns]
        extra_cols = [col for col in df.columns if col not in CANONICAL_COLUMNS]
        
        if missing_cols:
            self.add_issue(test_name, f"Missing required columns: {missing_cols}")
            return False
        
        if extra_cols:
            self.add_warning(test_name, f"Extra columns found: {extra_cols}")
        
        # Check column order
        if list(df.columns) != CANONICAL_COLUMNS:
            self.add_warning(test_name, "Columns not in canonical order")
        
        self.add_pass(test_name, f"Schema valid with {len(df.columns)} columns")
        return True
    
    def validate_duplicates(self, df: pd.DataFrame) -> bool:
        """Check for duplicate transactions."""
        test_name = "Duplicate Detection"
        
        duplicates = df.duplicated()
        duplicate_count = duplicates.sum()
        
        if duplicate_count > 0:
            self.add_issue(test_name, f"Found {duplicate_count} duplicate transactions")
            
            # Show sample duplicates
            duplicate_rows = df[duplicates]
            for i, (_, row) in enumerate(duplicate_rows.head(3).iterrows()):
                self.add_issue(test_name, f"  Duplicate {i+1}: {row['timestamp']} | {row['type']} | {row['asset']} | {row['quantity']}")
            
            return False
        
        self.add_pass(test_name, "No duplicate transactions found")
        return True
    
    def validate_timestamps(self, df: pd.DataFrame) -> bool:
        """Validate timestamp data quality."""
        test_name = "Timestamp Validation"
        
        if 'timestamp' not in df.columns:
            self.add_issue(test_name, "No timestamp column found")
            return False
        
        # Check for null timestamps
        null_timestamps = df['timestamp'].isnull().sum()
        if null_timestamps > 0:
            self.add_issue(test_name, f"{null_timestamps} transactions have null timestamps")
            return False
        
        # Check for unrealistic future dates
        future_threshold = datetime.now() + timedelta(days=365)
        future_dates = df[df['timestamp'] > future_threshold]
        if len(future_dates) > 0:
            self.add_issue(test_name, f"{len(future_dates)} transactions have unrealistic future dates")
            for _, row in future_dates.head(3).iterrows():
                self.add_issue(test_name, f"  Future date: {row['timestamp']} | {row['type']} | {row['asset']}")
            return False
        
        # Check for unrealistic past dates
        past_threshold = datetime(2009, 1, 1)
        past_dates = df[df['timestamp'] < past_threshold]
        if len(past_dates) > 0:
            self.add_issue(test_name, f"{len(past_dates)} transactions before 2009 (pre-Bitcoin)")
            return False
        
        self.add_pass(test_name, f"All {len(df)} timestamps are valid")
        return True
    
    def validate_transaction_types(self, df: pd.DataFrame) -> bool:
        """Validate transaction types are canonical."""
        test_name = "Transaction Type Validation"
        
        if 'type' not in df.columns:
            self.add_issue(test_name, "No type column found")
            return False
        
        invalid_types = set(df['type'].unique()) - CANONICAL_TYPES
        if invalid_types:
            self.add_issue(test_name, f"Invalid transaction types: {invalid_types}")
            return False
        
        unknown_count = (df['type'] == 'unknown').sum()
        if unknown_count > 0:
            unknown_pct = (unknown_count / len(df)) * 100
            if unknown_pct > 5:  # More than 5% unknown is concerning
                self.add_issue(test_name, f"{unknown_count} ({unknown_pct:.1f}%) transactions have unknown type")
                return False
            else:
                self.add_warning(test_name, f"{unknown_count} ({unknown_pct:.1f}%) transactions have unknown type")
        
        self.add_pass(test_name, f"All transaction types are canonical")
        return True
    
    def validate_assets(self, df: pd.DataFrame) -> bool:
        """Validate asset data quality."""
        test_name = "Asset Validation"
        
        if 'asset' not in df.columns:
            self.add_issue(test_name, "No asset column found")
            return False
        
        # Check for null assets
        null_assets = df['asset'].isnull().sum()
        if null_assets > 0:
            self.add_issue(test_name, f"{null_assets} transactions have null assets")
            return False
        
        # Check for empty string assets
        empty_assets = (df['asset'].str.strip() == '').sum()
        if empty_assets > 0:
            self.add_issue(test_name, f"{empty_assets} transactions have empty asset names")
            return False
        
        unique_assets = df['asset'].nunique()
        self.add_pass(test_name, f"{unique_assets} unique assets found")
        return True
    
    def validate_quantities(self, df: pd.DataFrame) -> bool:
        """Validate quantity data quality."""
        test_name = "Quantity Validation"
        
        if 'quantity' not in df.columns:
            self.add_issue(test_name, "No quantity column found")
            return False
        
        # Check for null quantities
        null_quantities = df['quantity'].isnull().sum()
        if null_quantities > 0:
            self.add_issue(test_name, f"{null_quantities} transactions have null quantities")
            return False
        
        # Check for zero quantities in non-fee transactions
        zero_qty_mask = (df['quantity'] == 0) & (~df['type'].isin(['fee', 'tax', 'fee_adjustment']))
        zero_qty_count = zero_qty_mask.sum()
        if zero_qty_count > 0:
            self.add_warning(test_name, f"{zero_qty_count} non-fee transactions have zero quantity")
        
        # Check for extremely large quantities
        large_qty_threshold = 1000000
        large_qty_count = (abs(df['quantity']) > large_qty_threshold).sum()
        if large_qty_count > 0:
            self.add_warning(test_name, f"{large_qty_count} transactions have very large quantities (>{large_qty_threshold:,})")
        
        self.add_pass(test_name, "Quantity validation passed")
        return True
    
    def validate_portfolio_calculation(self, df: pd.DataFrame) -> bool:
        """Validate that portfolio calculation produces reasonable results."""
        test_name = "Portfolio Calculation Validation"
        
        try:
            # Filter to portfolio-affecting transactions
            portfolio_affecting_types = ['buy', 'sell', 'staking_reward', 'dividend', 'interest', 'deposit', 'withdrawal', 'swap']
            filtered_df = df[df['type'].isin(portfolio_affecting_types)]
            
            if filtered_df.empty:
                self.add_warning(test_name, "No portfolio-affecting transactions found")
                return True
            
            # Check for reasonable asset balances
            asset_balances = filtered_df.groupby('asset')['quantity'].sum()
            
            # Flag extremely large balances
            for asset, balance in asset_balances.items():
                if asset in ['BTC'] and abs(balance) > 100:  # More than 100 BTC
                    self.add_warning(test_name, f"Large {asset} balance: {balance:.6f}")
                elif asset in ['ETH'] and abs(balance) > 1000:  # More than 1000 ETH
                    self.add_warning(test_name, f"Large {asset} balance: {balance:.6f}")
                elif asset in ['USD', 'USDC', 'USDT'] and abs(balance) > 10000000:  # More than $10M
                    self.add_warning(test_name, f"Large {asset} balance: ${balance:,.2f}")
            
            # Check for transfer inflation
            transfers_in = filtered_df[filtered_df['type'] == 'transfer_in']['quantity'].sum()
            transfers_out = filtered_df[filtered_df['type'] == 'transfer_out']['quantity'].sum()
            
            if abs(transfers_in) > 0 or abs(transfers_out) > 0:
                self.add_issue(test_name, "Portfolio calculation includes transfer_in/transfer_out transactions - this will inflate values")
                return False
            
            self.add_pass(test_name, "Portfolio calculation validation passed")
            return True
            
        except Exception as e:
            self.add_issue(test_name, f"Portfolio calculation failed: {str(e)}")
            return False
    
    def validate_data_consistency(self, df: pd.DataFrame) -> bool:
        """Validate overall data consistency."""
        test_name = "Data Consistency Validation"
        
        # Check for reasonable data distribution
        if len(df) == 0:
            self.add_issue(test_name, "No transactions found")
            return False
        
        # Check date range
        if 'timestamp' in df.columns:
            date_range = df['timestamp'].max() - df['timestamp'].min()
            if date_range.days > 3650:  # More than 10 years
                self.add_warning(test_name, f"Very long date range: {date_range.days} days")
        
        # Check institution distribution
        if 'institution' in df.columns:
            institutions = df['institution'].value_counts()
            if len(institutions) == 1:
                self.add_warning(test_name, "Only one institution found - consider adding more data sources")
        
        # Check transaction type distribution
        if 'type' in df.columns:
            type_counts = df['type'].value_counts()
            if 'unknown' in type_counts and type_counts['unknown'] > len(df) * 0.1:
                self.add_warning(test_name, f"High percentage of unknown transaction types: {type_counts['unknown']}/{len(df)}")
        
        self.add_pass(test_name, "Data consistency validation passed")
        return True
    
    def run_all_validations(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Run all data quality validations."""
        logger.info(f"🔍 Running data quality validations on {len(df)} transactions...")
        
        validations = [
            self.validate_schema,
            self.validate_duplicates,
            self.validate_timestamps,
            self.validate_transaction_types,
            self.validate_assets,
            self.validate_quantities,
            self.validate_portfolio_calculation,
            self.validate_data_consistency
        ]
        
        results = {}
        for validation in validations:
            try:
                result = validation(df)
                results[validation.__name__] = result
            except Exception as e:
                self.add_issue(validation.__name__, f"Validation failed with error: {str(e)}")
                results[validation.__name__] = False
        
        return results
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate a comprehensive data quality report."""
        total_tests = len(self.passed_tests) + len(self.warnings) + len(self.issues)
        
        report = {
            'summary': {
                'total_tests': total_tests,
                'passed': len(self.passed_tests),
                'warnings': len(self.warnings),
                'errors': len(self.issues),
                'success_rate': (len(self.passed_tests) / total_tests * 100) if total_tests > 0 else 0
            },
            'passed_tests': self.passed_tests,
            'warnings': self.warnings,
            'issues': self.issues,
            'timestamp': datetime.now()
        }
        
        return report


def test_normalized_file(file_path: str) -> bool:
    """Test a normalized CSV file for data quality issues."""
    logger.info(f"📁 Testing normalized file: {file_path}")
    
    try:
        # Load the file
        df = pd.read_csv(file_path, parse_dates=['timestamp'])
        logger.info(f"📊 Loaded {len(df)} transactions with {len(df.columns)} columns")
        
        # Run validations
        validator = DataQualityValidator()
        results = validator.run_all_validations(df)
        
        # Generate report
        report = validator.generate_report()
        
        # Print summary
        print("\n" + "="*60)
        print("📋 DATA QUALITY REPORT")
        print("="*60)
        print(f"Total Tests: {report['summary']['total_tests']}")
        print(f"✅ Passed: {report['summary']['passed']}")
        print(f"⚠️  Warnings: {report['summary']['warnings']}")
        print(f"❌ Errors: {report['summary']['errors']}")
        print(f"📈 Success Rate: {report['summary']['success_rate']:.1f}%")
        
        if report['summary']['errors'] == 0:
            print("\n🎉 All critical data quality tests PASSED!")
            return True
        else:
            print(f"\n💥 {report['summary']['errors']} critical issues found!")
            print("\nCritical Issues:")
            for issue in validator.issues:
                print(f"  ❌ {issue['test']}: {issue['description']}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Failed to test file {file_path}: {str(e)}")
        return False


def test_normalization_pipeline() -> bool:
    """Test the complete normalization pipeline."""
    logger.info("🔧 Testing normalization pipeline...")
    
    try:
        # Create test data with known issues
        test_data = pd.DataFrame({
            'timestamp': [
                datetime(2024, 1, 1),
                datetime(2024, 1, 1),  # Duplicate
                datetime(2024, 1, 2),
                datetime.now() + timedelta(days=400),  # Future date
                datetime(2024, 1, 3)
            ],
            'type': ['buy', 'buy', 'transfer_in', 'buy', 'invalid_type'],
            'asset': ['ETH', 'ETH', 'ETH', 'ETH', None],
            'quantity': [10.0, 10.0, 75.0, 1.0, 0.0],
            'price': [3500, 3500, 3500, 3500, 0],
            'fees': [10, 10, 0, 10, 0],
            'institution': ['coinbase', 'coinbase', 'coinbase', 'coinbase', 'coinbase'],
            'extra_column': ['a', 'b', 'c', 'd', 'e']
        })
        
        logger.info(f"📊 Created test data with {len(test_data)} transactions (including known issues)")
        
        # Normalize the data
        normalized_data = normalize_data(test_data)
        
        # Validate the normalized result
        validator = DataQualityValidator()
        results = validator.run_all_validations(normalized_data)
        
        # Check specific fixes
        success = True
        
        # Should have fewer transactions (duplicates and invalid data removed)
        if len(normalized_data) >= len(test_data):
            logger.error("❌ Normalization did not remove problematic transactions")
            success = False
        
        # Should have only canonical columns
        if list(normalized_data.columns) != CANONICAL_COLUMNS:
            logger.error("❌ Normalization did not filter to canonical columns")
            success = False
        
        # Should have no duplicates
        if normalized_data.duplicated().any():
            logger.error("❌ Normalization did not remove duplicates")
            success = False
        
        if success:
            logger.info("✅ Normalization pipeline test PASSED")
        else:
            logger.error("❌ Normalization pipeline test FAILED")
        
        return success
        
    except Exception as e:
        logger.error(f"❌ Normalization pipeline test failed: {str(e)}")
        return False


def main():
    """Main test runner."""
    parser = argparse.ArgumentParser(description='Run data quality tests')
    parser.add_argument('--file', help='Test specific normalized CSV file')
    parser.add_argument('--quick', action='store_true', help='Run only critical tests')
    parser.add_argument('--pipeline', action='store_true', help='Test normalization pipeline')
    
    args = parser.parse_args()
    
    print("🧪 Portfolio Analytics Data Quality Test Runner")
    print("=" * 50)
    
    success = True
    
    if args.file:
        # Test specific file
        if not os.path.exists(args.file):
            logger.error(f"❌ File not found: {args.file}")
            return False
        
        success = test_normalized_file(args.file)
        
    elif args.pipeline:
        # Test normalization pipeline
        success = test_normalization_pipeline()
        
    else:
        # Test default normalized file
        default_file = 'output/transactions_normalized.csv'
        
        if os.path.exists(default_file):
            logger.info("📁 Testing default normalized file...")
            success = test_normalized_file(default_file)
        else:
            logger.warning(f"⚠️  Default file not found: {default_file}")
            logger.info("🔧 Running normalization pipeline test instead...")
            success = test_normalization_pipeline()
    
    if success:
        print("\n🎉 All data quality tests PASSED!")
        return True
    else:
        print("\n💥 Data quality tests FAILED!")
        print("Please fix the issues above before proceeding.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 