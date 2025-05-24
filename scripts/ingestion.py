"""
Root-level ingestion module for backward compatibility.
This module re-exports functions from app.ingestion for tests.
"""

from app.ingestion.loader import ingest_csv

__all__ = ['ingest_csv'] 