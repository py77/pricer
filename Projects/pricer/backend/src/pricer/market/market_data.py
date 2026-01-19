"""
Aggregated market data container.

Bundles all market data required for pricing into a single object.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, Optional, Any, List
import math

from pricer.core.day_count import DayCountConvention, day_count_fraction
from pricer.market.rates import RateCurve, FlatRateCurve
from pricer.market.volatility import VolatilitySurface, FlatVolatility, PiecewiseConstantVol
from pricer.market.dividends import DividendModel, ContinuousDividend, DiscreteDividend
from pricer.market.correlation import CorrelationMatrix


@dataclass
class Underlying:
    """
    Market data for a single underlying asset.
    
    Attributes:
        ticker: Asset identifier
        spot: Current spot price
        vol_surface: Volatility surface/term structure
        dividend_model: Dividend model
        currency: Currency code (e.g., "USD", "EUR")
    """
    
    ticker: str
    spot: float
    vol_surface: VolatilitySurface
    dividend_model: DividendModel = field(default_factory=ContinuousDividend)
    currency: str = "USD"
    
    def get_forward(
        self,
        reference_date: date,
        target_date: date,
        rate_curve: RateCurve
    ) -> float:
        """Calculate forward price at target date."""
        if target_date <= reference_date:
            return self.spot
        
        # F = S * exp((r - q) * t) for continuous yield
        # Or F = S * exp(r*t) * div_adjustment for discrete divs
        
        df = rate_curve.discount_factor(reference_date, target_date)
        div_adj = self.dividend_model.get_dividend_adjustment(
            reference_date, target_date, self.spot
        )
        
        return self.spot * div_adj / df


@dataclass
class MarketData:
    """
    Complete market data for pricing.
    
    Aggregates all market observables: spots, vols, rates, dividends, correlations.
    
    Attributes:
        valuation_date: Pricing date
        underlyings: Dict of underlying assets by ticker
        rate_curve: Interest rate curve for discounting
        correlation: Correlation matrix for multi-asset
    """
    
    valuation_date: date
    underlyings: Dict[str, Underlying] = field(default_factory=dict)
    rate_curve: RateCurve = field(default_factory=lambda: FlatRateCurve(rate=0.05))
    correlation: Optional[CorrelationMatrix] = None
    
    def __post_init__(self) -> None:
        """Initialize correlation matrix if not provided."""
        if self.correlation is None and self.underlyings:
            assets = list(self.underlyings.keys())
            self.correlation = CorrelationMatrix.identity(assets)
    
    def get_spot(self, ticker: str) -> float:
        """Get spot price for an underlying."""
        if ticker not in self.underlyings:
            raise KeyError(f"Unknown underlying: {ticker}")
        return self.underlyings[ticker].spot
    
    def get_spots(self, tickers: List[str]) -> Dict[str, float]:
        """Get spots for multiple underlyings."""
        return {ticker: self.get_spot(ticker) for ticker in tickers}
    
    def get_vol(
        self,
        ticker: str,
        expiry: date,
        strike: Optional[float] = None
    ) -> float:
        """Get implied volatility for an underlying."""
        if ticker not in self.underlyings:
            raise KeyError(f"Unknown underlying: {ticker}")
        return self.underlyings[ticker].vol_surface.get_vol(
            self.valuation_date, expiry, strike
        )
    
    def get_forward(self, ticker: str, target_date: date) -> float:
        """Get forward price for an underlying."""
        if ticker not in self.underlyings:
            raise KeyError(f"Unknown underlying: {ticker}")
        return self.underlyings[ticker].get_forward(
            self.valuation_date, target_date, self.rate_curve
        )
    
    def discount_factor(self, target_date: date) -> float:
        """Get discount factor to target date."""
        return self.rate_curve.discount_factor(self.valuation_date, target_date)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MarketData":
        """
        Create MarketData from a dictionary specification.
        
        Expected format:
        {
            "valuation_date": "2024-01-15",
            "rate": 0.05,  # or "rate_curve": [...]
            "underlyings": {
                "AAPL": {
                    "spot": 180.0,
                    "vol": 0.25,  # or "vol_term": [...]
                    "div_yield": 0.01,  # or "dividends": [...]
                    "currency": "USD"
                },
                ...
            },
            "correlations": {"AAPL_GOOG": 0.6, ...}
        }
        """
        val_date = date.fromisoformat(data["valuation_date"])
        
        # Parse rate curve
        if "rate" in data:
            rate_curve = FlatRateCurve(rate=data["rate"])
        else:
            rate_curve = FlatRateCurve(rate=0.05)  # Default
        
        # Parse underlyings
        underlyings: Dict[str, Underlying] = {}
        underlying_data = data.get("underlyings", {})
        
        for ticker, udata in underlying_data.items():
            # Vol
            if "vol" in udata:
                vol_surface: VolatilitySurface = FlatVolatility(vol=udata["vol"])
            elif "vol_term" in udata:
                tenors = [
                    (date.fromisoformat(t["date"]), t["vol"])
                    for t in udata["vol_term"]
                ]
                vol_surface = PiecewiseConstantVol(tenors=tenors)
            else:
                vol_surface = FlatVolatility(vol=0.20)  # Default 20%
            
            # Dividends
            if "div_yield" in udata:
                div_model: DividendModel = ContinuousDividend(
                    yield_rate=udata["div_yield"]
                )
            elif "dividends" in udata:
                divs = [
                    (date.fromisoformat(d["ex_date"]), d["amount"])
                    for d in udata["dividends"]
                ]
                div_model = DiscreteDividend(dividends=divs)
            else:
                div_model = ContinuousDividend(yield_rate=0.0)
            
            underlyings[ticker] = Underlying(
                ticker=ticker,
                spot=udata["spot"],
                vol_surface=vol_surface,
                dividend_model=div_model,
                currency=udata.get("currency", "USD")
            )
        
        # Parse correlations
        correlation = None
        if "correlations" in data and len(underlyings) > 1:
            assets = list(underlyings.keys())
            correlation = CorrelationMatrix.from_dict(assets, data["correlations"])
        
        return cls(
            valuation_date=val_date,
            underlyings=underlyings,
            rate_curve=rate_curve,
            correlation=correlation
        )
