"""
Interest rate curves for discounting.

Supports flat and piecewise constant rate curves.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import List, Tuple
import math

from pricer.core.day_count import DayCountConvention, day_count_fraction


class RateCurve(ABC):
    """Abstract base class for interest rate curves."""
    
    @abstractmethod
    def discount_factor(self, from_date: date, to_date: date) -> float:
        """Calculate discount factor from one date to another."""
        pass
    
    @abstractmethod
    def zero_rate(self, from_date: date, to_date: date) -> float:
        """Calculate continuously compounded zero rate."""
        pass
    
    def forward_rate(
        self,
        from_date: date,
        start: date,
        end: date
    ) -> float:
        """Calculate forward rate between two future dates."""
        df_start = self.discount_factor(from_date, start)
        df_end = self.discount_factor(from_date, end)
        
        if df_end <= 0 or df_start <= 0:
            raise ValueError("Discount factors must be positive")
        
        yf = day_count_fraction(start, end, DayCountConvention.ACT_365F)
        if yf <= 0:
            return 0.0
        
        return math.log(df_start / df_end) / yf


@dataclass
class FlatRateCurve(RateCurve):
    """
    Flat interest rate curve (constant rate for all tenors).
    
    Attributes:
        rate: Continuously compounded rate
        day_count: Day count convention for rate calculation
    """
    
    rate: float
    day_count: DayCountConvention = DayCountConvention.ACT_365F
    
    def discount_factor(self, from_date: date, to_date: date) -> float:
        """Calculate discount factor."""
        if to_date < from_date:
            raise ValueError(f"to_date {to_date} must be >= from_date {from_date}")
        
        yf = day_count_fraction(from_date, to_date, self.day_count)
        return math.exp(-self.rate * yf)
    
    def zero_rate(self, from_date: date, to_date: date) -> float:
        """Return the flat rate."""
        return self.rate


@dataclass
class PiecewiseConstantRateCurve(RateCurve):
    """
    Piecewise constant rate curve.
    
    Rate is constant between tenor points, with step changes at each tenor.
    
    Attributes:
        reference_date: Curve reference date
        tenors: List of (date, rate) tuples, sorted by date
        day_count: Day count convention
    """
    
    reference_date: date
    tenors: List[Tuple[date, float]] = field(default_factory=list)
    day_count: DayCountConvention = DayCountConvention.ACT_365F
    
    def __post_init__(self) -> None:
        """Sort tenors by date."""
        self.tenors = sorted(self.tenors, key=lambda x: x[0])
    
    def _get_rate_at(self, target_date: date) -> float:
        """Get the rate applicable at a target date."""
        if not self.tenors:
            return 0.0
        
        # Before first tenor, use first rate
        if target_date <= self.tenors[0][0]:
            return self.tenors[0][1]
        
        # After last tenor, use last rate
        if target_date >= self.tenors[-1][0]:
            return self.tenors[-1][1]
        
        # Find applicable tenor bucket
        for i in range(len(self.tenors) - 1):
            if target_date < self.tenors[i + 1][0]:
                return self.tenors[i][1]
        
        return self.tenors[-1][1]
    
    def discount_factor(self, from_date: date, to_date: date) -> float:
        """
        Calculate discount factor with piecewise integration.
        
        Integrates the rate over each constant segment.
        """
        if to_date < from_date:
            raise ValueError(f"to_date {to_date} must be >= from_date {from_date}")
        
        if to_date == from_date:
            return 1.0
        
        # Simple integration over rate segments
        total_log_df = 0.0
        current = from_date
        
        # Get all breakpoints between from_date and to_date
        breakpoints = [from_date]
        for tenor_date, _ in self.tenors:
            if from_date < tenor_date < to_date:
                breakpoints.append(tenor_date)
        breakpoints.append(to_date)
        
        for i in range(len(breakpoints) - 1):
            seg_start = breakpoints[i]
            seg_end = breakpoints[i + 1]
            rate = self._get_rate_at(seg_start)
            yf = day_count_fraction(seg_start, seg_end, self.day_count)
            total_log_df += rate * yf
        
        return math.exp(-total_log_df)
    
    def zero_rate(self, from_date: date, to_date: date) -> float:
        """Calculate effective zero rate."""
        if to_date <= from_date:
            return self._get_rate_at(from_date)
        
        df = self.discount_factor(from_date, to_date)
        yf = day_count_fraction(from_date, to_date, self.day_count)
        
        if yf <= 0:
            return 0.0
        
        return -math.log(df) / yf
