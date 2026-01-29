"""
Base product definitions and common structures.

Defines abstract Product class and barrier specifications.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import List, Optional, Dict, Any


class BarrierType(str, Enum):
    """Barrier observation type."""
    
    EUROPEAN = "european"       # Observed only at specific dates (discrete)
    AMERICAN = "american"       # Continuously monitored throughout life
    WINDOW = "window"           # Monitored within a specific date range


class BarrierDirection(str, Enum):
    """Barrier crossing direction."""
    
    DOWN = "down"   # Triggered when price falls to or below level
    UP = "up"       # Triggered when price rises to or above level


class SettlementType(str, Enum):
    """Settlement type at maturity."""
    
    CASH = "cash"           # Cash settlement
    PHYSICAL = "physical"   # Physical delivery of underlying


@dataclass
class Barrier:
    """
    Barrier specification for knock-in/knock-out features.
    
    Attributes:
        level: Barrier level as percentage of initial (e.g., 0.60 = 60%)
        barrier_type: European (discrete) or American (continuous)
        direction: Down or up barrier
        observation_start: Start date for barrier monitoring (optional)
        observation_end: End date for barrier monitoring (optional)
    """
    
    level: float
    barrier_type: BarrierType = BarrierType.AMERICAN
    direction: BarrierDirection = BarrierDirection.DOWN
    observation_start: Optional[date] = None
    observation_end: Optional[date] = None
    
    def is_breached(self, performance: float) -> bool:
        """
        Check if barrier is breached for a given performance level.
        
        Args:
            performance: Current price / initial price ratio
            
        Returns:
            True if barrier is breached
        """
        if self.direction == BarrierDirection.DOWN:
            return performance <= self.level
        else:
            return performance >= self.level


@dataclass
class Product(ABC):
    """
    Abstract base class for all structured products.
    
    Defines common attributes and interface for pricing.
    """
    
    product_id: str
    underlyings: List[str]
    notional: float
    currency: str
    trade_date: date
    settlement_date: date
    maturity_date: date
    worst_of: bool = True  # Worst-of for multi-asset
    settlement_type: SettlementType = SettlementType.CASH
    
    @abstractmethod
    def get_all_dates(self) -> List[date]:
        """Get all relevant dates for the product (for path generation)."""
        pass
    
    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Serialize product to dictionary."""
        pass
    
    @classmethod
    @abstractmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Product":
        """Deserialize product from dictionary."""
        pass
