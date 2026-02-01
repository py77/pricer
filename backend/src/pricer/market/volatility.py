"""
Volatility surfaces and term structures.

Supports piecewise constant vol by tenor buckets.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import List, Tuple, Optional
import math

from pricer.core.day_count import DayCountConvention, day_count_fraction


class VolatilitySurface(ABC):
    """Abstract base class for volatility surfaces."""
    
    @abstractmethod
    def get_vol(self, reference_date: date, expiry: date, strike: Optional[float] = None) -> float:
        """
        Get implied volatility for a given expiry and strike.
        
        Args:
            reference_date: Valuation date
            expiry: Option expiry date
            strike: Strike level (optional, for smile)
            
        Returns:
            Implied volatility (annualized)
        """
        pass
    
    def get_variance(self, reference_date: date, expiry: date, strike: Optional[float] = None) -> float:
        """Get total variance to expiry."""
        vol = self.get_vol(reference_date, expiry, strike)
        yf = day_count_fraction(reference_date, expiry, DayCountConvention.ACT_365F)
        return vol * vol * yf
    
    def get_forward_vol(
        self,
        reference_date: date,
        start: date,
        end: date,
        strike: Optional[float] = None
    ) -> float:
        """Get forward volatility between two future dates."""
        var_start = self.get_variance(reference_date, start, strike)
        var_end = self.get_variance(reference_date, end, strike)
        
        yf = day_count_fraction(start, end, DayCountConvention.ACT_365F)
        if yf <= 0:
            return self.get_vol(reference_date, end, strike)
        
        forward_var = var_end - var_start
        if forward_var < 0:
            # Should not happen with proper calibration
            forward_var = 0.0
        
        return math.sqrt(forward_var / yf)


@dataclass
class FlatVolatility(VolatilitySurface):
    """Flat volatility surface (constant vol for all strikes and expiries)."""
    
    vol: float
    
    def get_vol(self, reference_date: date, expiry: date, strike: Optional[float] = None) -> float:
        """Return flat volatility."""
        return self.vol


@dataclass
class PiecewiseConstantVol(VolatilitySurface):
    """
    Piecewise constant volatility term structure.
    
    Vol is constant within each tenor bucket, with step changes at bucket boundaries.
    This is ATM vol only (no smile).
    
    Attributes:
        tenors: List of (date, vol) tuples, sorted by date
            The vol applies from the previous date to this date
    """
    
    tenors: List[Tuple[date, float]] = field(default_factory=list)
    
    def __post_init__(self) -> None:
        """Sort tenors by date."""
        self.tenors = sorted(self.tenors, key=lambda x: x[0])
    
    def _get_vol_at(self, reference_date: date, target_date: date) -> float:
        """Get the vol applicable at a target date."""
        if not self.tenors:
            raise ValueError("No volatility tenors defined")
        
        # For dates at or before first tenor, use first vol
        if target_date <= self.tenors[0][0]:
            return self.tenors[0][1]
        
        # Find the applicable tenor bucket
        for i in range(len(self.tenors)):
            if target_date <= self.tenors[i][0]:
                return self.tenors[i][1]
        
        # After last tenor, use last vol (flat extrapolation)
        return self.tenors[-1][1]
    
    def get_vol(self, reference_date: date, expiry: date, strike: Optional[float] = None) -> float:
        """
        Get implied volatility at expiry.
        
        For piecewise constant vol, this returns the effective average vol to expiry,
        preserving total variance.
        """
        if expiry <= reference_date:
            return self._get_vol_at(reference_date, reference_date)
        
        # Calculate total variance by integrating over segments
        total_variance = 0.0
        current = reference_date
        
        # Get all breakpoints between reference_date and expiry
        breakpoints = [reference_date]
        for tenor_date, _ in self.tenors:
            if reference_date < tenor_date < expiry:
                breakpoints.append(tenor_date)
        breakpoints.append(expiry)
        
        for i in range(len(breakpoints) - 1):
            seg_start = breakpoints[i]
            seg_end = breakpoints[i + 1]
            vol = self._get_vol_at(reference_date, seg_end)
            yf = day_count_fraction(seg_start, seg_end, DayCountConvention.ACT_365F)
            total_variance += vol * vol * yf
        
        total_yf = day_count_fraction(reference_date, expiry, DayCountConvention.ACT_365F)
        if total_yf <= 0:
            return self._get_vol_at(reference_date, expiry)
        
        return math.sqrt(total_variance / total_yf)
    
    def get_instantaneous_vol(self, reference_date: date, target_date: date) -> float:
        """Get the instantaneous (local) vol at a specific date."""
        return self._get_vol_at(reference_date, target_date)
