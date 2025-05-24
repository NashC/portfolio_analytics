"""
Root-level normalization module for backward compatibility.
This module re-exports functions from app.ingestion for tests.
"""

from app.ingestion.normalization import *

__all__ = ['normalize_transactions', 'standardize_transaction_types', 'clean_numeric_fields'] 