"""Product definitions: Term sheet schema and autocallable structures."""

from pricer.products.schema import (
    TermSheet,
    load_term_sheet,
    validate_term_sheet_json,
    print_term_sheet_summary,
    Meta,
    Underlying,
    Schedules,
    Payoff,
    KnockInBarrier,
    DividendModel,
    VolModel,
    DiscountCurve,
    Conventions,
    Correlation,
)

__all__ = [
    "TermSheet",
    "load_term_sheet",
    "validate_term_sheet_json",
    "print_term_sheet_summary",
    "Meta",
    "Underlying",
    "Schedules",
    "Payoff",
    "KnockInBarrier",
    "DividendModel",
    "VolModel",
    "DiscountCurve",
    "Conventions",
    "Correlation",
]
