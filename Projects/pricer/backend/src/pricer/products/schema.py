"""
Strict Pydantic schema for structured product term sheets.

Comprehensive validation for all term sheet fields with explicit types.
"""

from datetime import date
from enum import Enum
from typing import List, Optional, Union, Annotated
from pydantic import BaseModel, Field, field_validator, model_validator
import json
from pathlib import Path


# ============================================================================
# Enums for strict typing
# ============================================================================

class DayCountConvention(str, Enum):
    """Day count conventions."""
    ACT_360 = "ACT/360"
    ACT_365F = "ACT/365F"
    THIRTY_360 = "30/360"


class BusinessDayRule(str, Enum):
    """Business day adjustment rules."""
    FOLLOWING = "following"
    MODIFIED_FOLLOWING = "modified_following"
    PRECEDING = "preceding"
    UNADJUSTED = "unadjusted"


class Calendar(str, Enum):
    """Supported calendars."""
    WEEKENDS = "WE"          # Weekends only
    NYSE = "NYSE"            # NYSE trading days
    TARGET = "TARGET"        # Euro area
    LONDON = "LON"           # London


class DividendModelType(str, Enum):
    """Dividend model types."""
    CONTINUOUS = "continuous"
    DISCRETE = "discrete"
    MIXED = "mixed"


class VolModelType(str, Enum):
    """Volatility model types."""
    FLAT = "flat"
    PIECEWISE_CONSTANT = "piecewise_constant"


class BarrierMonitoringType(str, Enum):
    """Barrier monitoring types."""
    CONTINUOUS = "continuous"   # Brownian bridge between steps
    DISCRETE = "discrete"       # Only at observation dates


class SettlementType(str, Enum):
    """Settlement types."""
    CASH = "cash"
    PHYSICAL = "physical"


# ============================================================================
# Sub-schemas for nested structures
# ============================================================================

class DiscreteDividend(BaseModel):
    """A single discrete dividend."""
    ex_date: date
    amount: float = Field(..., gt=0, description="Dividend amount in currency")


class DividendModel(BaseModel):
    """Dividend model specification."""
    type: DividendModelType
    continuous_yield: Optional[float] = Field(
        default=None, ge=0, le=0.5,
        description="Continuous dividend yield (annualized)"
    )
    discrete_dividends: Optional[List[DiscreteDividend]] = Field(
        default=None,
        description="List of discrete dividends with ex-dates"
    )
    
    @model_validator(mode='after')
    def validate_dividend_model(self) -> 'DividendModel':
        """Validate dividend model has required fields for its type."""
        if self.type == DividendModelType.CONTINUOUS:
            if self.continuous_yield is None:
                raise ValueError("continuous_yield required for continuous dividend model")
        elif self.type == DividendModelType.DISCRETE:
            if not self.discrete_dividends:
                raise ValueError("discrete_dividends required for discrete dividend model")
        elif self.type == DividendModelType.MIXED:
            if self.continuous_yield is None:
                raise ValueError("continuous_yield required for mixed dividend model")
        return self


class VolTenor(BaseModel):
    """A volatility tenor point."""
    date: date
    vol: float = Field(..., gt=0, le=2.0, description="Volatility (e.g., 0.25 for 25%)")


class VolModel(BaseModel):
    """Volatility model specification."""
    type: VolModelType
    flat_vol: Optional[float] = Field(
        default=None, gt=0, le=2.0,
        description="Flat volatility for flat model"
    )
    term_structure: Optional[List[VolTenor]] = Field(
        default=None,
        description="Piecewise constant vol term structure"
    )
    
    @model_validator(mode='after')
    def validate_vol_model(self) -> 'VolModel':
        """Validate vol model has required fields for its type."""
        if self.type == VolModelType.FLAT:
            if self.flat_vol is None:
                raise ValueError("flat_vol required for flat vol model")
        elif self.type == VolModelType.PIECEWISE_CONSTANT:
            if not self.term_structure:
                raise ValueError("term_structure required for piecewise constant vol model")
        return self


