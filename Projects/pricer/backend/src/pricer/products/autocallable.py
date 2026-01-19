"""
Autocallable note product definition.

Defines the complete specification for worst-of autocallable notes with coupons.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional, Dict, Any, Union

from pricer.products.base import (
    Product, Barrier, BarrierType, BarrierDirection, SettlementType
)


def _parse_date(value: Union[str, date]) -> date:
    """Parse a date from either a string or date object."""
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)

@dataclass
class ObservationDate:
    """
    Single observation date with associated barriers and payoff.
    
    Attributes:
        date: Observation date
        autocall_level: Autocall barrier as % of initial (e.g., 1.0 = 100%)
        redemption_amount: Amount paid on autocall (as % of notional)
    """
    
    date: date
    autocall_level: float = 1.0       # 100% of initial by default
    redemption_amount: float = 1.0    # 100% of notional by default


@dataclass
class CouponDate:
    """
    Coupon observation date.
    
    Attributes:
        observation_date: Date to check coupon barrier
        payment_date: Date coupon is paid (may be adjusted)
        coupon_barrier: Barrier level as % of initial
        coupon_rate: Coupon rate as % of notional (e.g., 0.02 = 2%)
    """
    
    observation_date: date
    payment_date: date
    coupon_barrier: float = 0.70  # 70% of initial
    coupon_rate: float = 0.02     # 2% per period


@dataclass
class ObservationSchedule:
    """Schedule of autocall observation dates."""
    
    dates: List[ObservationDate] = field(default_factory=list)
    
    def __len__(self) -> int:
        return len(self.dates)
    
    def __iter__(self):
        return iter(self.dates)
    
    def __getitem__(self, idx: int) -> ObservationDate:
        return self.dates[idx]
    
    @property
    def observation_dates(self) -> List[date]:
        """Get list of observation dates."""
        return [d.date for d in self.dates]


@dataclass
class CouponSchedule:
    """Schedule of coupon dates."""
    
    dates: List[CouponDate] = field(default_factory=list)
    memory: bool = True  # Coupon memory feature
    
    def __len__(self) -> int:
        return len(self.dates)
    
    def __iter__(self):
        return iter(self.dates)
    
    def __getitem__(self, idx: int) -> CouponDate:
        return self.dates[idx]
    
    @property
    def observation_dates(self) -> List[date]:
        """Get list of coupon observation dates."""
        return [d.observation_date for d in self.dates]


@dataclass
class AutocallableNote(Product):
    """
    Worst-of Autocallable Note with Coupons.
    
    Features:
    - Multi-asset worst-of payoff
    - Periodic autocall observation with early redemption
    - Periodic coupon with optional memory feature
    - Knock-in barrier (continuous or discrete) for principal protection
    - Cash or physical settlement at maturity
    
    Attributes:
        autocall_schedule: Schedule of autocall observation dates
        coupon_schedule: Schedule of coupon observation dates
        ki_barrier: Knock-in barrier specification
        final_redemption: Redemption amount at maturity if not autocalled
        protection_level: Protection level if KI has NOT occurred (usually 1.0)
    """
    
    # Inherited from Product:
    # product_id, underlyings, notional, currency, trade_date, 
    # settlement_date, maturity_date, worst_of, settlement_type
    
    autocall_schedule: ObservationSchedule = field(default_factory=ObservationSchedule)
    coupon_schedule: CouponSchedule = field(default_factory=CouponSchedule)
    ki_barrier: Optional[Barrier] = None
    final_redemption: float = 1.0  # 100% of notional if not knocked in
    protection_level: float = 0.0  # No protection floor beyond KI
    
    def get_all_dates(self) -> List[date]:
        """Get all relevant dates for path generation."""
        dates = set()
        
        # Settlement and maturity
        dates.add(self.settlement_date)
        dates.add(self.maturity_date)
        
        # Autocall dates
        for obs in self.autocall_schedule:
            dates.add(obs.date)
        
        # Coupon dates
        for coupon in self.coupon_schedule:
            dates.add(coupon.observation_date)
            dates.add(coupon.payment_date)
        
        return sorted(dates)
    
    def get_observation_dates(self) -> List[date]:
        """Get autocall observation dates only."""
        return self.autocall_schedule.observation_dates
    
    def get_coupon_dates(self) -> List[date]:
        """Get coupon observation dates only."""
        return self.coupon_schedule.observation_dates
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for JSON export."""
        data: Dict[str, Any] = {
            "product_type": "autocallable",
            "product_id": self.product_id,
            "underlyings": self.underlyings,
            "notional": self.notional,
            "currency": self.currency,
            "trade_date": self.trade_date.isoformat(),
            "settlement_date": self.settlement_date.isoformat(),
            "maturity_date": self.maturity_date.isoformat(),
            "worst_of": self.worst_of,
            "settlement_type": self.settlement_type.value,
            "final_redemption": self.final_redemption,
            "protection_level": self.protection_level,
            "coupon_memory": self.coupon_schedule.memory,
        }
        
        # Autocall schedule
        data["autocall_schedule"] = [
            {
                "date": obs.date.isoformat(),
                "autocall_level": obs.autocall_level,
                "redemption_amount": obs.redemption_amount,
            }
            for obs in self.autocall_schedule
        ]
        
        # Coupon schedule
        data["coupon_schedule"] = [
            {
                "observation_date": c.observation_date.isoformat(),
                "payment_date": c.payment_date.isoformat(),
                "coupon_barrier": c.coupon_barrier,
                "coupon_rate": c.coupon_rate,
            }
            for c in self.coupon_schedule
        ]
        
        # KI barrier
        if self.ki_barrier:
            data["ki_barrier"] = {
                "level": self.ki_barrier.level,
                "type": self.ki_barrier.barrier_type.value,
                "direction": self.ki_barrier.direction.value,
            }
            if self.ki_barrier.observation_start:
                data["ki_barrier"]["observation_start"] = \
                    self.ki_barrier.observation_start.isoformat()
            if self.ki_barrier.observation_end:
                data["ki_barrier"]["observation_end"] = \
                    self.ki_barrier.observation_end.isoformat()
        
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AutocallableNote":
        """Deserialize from dictionary."""
        # Parse autocall schedule
        autocall_dates = [
            ObservationDate(
                date=_parse_date(obs["date"]),
                autocall_level=obs.get("autocall_level", 1.0),
                redemption_amount=obs.get("redemption_amount", 1.0),
            )
            for obs in data.get("autocall_schedule", [])
        ]
        
        # Parse coupon schedule
        coupon_dates = [
            CouponDate(
                observation_date=_parse_date(c["observation_date"]),
                payment_date=_parse_date(c["payment_date"]),
                coupon_barrier=c.get("coupon_barrier", 0.70),
                coupon_rate=c.get("coupon_rate", 0.02),
            )
            for c in data.get("coupon_schedule", [])
        ]
        
        # Parse KI barrier
        ki_barrier = None
        if "ki_barrier" in data:
            ki_data = data["ki_barrier"]
            ki_barrier = Barrier(
                level=ki_data["level"],
                barrier_type=BarrierType(ki_data.get("type", "american")),
                direction=BarrierDirection(ki_data.get("direction", "down")),
                observation_start=_parse_date(ki_data["observation_start"])
                    if ki_data.get("observation_start") is not None else None,
                observation_end=_parse_date(ki_data["observation_end"])
                    if ki_data.get("observation_end") is not None else None,
            )
        
        return cls(
            product_id=data["product_id"],
            underlyings=data["underlyings"],
            notional=data["notional"],
            currency=data.get("currency", "USD"),
            trade_date=_parse_date(data["trade_date"]),
            settlement_date=_parse_date(data["settlement_date"]),
            maturity_date=_parse_date(data["maturity_date"]),
            worst_of=data.get("worst_of", True),
            settlement_type=SettlementType(data.get("settlement_type", "cash")),
            autocall_schedule=ObservationSchedule(dates=autocall_dates),
            coupon_schedule=CouponSchedule(
                dates=coupon_dates,
                memory=data.get("coupon_memory", True),
            ),
            ki_barrier=ki_barrier,
            final_redemption=data.get("final_redemption", 1.0),
            protection_level=data.get("protection_level", 0.0),
        )
