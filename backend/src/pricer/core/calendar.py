"""
Business day calendars and date adjustment conventions.

Supports Following and Modified Following business day conventions.
"""

from datetime import date, timedelta
from enum import Enum
from typing import Set, Optional
from functools import lru_cache


class BusinessDayConvention(str, Enum):
    """Business day adjustment conventions."""
    
    UNADJUSTED = "UNADJUSTED"
    FOLLOWING = "FOLLOWING"
    MODIFIED_FOLLOWING = "MODIFIED_FOLLOWING"
    PRECEDING = "PRECEDING"


class Calendar:
    """
    Business day calendar with holiday support.
    
    Provides methods to check business days and adjust dates.
    """
    
    def __init__(
        self,
        name: str = "WE",  # Weekend-only calendar
        holidays: Optional[Set[date]] = None
    ) -> None:
        """
        Initialize calendar.
        
        Args:
            name: Calendar identifier (e.g., "WE", "NYSE", "TARGET")
            holidays: Set of holiday dates (excluding weekends)
        """
        self.name = name
        self._holidays: Set[date] = holidays or set()
    
    def is_business_day(self, d: date) -> bool:
        """Check if a date is a business day."""
        # Weekend check (Saturday=5, Sunday=6)
        if d.weekday() >= 5:
            return False
        # Holiday check
        if d in self._holidays:
            return False
        return True
    
    def add_business_days(self, d: date, days: int) -> date:
        """Add business days to a date."""
        if days == 0:
            return d
        
        step = 1 if days > 0 else -1
        remaining = abs(days)
        current = d
        
        while remaining > 0:
            current += timedelta(days=step)
            if self.is_business_day(current):
                remaining -= 1
        
        return current
    
    def next_business_day(self, d: date) -> date:
        """Get the next business day on or after the given date."""
        current = d
        while not self.is_business_day(current):
            current += timedelta(days=1)
        return current
    
    def prev_business_day(self, d: date) -> date:
        """Get the previous business day on or before the given date."""
        current = d
        while not self.is_business_day(current):
            current -= timedelta(days=1)
        return current
    
    def add_holidays(self, holidays: Set[date]) -> None:
        """Add holidays to the calendar."""
        self._holidays.update(holidays)


# Default weekend-only calendar
DEFAULT_CALENDAR = Calendar("WE")


def adjust_date(
    d: date,
    convention: BusinessDayConvention,
    calendar: Optional[Calendar] = None
) -> date:
    """
    Adjust a date according to a business day convention.
    
    Args:
        d: Date to adjust
        convention: Business day convention
        calendar: Calendar to use (defaults to weekend-only)
        
    Returns:
        Adjusted date
    """
    cal = calendar or DEFAULT_CALENDAR
    
    if convention == BusinessDayConvention.UNADJUSTED:
        return d
    
    elif convention == BusinessDayConvention.FOLLOWING:
        return cal.next_business_day(d)
    
    elif convention == BusinessDayConvention.PRECEDING:
        return cal.prev_business_day(d)
    
    elif convention == BusinessDayConvention.MODIFIED_FOLLOWING:
        adjusted = cal.next_business_day(d)
        # If adjusted date is in a different month, go backwards instead
        if adjusted.month != d.month:
            adjusted = cal.prev_business_day(d)
        return adjusted
    
    else:
        raise ValueError(f"Unknown business day convention: {convention}")


def business_days_between(
    start: date,
    end: date,
    calendar: Optional[Calendar] = None
) -> int:
    """Count business days between two dates (exclusive of start, inclusive of end)."""
    cal = calendar or DEFAULT_CALENDAR
    
    if end <= start:
        return 0
    
    count = 0
    current = start + timedelta(days=1)
    while current <= end:
        if cal.is_business_day(current):
            count += 1
        current += timedelta(days=1)
    
    return count