class Underlying(BaseModel):
    """Underlying asset specification."""
    id: str = Field(..., min_length=1, description="Unique identifier (ticker)")
    spot: float = Field(..., gt=0, description="Current spot price")
    currency: str = Field(default="USD", min_length=3, max_length=3)
    dividend_model: DividendModel
    vol_model: VolModel


class DiscountCurve(BaseModel):
    """Discount curve specification."""
    type: str = Field(default="flat", pattern="^(flat|piecewise)$")
    flat_rate: Optional[float] = Field(
        default=None, ge=-0.1, le=0.5,
        description="Flat continuous rate"
    )
    tenors: Optional[List[tuple]] = Field(
        default=None,
        description="List of (date, rate) tuples for piecewise curve"
    )
    day_count: DayCountConvention = DayCountConvention.ACT_365F
    
    @model_validator(mode='after')
    def validate_curve(self) -> 'DiscountCurve':
        """Validate curve has required data."""
        if self.type == "flat":
            if self.flat_rate is None:
                raise ValueError("flat_rate required for flat curve")
        return self


class Conventions(BaseModel):
    """Convention specifications."""
    calendar: Calendar = Calendar.WEEKENDS
    business_day_rule: BusinessDayRule = BusinessDayRule.MODIFIED_FOLLOWING
    coupon_day_count: DayCountConvention = DayCountConvention.ACT_360
    discount_day_count: DayCountConvention = DayCountConvention.ACT_365F


class KnockInBarrier(BaseModel):
    """Knock-in barrier specification."""
    level: float = Field(..., gt=0, le=1.5, description="Barrier as fraction of initial (e.g., 0.6)")
    monitoring: BarrierMonitoringType = BarrierMonitoringType.CONTINUOUS
    
    @field_validator('level')
    @classmethod
    def validate_level(cls, v: float) -> float:
        """Validate barrier level is sensible."""
        if v <= 0 or v > 1.5:
            raise ValueError(f"Barrier level must be in (0, 1.5], got {v}")
        return v


class Correlation(BaseModel):
    """Correlation specification."""
    matrix: Optional[List[List[float]]] = Field(
        default=None,
        description="Full correlation matrix (row-major)"
    )
    pairwise: Optional[dict] = Field(
        default=None,
        description="Pairwise correlations like {'AAPL_GOOG': 0.6}"
    )


class Schedules(BaseModel):
    """All schedule data aligned by observation index."""
    observation_dates: List[date] = Field(
        ..., min_length=1,
        description="Observation dates for autocall/coupon checks"
    )
    payment_dates: List[date] = Field(
        ..., min_length=1,
        description="Payment dates aligned with observation dates"
    )
    autocall_levels: List[float] = Field(
        ..., min_length=1,
        description="Autocall barrier levels per observation (1.0 = 100%)"
    )
    coupon_barriers: List[float] = Field(
        ..., min_length=1,
        description="Coupon barrier levels per observation"
    )
    coupon_rates: List[float] = Field(
        ..., min_length=1,
        description="Coupon rates per observation (e.g., 0.02 = 2%)"
    )
    
    @model_validator(mode='after')
    def validate_alignment(self) -> 'Schedules':
        """Validate all arrays are aligned with observation dates."""
        n = len(self.observation_dates)
        if len(self.payment_dates) != n:
            raise ValueError(f"payment_dates length {len(self.payment_dates)} != observation_dates length {n}")
        if len(self.autocall_levels) != n:
            raise ValueError(f"autocall_levels length {len(self.autocall_levels)} != observation_dates length {n}")
        if len(self.coupon_barriers) != n:
            raise ValueError(f"coupon_barriers length {len(self.coupon_barriers)} != observation_dates length {n}")
        if len(self.coupon_rates) != n:
            raise ValueError(f"coupon_rates length {len(self.coupon_rates)} != observation_dates length {n}")
        
        # Validate ordering
        for i in range(1, n):
            if self.observation_dates[i] <= self.observation_dates[i-1]:
                raise ValueError(f"observation_dates must be strictly increasing")
        
        # Validate barrier levels
        for i, level in enumerate(self.autocall_levels):
            if level <= 0 or level > 2.0:
                raise ValueError(f"autocall_levels[{i}] = {level} out of range (0, 2.0]")
        for i, level in enumerate(self.coupon_barriers):
            if level <= 0 or level > 2.0:
                raise ValueError(f"coupon_barriers[{i}] = {level} out of range (0, 2.0]")
        
        return self


