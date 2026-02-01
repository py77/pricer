"""
Schedule generation for structured products.

Generates observation, coupon, and settlement schedules.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import List, Optional
from enum import Enum

from pricer.core.calendar import Calendar, BusinessDayConvention, adjust_date, DEFAULT_CALENDAR


class Frequency(str, Enum):
    """Schedule frequency."""
    
    ANNUAL = "ANNUAL"
    SEMI_ANNUAL = "SEMI_ANNUAL"
    QUARTERLY = "QUARTERLY"
    MONTHLY = "MONTHLY"
    WEEKLY = "WEEKLY"
    DAILY = "DAILY"


def _months_for_frequency(freq: Frequency) -> int:
    """Get number of months per period for a frequency."""
    mapping = {
        Frequency.ANNUAL: 12,
        Frequency.SEMI_ANNUAL: 6,
        Frequency.QUARTERLY: 3,
        Frequency.MONTHLY: 1,
    }
    if freq not in mapping:
        raise ValueError(f"Frequency {freq} not supported for month-based schedules")
    return mapping[freq]


def _add_months(d: date, months: int) -> date:
    """Add months to a date, handling end-of-month."""
    year = d.year + (d.month + months - 1) // 12
    month = (d.month + months - 1) % 12 + 1
    
    # Handle end-of-month
    import calendar
    max_day = calendar.monthrange(year, month)[1]
    day = min(d.day, max_day)
    
    return date(year, month, day)


@dataclass
class ScheduleDate:
    """A single date in a schedule with associated metadata."""
    
    unadjusted_date: date
    adjusted_date: date
    period_start: Optional[date] = None
    period_end: Optional[date] = None


@dataclass
class Schedule:
    """
    A schedule of dates for a structured product.
    
    Used for observation dates, coupon dates, settlement dates, etc.
    """
    
    dates: List[ScheduleDate] = field(default_factory=list)
    
    def __len__(self) -> int:
        return len(self.dates)
    
    def __iter__(self):
        return iter(self.dates)
    
    def __getitem__(self, idx: int) -> ScheduleDate:
        return self.dates[idx]
    
    @property
    def adjusted_dates(self) -> List[date]:
        """Get list of adjusted dates."""
        return [d.adjusted_date for d in self.dates]
    
    @property
    def unadjusted_dates(self) -> List[date]:
        """Get list of unadjusted dates."""
        return [d.unadjusted_date for d in self.dates]


def generate_schedule(
    start_date: date,
    end_date: date,
    frequency: Frequency,
    convention: BusinessDayConvention = BusinessDayConvention.MODIFIED_FOLLOWING,
    calendar: Optional[Calendar] = None,
    stub_at_end: bool = True,
    include_start: bool = False,
    include_end: bool = True
) -> Schedule:
    """
    Generate a schedule of dates between start and end.
    
    Args:
        start_date: Schedule start date
        end_date: Schedule end date
        frequency: Frequency of dates
        convention: Business day adjustment convention
        calendar: Business day calendar
        stub_at_end: If True, short stub period at end; else at start
        include_start: Include start date in schedule
        include_end: Include end date in schedule
        
    Returns:
        Schedule of dates
    """
    cal = calendar or DEFAULT_CALENDAR
    dates: List[ScheduleDate] = []
    
    if frequency == Frequency.DAILY:
        current = start_date
        while current <= end_date:
            if include_start or current != start_date:
                if include_end or current != end_date:
                    adjusted = adjust_date(current, convention, cal)
                    dates.append(ScheduleDate(
                        unadjusted_date=current,
                        adjusted_date=adjusted
                    ))
            current += timedelta(days=1)
    
    elif frequency == Frequency.WEEKLY:
        current = start_date
        while current <= end_date:
            if include_start or current != start_date:
                if include_end or current != end_date:
                    adjusted = adjust_date(current, convention, cal)
                    dates.append(ScheduleDate(
                        unadjusted_date=current,
                        adjusted_date=adjusted
                    ))
            current += timedelta(weeks=1)
    
    else:
        # Month-based frequencies
        months = _months_for_frequency(frequency)
        
        if stub_at_end:
            # Roll forward from start
            current = start_date
            period_num = 0
            while current <= end_date:
                if include_start or period_num > 0:
                    adjusted = adjust_date(current, convention, cal)
                    dates.append(ScheduleDate(
                        unadjusted_date=current,
                        adjusted_date=adjusted
                    ))
                current = _add_months(start_date, (period_num + 1) * months)
                period_num += 1
            
            # Add end date if needed and not already included
            if include_end and (not dates or dates[-1].unadjusted_date != end_date):
                if end_date > start_date:
                    adjusted = adjust_date(end_date, convention, cal)
                    dates.append(ScheduleDate(
                        unadjusted_date=end_date,
                        adjusted_date=adjusted
                    ))
        else:
            # Roll backward from end
            temp_dates: List[date] = []
            current = end_date
            while current >= start_date:
                temp_dates.append(current)
                current = _add_months(end_date, -len(temp_dates) * months)
            
            temp_dates.reverse()
            
            for d in temp_dates:
                if (include_start or d != start_date) and (include_end or d != end_date):
                    adjusted = adjust_date(d, convention, cal)
                    dates.append(ScheduleDate(
                        unadjusted_date=d,
                        adjusted_date=adjusted
                    ))
    
    # Add period start/end for accrual calculations
    for i, sched_date in enumerate(dates):
        if i == 0:
            sched_date.period_start = adjust_date(start_date, convention, cal)
        else:
            sched_date.period_start = dates[i - 1].adjusted_date
        sched_date.period_end = sched_date.adjusted_date
    
    return Schedule(dates=dates)


def generate_explicit_schedule(
    explicit_dates: List[date],
    convention: BusinessDayConvention = BusinessDayConvention.MODIFIED_FOLLOWING,
    calendar: Optional[Calendar] = None
) -> Schedule:
    """
    Generate a schedule from explicit dates.
    
    Args:
        explicit_dates: List of unadjusted dates
        convention: Business day adjustment convention
        calendar: Business day calendar
        
    Returns:
        Schedule of dates
    """
    cal = calendar or DEFAULT_CALENDAR
    dates: List[ScheduleDate] = []
    
    sorted_dates = sorted(explicit_dates)
    
    for i, d in enumerate(sorted_dates):
        adjusted = adjust_date(d, convention, cal)
        period_start = dates[i - 1].adjusted_date if i > 0 else adjusted
        dates.append(ScheduleDate(
            unadjusted_date=d,
            adjusted_date=adjusted,
            period_start=period_start,
            period_end=adjusted
        ))
    
    return Schedule(dates=dates)
