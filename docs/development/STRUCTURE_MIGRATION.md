# Project Structure Migration Guide

This document outlines the reorganization of the Portfolio Analytics project structure implemented to improve maintainability and organization.

## 🎯 Migration Overview

**Date**: January 2025  
**Version**: 2.0 → 2.1  
**Impact**: File locations changed, but functionality remains the same

## 📁 What Changed

### Documentation Reorganization
All documentation has been moved from the root directory to organized subdirectories:

| Old Location | New Location | Purpose |
|--------------|--------------|---------|
| `DASHBOARD_COMPLETION_SUMMARY.md` | `docs/project-management/` | Project status |
| `DASHBOARD_IMPROVEMENTS.md` | `docs/project-management/` | Enhancement details |
| `PERFORMANCE_SUMMARY.md` | `docs/project-management/` | Performance metrics |
| `MIGRATION_SUMMARY.md` | `docs/project-management/` | Database migration docs |
| `FEATURE_ROADMAP.md` | `docs/project-management/` | Feature roadmap |
| `NEXT_STEPS_ROADMAP.md` | `docs/project-management/` | Development phases |
| `DEPLOYMENT_GUIDE.md` | `docs/development/` | Deployment instructions |
| `FINAL_CHECKLIST.md` | `docs/development/` | Production checklist |

### Data File Organization
Data files have been moved to organized subdirectories:

| Old Location | New Location | Purpose |
|--------------|--------------|---------|
| `portfolio.db` | `data/databases/` | Main database |
| `schema.sql` | `data/databases/` | Database schema |
| `temp_combined_transactions_before_norm.csv` | `data/temp/` | Temporary files |

### Script Consolidation
Legacy Python scripts moved to scripts directory:

| Old Location | New Location | Status |
|--------------|--------------|--------|
| `analytics.py` | `scripts/analytics.py` | Legacy wrapper |
| `ingestion.py` | `scripts/ingestion.py` | Legacy wrapper |
| `normalization.py` | `scripts/normalization.py` | Legacy wrapper |
| `transfers.py` | `scripts/transfers.py` | Legacy wrapper |
| `migration.py` | `scripts/migration.py` | Active script |
| `visualize_prices.py` | `scripts/visualize_prices.py` | Utility script |

### Test Organization
Test files moved to proper test directory:

| Old Location | New Location | Purpose |
|--------------|--------------|---------|
| `test_portfolio_simple.py` | `tests/test_portfolio_simple.py` | Portfolio tests |
| `test_portfolio_returns_with_real_data.py` | `tests/test_portfolio_returns_with_real_data.py` | Integration tests |

### Notebook Organization
Jupyter notebooks moved to dedicated directory:

| Old Location | New Location | Purpose |
|--------------|--------------|---------|
| `coinbase_transfer.ipynb` | `notebooks/coinbase_transfer.ipynb` | Analysis notebook |

### Project Management
Project setup files moved to dedicated directory:

| Old Location | New Location | Purpose |
|--------------|--------------|---------|
| `setup.sh` | `project/setup.sh` | Environment setup |

## 🔄 Updated Commands

### Database Migration
```bash
# Old command
python migration.py

# New command
python scripts/migration.py
```

### Dashboard Launch
```bash
# Enhanced dashboard (recommended)
PYTHONPATH=$(pwd) streamlit run ui/streamlit_app_v2.py --server.port 8502

# Legacy dashboard
streamlit run ui/streamlit_app.py
```

### Testing
```bash
# Full test suite
python -m pytest tests/ -v

# Portfolio-specific tests
python tests/test_portfolio_simple.py
python tests/test_portfolio_returns_with_real_data.py
```

### Benchmarking
```bash
python scripts/simple_benchmark.py
python scripts/demo_dashboard.py
```

## 📂 New Directory Structure

```
portfolio_analytics/
├── 📚 docs/                    # All documentation
│   ├── README.md              # Documentation index
│   ├── architecture/          # Technical docs
│   ├── development/           # Dev guides
│   ├── project-management/    # Status & roadmaps
│   └── user-guides/           # User documentation
│
├── 🗃️ data/                    # All data files
│   ├── databases/             # Database files
│   ├── temp/                  # Temporary files
│   ├── exports/               # Generated exports
│   ├── historical_price_data/ # Price data CSVs
│   └── transaction_history/   # Input CSVs
│
├── 🧪 tests/                   # All test files
│   ├── unit/                  # Unit tests
│   ├── integration/           # Integration tests
│   ├── fixtures/              # Test data
│   └── test_portfolio_*.py    # Portfolio tests
│
├── 🔧 scripts/                 # Utility scripts
│   ├── migration.py           # Database migration
│   ├── benchmark_*.py         # Performance tests
│   └── legacy scripts...      # Legacy wrappers
│
├── 📓 notebooks/               # Jupyter notebooks
├── 📋 project/                 # Project management
└── [existing directories...]   # app/, ui/, config/, etc.
```

## ⚠️ Breaking Changes

### File Path Updates Required
If you have any custom scripts or bookmarks that reference the old file locations, update them:

1. **Documentation links** - Update any references to moved `.md` files
2. **Database paths** - Update any hardcoded paths to `portfolio.db`
3. **Script imports** - Update any imports of moved Python files
4. **Test commands** - Use new test file locations

### Environment Variables
No environment variable changes required.

### Database Schema
No database schema changes - only file location moved.

## 🔧 Migration Steps for Existing Users

1. **Pull the latest changes:**
   ```bash
   git pull origin main
   ```

2. **Update any custom scripts** that reference old file paths

3. **Update bookmarks** to documentation files

4. **Verify functionality:**
   ```bash
   # Test database migration
   python scripts/migration.py
   
   # Test dashboard
   PYTHONPATH=$(pwd) streamlit run ui/streamlit_app_v2.py --server.port 8502
   
   # Run tests
   python -m pytest tests/ -v
   ```

## 📋 Benefits of New Structure

### ✅ Improved Organization
- **Clear separation** of concerns (docs, data, tests, scripts)
- **Easier navigation** with logical grouping
- **Reduced clutter** in root directory

### ✅ Better Maintainability
- **Easier to find** relevant files
- **Clearer project structure** for new contributors
- **Better version control** with organized commits

### ✅ Enhanced Documentation
- **Centralized documentation** hub
- **Categorized by audience** (users, developers, managers)
- **Clear navigation** with index files

### ✅ Professional Standards
- **Industry best practices** for project organization
- **Scalable structure** for future growth
- **Clear separation** of production and development files

## 🆘 Troubleshooting

### Common Issues After Migration

1. **"File not found" errors:**
   - Check if you're using old file paths
   - Update commands to use new locations

2. **Import errors:**
   - Ensure PYTHONPATH is set correctly
   - Use `PYTHONPATH=$(pwd)` for relative imports

3. **Database connection issues:**
   - Database is now at `data/databases/portfolio.db`
   - Update any hardcoded paths in custom scripts

4. **Test failures:**
   - Tests are now in `tests/` directory
   - Use `python -m pytest tests/` to run all tests

### Getting Help

If you encounter issues after the migration:
1. Check this migration guide
2. Review the updated [README.md](../../README.md)
3. Check the [Documentation Hub](../README.md)
4. Open an issue with details about the problem

## 📈 Next Steps

This reorganization sets the foundation for:
- **Better documentation** with user guides and API docs
- **Improved testing** with organized test suites
- **Enhanced development** workflows
- **Professional deployment** practices

The project functionality remains exactly the same - only the organization has improved! 