class Payoff(BaseModel):
    """Payoff rules."""
    worst_of: bool = Field(default=True, description="Use worst-of for multi-asset")
    coupon_memory: bool = Field(default=True, description="Enable coupon memory feature")
    settlement: SettlementType = SettlementType.CASH
    coupon_on_autocall: bool = Field(
        default=True,
        description="Pay coupon when autocall triggers"
    )
    redemption_if_autocall: float = Field(
        default=1.0, gt=0, le=2.0,
        description="Redemption amount on autocall (fraction of notional)"
    )
    redemption_if_no_ki: float = Field(
        default=1.0, gt=0, le=2.0,
        description="Maturity redemption if no KI occurred"
    )
    redemption_if_ki: str = Field(
        default="worst_performance",
        pattern="^(worst_performance|fixed|floored)$",
        description="Maturity redemption rule if KI occurred"
    )
    ki_redemption_floor: Optional[float] = Field(
        default=None, ge=0, le=1.0,
        description="Floor for KI redemption (e.g., 0.0 for no floor)"
    )


class Meta(BaseModel):
    """Trade metadata."""
    product_id: str = Field(..., min_length=1)
    trade_date: date
    valuation_date: date
    settlement_date: date
    maturity_date: date
    maturity_payment_date: date
    currency: str = Field(default="USD", min_length=3, max_length=3)
    notional: float = Field(..., gt=0)
    
    @model_validator(mode='after')
    def validate_dates(self) -> 'Meta':
        """Validate date ordering."""
        if self.valuation_date < self.trade_date:
            raise ValueError("valuation_date cannot be before trade_date")
        if self.maturity_date < self.valuation_date:
            raise ValueError("maturity_date cannot be before valuation_date")
        if self.maturity_payment_date < self.maturity_date:
            raise ValueError("maturity_payment_date cannot be before maturity_date")
        return self


# ============================================================================
# Main Term Sheet Schema
# ============================================================================

class TermSheet(BaseModel):
    """
    Complete term sheet for an autocallable structured product.
    
    This is the single source of truth for product specification.
    All fields are validated for consistency and alignment.
    """
    
    meta: Meta
    underlyings: List[Underlying] = Field(..., min_length=1)
    conventions: Conventions = Field(default_factory=Conventions)
    discount_curve: DiscountCurve
    correlation: Optional[Correlation] = None
    schedules: Schedules
    ki_barrier: Optional[KnockInBarrier] = None
    payoff: Payoff = Field(default_factory=Payoff)
    
    @model_validator(mode='after')
    def validate_term_sheet(self) -> 'TermSheet':
        """Cross-field validation."""
        # Validate schedules are within product life
        for obs_date in self.schedules.observation_dates:
            if obs_date > self.meta.maturity_date:
                raise ValueError(f"observation_date {obs_date} is after maturity_date")
            if obs_date < self.meta.valuation_date:
                raise ValueError(f"observation_date {obs_date} is before valuation_date")
        
        # Validate correlation if multi-asset
        n_underlyings = len(self.underlyings)
        if n_underlyings > 1:
            if self.correlation is None:
                raise ValueError("correlation required for multi-asset products")
            if self.correlation.matrix is not None:
                if len(self.correlation.matrix) != n_underlyings:
                    raise ValueError(f"correlation matrix size {len(self.correlation.matrix)} != {n_underlyings} underlyings")
        
        return self
    
    class Config:
        """Pydantic configuration."""
        extra = "forbid"


