"""
Root-level analytics module for backward compatibility.
This module re-exports functions from app.analytics for tests.
"""

from app.analytics.portfolio import calculate_cost_basis_fifo, calculate_cost_basis_avg

__all__ = ['calculate_cost_basis_fifo', 'calculate_cost_basis_avg'] 