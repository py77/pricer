"""
Day count conventions for interest rate calculations.

Supports: ACT/360, ACT/365F, 30/360
"""

from datetime import date
from enum import Enum
from typing import Tuple


class DayCountConvention(str, Enum):
    """Supported day count conventions."""
    
    ACT_360 = "ACT/360"
    ACT_365F = "ACT/365F"
    THIRTY_360 = "30/360"


def _actual_days(start: date, end: date) -> int:
    """Calculate actual number of days between two dates."""
    return (end - start).days


def _thirty_360_days(start: date, end: date) -> int:
    """
    Calculate days using 30/360 convention (ISDA).
    
    Each month is treated as having 30 days, year has 360 days.
    """
    d1, m1, y1 = start.day, start.month, start.year
    d2, m2, y2 = end.day, end.month, end.year
    
    # Adjust day-of-month per 30/360 ISDA rules
    if d1 == 31:
        d1 = 30
    if d2 == 31 and d1 >= 30:
        d2 = 30
    
    return 360 * (y2 - y1) + 30 * (m2 - m1) + (d2 - d1)


def day_count_fraction(
    start: date,
    end: date,
    convention: DayCountConvention
) -> float:
    """
    Calculate the year fraction between two dates.
    
    Args:
        start: Start date (exclusive for accrual)
        end: End date (inclusive for accrual)
        convention: Day count convention to use
        
    Returns:
        Year fraction as a float
        
    Examples:
        >>> from datetime import date
        >>> day_count_fraction(date(2024, 1, 1), date(2024, 7, 1), DayCountConvention.ACT_360)
        0.5055555555555555
    """
    if end < start:
        raise ValueError(f"End date {end} must be >= start date {start}")
    
    if end == start:
        return 0.0
    
    if convention == DayCountConvention.ACT_360:
        return _actual_days(start, end) / 360.0
    
    elif convention == DayCountConvention.ACT_365F:
        return _actual_days(start, end) / 365.0
    
    elif convention == DayCountConvention.THIRTY_360:
        return _thirty_360_days(start, end) / 360.0
    
    else:
        raise ValueError(f"Unknown day count convention: {convention}")


def year_fraction_to_days(
    year_fraction: float,
    convention: DayCountConvention
) -> int:
    """Convert a year fraction back to approximate days."""
    if convention == DayCountConvention.ACT_360:
        return int(round(year_fraction * 360))
    elif convention == DayCountConvention.ACT_365F:
        return int(round(year_fraction * 365))
    elif convention == DayCountConvention.THIRTY_360:
        return int(round(year_fraction * 360))
    else:
        raise ValueError(f"Unknown day count convention: {convention}")