# ============================================================================
# Loading and validation functions
# ============================================================================

def load_term_sheet(path: Union[str, Path]) -> TermSheet:
    """
    Load and validate a term sheet from JSON file.
    
    Args:
        path: Path to JSON file
        
    Returns:
        Validated TermSheet object
        
    Raises:
        FileNotFoundError: If file doesn't exist
        ValidationError: If JSON doesn't match schema
    """
    filepath = Path(path)
    if not filepath.exists():
        raise FileNotFoundError(f"Term sheet not found: {path}")
    
    with open(filepath, "r") as f:
        data = json.load(f)
    
    return TermSheet(**data)


def validate_term_sheet_json(data: dict) -> TermSheet:
    """
    Validate term sheet data dictionary.
    
    Args:
        data: Raw JSON data as dictionary
        
    Returns:
        Validated TermSheet object
    """
    return TermSheet(**data)


def print_term_sheet_summary(ts: TermSheet) -> None:
    """Print a clean summary of the term sheet."""
    print("=" * 70)
    print(f"TERM SHEET SUMMARY: {ts.meta.product_id}")
    print("=" * 70)
    
    print(f"\n--- META ---")
    print(f"  Trade Date:      {ts.meta.trade_date}")
    print(f"  Valuation Date:  {ts.meta.valuation_date}")
    print(f"  Maturity Date:   {ts.meta.maturity_date}")
    print(f"  Notional:        {ts.meta.currency} {ts.meta.notional:,.0f}")
    
    print(f"\n--- UNDERLYINGS ({len(ts.underlyings)}) ---")
    for u in ts.underlyings:
        vol_str = f"{u.vol_model.flat_vol:.1%}" if u.vol_model.flat_vol else "term structure"
        div_str = f"{u.dividend_model.continuous_yield:.2%}" if u.dividend_model.continuous_yield else "discrete"
        print(f"  {u.id}: Spot={u.spot:,.2f}, Vol={vol_str}, Div={div_str}")
    
    print(f"\n--- DISCOUNT CURVE ---")
    print(f"  Type: {ts.discount_curve.type}")
    if ts.discount_curve.flat_rate is not None:
        print(f"  Rate: {ts.discount_curve.flat_rate:.2%}")
    
    print(f"\n--- SCHEDULES ({len(ts.schedules.observation_dates)} observations) ---")
    print(f"  First Obs:  {ts.schedules.observation_dates[0]}")
    print(f"  Last Obs:   {ts.schedules.observation_dates[-1]}")
    print(f"  Autocall:   {min(ts.schedules.autocall_levels):.0%} - {max(ts.schedules.autocall_levels):.0%}")
    print(f"  Coupon:     {min(ts.schedules.coupon_barriers):.0%} barrier, {ts.schedules.coupon_rates[0]:.1%}/period")
    
    if ts.ki_barrier:
        print(f"\n--- KNOCK-IN BARRIER ---")
        print(f"  Level:      {ts.ki_barrier.level:.0%}")
        print(f"  Monitoring: {ts.ki_barrier.monitoring.value}")
    
    print(f"\n--- PAYOFF ---")
    print(f"  Worst-of:   {ts.payoff.worst_of}")
    print(f"  Memory:     {ts.payoff.coupon_memory}")
    print(f"  Settlement: {ts.payoff.settlement.value}")
    
    if ts.correlation and len(ts.underlyings) > 1:
        print(f"\n--- CORRELATION ---")
        if ts.correlation.pairwise:
            for pair, corr in ts.correlation.pairwise.items():
                print(f"  {pair}: {corr:.2f}")
    
    print("=" * 70)
    print("VALIDATION: PASSED")
    print("=" * 70)
