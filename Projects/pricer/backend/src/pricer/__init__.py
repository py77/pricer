"""
Pricer: A production-grade structured products pricing library.

Supports Autocallables, Phoenix notes, and other barrier-based structured products.
"""

from pricer.products.schema import (
    TermSheet,
    load_term_sheet,
    validate_term_sheet_json,
    print_term_sheet_summary,
)
from pricer.engines.base import PricingResult

__version__ = "0.1.0"

__all__ = [
    "TermSheet",
    "load_term_sheet",
    "validate_term_sheet_json",
    "print_term_sheet_summary",
    "PricingResult",
]
