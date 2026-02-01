"""
Base pricing engine interface and result structures.

Defines abstract engine and common result types.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional, Any

from pricer.products.base import Product
from pricer.market.market_data import MarketData


@dataclass
class CashFlow:
    """
    Individual cash flow from a structured product.
    
    Attributes:
        date: Payment date
        amount: Cash flow amount (positive = receive)
        type: Type of cash flow (coupon, redemption, etc.)
        underlying: Associated underlying (for physical settlement)
    """
    
    date: date
    amount: float
    type: str  # "coupon", "redemption", "autocall", "maturity"
    underlying: Optional[str] = None


@dataclass
class PathResult:
    """
    Result for a single Monte Carlo path.
    
    Used for debugging and detailed analysis.
    """
    
    path_id: int
    cashflows: List[CashFlow] = field(default_factory=list)
    autocalled: bool = False
    autocall_date: Optional[date] = None
    knocked_in: bool = False
    knock_in_date: Optional[date] = None
    final_performance: float = 1.0  # Worst-of performance at maturity


@dataclass
class PricingResult:
    """
    Complete pricing result from an engine.
    
    Contains PV, statistics, Greeks, and detailed breakdown.
    """
    
    # Primary outputs
    pv: float                           # Present value
    pv_std_error: float = 0.0           # Standard error (MC only)
    
    # Probabilities
    autocall_probability: float = 0.0   # P(autocall before maturity)
    ki_probability: float = 0.0         # P(knock-in event)
    expected_coupon_count: float = 0.0  # Expected number of coupons
    
    # Timing
    expected_life: float = 0.0          # Expected life in years
    
    # Greeks (optional, filled by risk engine)
    greeks: Dict[str, float] = field(default_factory=dict)
    
    # Cashflow table (expected or pathwise)
    expected_cashflows: List[CashFlow] = field(default_factory=list)
    
    # Diagnostics
    num_paths: int = 0
    valuation_date: Optional[date] = None
    computation_time_ms: float = 0.0
    
    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize result to dictionary."""
        return {
            "pv": self.pv,
            "pv_std_error": self.pv_std_error,
            "autocall_probability": self.autocall_probability,
            "ki_probability": self.ki_probability,
            "expected_coupon_count": self.expected_coupon_count,
            "expected_life": self.expected_life,
            "greeks": self.greeks,
            "num_paths": self.num_paths,
            "valuation_date": self.valuation_date.isoformat() if self.valuation_date else None,
            "computation_time_ms": self.computation_time_ms,
        }


class PricingEngine(ABC):
    """
    Abstract base class for pricing engines.
    
    All engines must implement the price() method.
    """
    
    @abstractmethod
    def price(
        self,
        product: Product,
        market: MarketData
    ) -> PricingResult:
        """
        Price a product given market data.
        
        Args:
            product: Product to price
            market: Market data snapshot
            
        Returns:
            PricingResult with PV and diagnostics
        """
        pass
    
    @abstractmethod
    def get_seed(self) -> Optional[int]:
        """Get current random seed (for reproducibility)."""
        pass
    
    @abstractmethod
    def set_seed(self, seed: int) -> None:
        """Set random seed for reproducibility."""
        pass
