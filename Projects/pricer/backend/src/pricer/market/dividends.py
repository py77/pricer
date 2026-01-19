"""
Dividend models for equity underlyings.

Supports continuous dividend yield and discrete cash dividends.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import List, Tuple, Optional
import math

from pricer.core.day_count import DayCountConvention, day_count_fraction


class DividendModel(ABC):
    """Abstract base class for dividend models."""
    
    @abstractmethod
    def get_dividend_adjustment(
        self,
        reference_date: date,
        target_date: date,
        spot: float
    ) -> float:
        """
        Calculate the forward price adjustment factor for dividends.
        
        Returns:
            Multiplicative factor to apply to spot for forward calculation.
            For continuous yield: exp(-q * t)
            For discrete: product of (1 - D_i/S) factors
        """
        pass
    
    @abstractmethod
    def get_discrete_dividends_between(
        self,
        start_date: date,
        end_date: date
    ) -> List[Tuple[date, float]]:
        """Get list of discrete dividends between two dates."""
        pass


@dataclass
class ContinuousDividend(DividendModel):
    """
    Continuous dividend yield model.
    
    Attributes:
        yield_rate: Continuous dividend yield (annualized)
        day_count: Day count convention for yield calculation
    """
    
    yield_rate: float = 0.0
    day_count: DayCountConvention = DayCountConvention.ACT_365F
    
    def get_dividend_adjustment(
        self,
        reference_date: date,
        target_date: date,
        spot: float
    ) -> float:
        """Calculate exp(-q * t) adjustment."""
        if target_date <= reference_date:
            return 1.0
        
        yf = day_count_fraction(reference_date, target_date, self.day_count)
        return math.exp(-self.yield_rate * yf)
    
    def get_discrete_dividends_between(
        self,
        start_date: date,
        end_date: date
    ) -> List[Tuple[date, float]]:
        """Continuous yield has no discrete dividends."""
        return []


@dataclass
class DiscreteDividend(DividendModel):
    """
    Discrete cash dividend model.
    
    Supports a schedule of known future cash dividends with ex-dates.
    
    Attributes:
        dividends: List of (ex_date, amount) tuples
    """
    
    dividends: List[Tuple[date, float]] = field(default_factory=list)
    
    def __post_init__(self) -> None:
        """Sort dividends by date."""
        self.dividends = sorted(self.dividends, key=lambda x: x[0])
    
    def get_dividend_adjustment(
        self,
        reference_date: date,
        target_date: date,
        spot: float
    ) -> float:
        """
        Calculate forward adjustment for discrete dividends.
        
        Uses the multiplicative adjustment: prod(1 - D_i/S_i)
        where S_i is the forward spot at ex-date i.
        
        Note: This is a simplified model. A more accurate approach would
        use the full forward price including interest rate effects.
        """
        if target_date <= reference_date or spot <= 0:
            return 1.0
        
        adjustment = 1.0
        cumulative_div = 0.0
        
        for ex_date, amount in self.dividends:
            if reference_date < ex_date <= target_date:
                # Approximate forward spot at ex-date
                forward_spot = spot - cumulative_div
                if forward_spot > amount:
                    adjustment *= (forward_spot - amount) / forward_spot
                    cumulative_div += amount
        
        return adjustment
    
    def get_discrete_dividends_between(
        self,
        start_date: date,
        end_date: date
    ) -> List[Tuple[date, float]]:
        """Get dividends with ex-date between start and end."""
        return [
            (ex_date, amount)
            for ex_date, amount in self.dividends
            if start_date < ex_date <= end_date
        ]
    
    def get_total_dividends_between(
        self,
        start_date: date,
        end_date: date
    ) -> float:
        """Get total dividend amount between two dates."""
        return sum(
            amount
            for ex_date, amount in self.dividends
            if start_date < ex_date <= end_date
        )


@dataclass
class MixedDividend(DividendModel):
    """
    Mixed dividend model: continuous yield plus discrete dividends.
    
    Useful for modeling known near-term dividends with a yield for far future.
    
    Attributes:
        continuous_yield: Continuous dividend yield
        discrete_dividends: List of (ex_date, amount) tuples
        discrete_horizon: Date after which only continuous yield applies
    """
    
    continuous_yield: float = 0.0
    discrete_dividends: List[Tuple[date, float]] = field(default_factory=list)
    discrete_horizon: Optional[date] = None
    day_count: DayCountConvention = DayCountConvention.ACT_365F
    
    def __post_init__(self) -> None:
        """Sort dividends by date."""
        self.discrete_dividends = sorted(self.discrete_dividends, key=lambda x: x[0])
    
    def get_dividend_adjustment(
        self,
        reference_date: date,
        target_date: date,
        spot: float
    ) -> float:
        """Combined adjustment for discrete and continuous dividends."""
        if target_date <= reference_date:
            return 1.0
        
        adjustment = 1.0
        
        # Apply discrete dividends
        cumulative_div = 0.0
        for ex_date, amount in self.discrete_dividends:
            if reference_date < ex_date <= target_date:
                if self.discrete_horizon is None or ex_date <= self.discrete_horizon:
                    forward_spot = spot - cumulative_div
                    if forward_spot > amount:
                        adjustment *= (forward_spot - amount) / forward_spot
                        cumulative_div += amount
        
        # Apply continuous yield for period beyond discrete horizon
        if self.discrete_horizon is not None and target_date > self.discrete_horizon:
            start = max(reference_date, self.discrete_horizon)
            yf = day_count_fraction(start, target_date, self.day_count)
            adjustment *= math.exp(-self.continuous_yield * yf)
        elif self.discrete_horizon is None and self.continuous_yield > 0:
            # Apply continuous yield to entire period
            yf = day_count_fraction(reference_date, target_date, self.day_count)
            adjustment *= math.exp(-self.continuous_yield * yf)
        
        return adjustment
    
    def get_discrete_dividends_between(
        self,
        start_date: date,
        end_date: date
    ) -> List[Tuple[date, float]]:
        """Get discrete dividends between dates."""
        return [
            (ex_date, amount)
            for ex_date, amount in self.discrete_dividends
            if start_date < ex_date <= end_date
        ]
