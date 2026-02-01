"""
Reporting module for structured products pricer.

Provides:
- CashflowReport: Table of expected cashflows with PV contributions
- PricingSummary: Aggregated pricing statistics
- PVDecomposition: Breakdown of coupon vs redemption PV
"""

from pricer.reporting.cashflow_report import (
    CashflowReport,
    CashflowEntry,
    PricingSummary,
    PathStatistics,
    generate_cashflow_report,
)
from pricer.reporting.decomposition import (
    PVDecomposition,
    compute_pv_decomposition,
)

__all__ = [
    "CashflowReport",
    "CashflowEntry",
    "PricingSummary",
    "PathStatistics",
    "PVDecomposition",
    "generate_cashflow_report",
    "compute_pv_decomposition",
]
