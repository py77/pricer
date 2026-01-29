"""
Autocallable-specific pricer using event engine.

Orchestrates event timeline construction and MC pricing.
"""

from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional
import numpy as np

from pricer.products.autocallable import AutocallableNote
from pricer.market.market_data import MarketData
from pricer.engines.base import PricingResult, CashFlow
from pricer.pricers.event_engine import EventEngine, Event, EventType, PathState


class AutocallablePricer:
    """
    Pricer for Autocallable notes.
    
    Builds event timeline from product specification and coordinates
    with Monte Carlo engine for path-wise payoff evaluation.
    
    This is a stub for Phase A - full implementation in Phase B.
    """
    
    def __init__(self) -> None:
        self.event_engine = EventEngine()
    
    def build_events(
        self,
        product: AutocallableNote,
        valuation_date: date
    ) -> List[Event]:
        """
        Build event timeline from product specification.
        
        Events are ordered by date, with priority:
        1. Autocall check
        2. Coupon check  
        3. KI check (discrete)
        4. Maturity
        """
        events: List[Event] = []
        
        # Autocall events
        for obs in product.autocall_schedule:
            if obs.date > valuation_date:
                events.append(Event(
                    date=obs.date,
                    event_type=EventType.AUTOCALL_CHECK,
                    payload={
                        "level": obs.autocall_level,
                        "redemption": obs.redemption_amount,
                    }
                ))
        
        # Coupon events
        for coupon in product.coupon_schedule:
            if coupon.observation_date > valuation_date:
                events.append(Event(
                    date=coupon.observation_date,
                    event_type=EventType.COUPON_CHECK,
                    payload={
                        "barrier": coupon.coupon_barrier,
                        "rate": coupon.coupon_rate,
                        "payment_date": coupon.payment_date,
                        "memory": product.coupon_schedule.memory,
                    }
                ))
        
        # Discrete KI events (if European barrier type)
        if product.ki_barrier is not None:
            from pricer.products.base import BarrierType
            if product.ki_barrier.barrier_type == BarrierType.EUROPEAN:
                # Add KI check at each observation date
                for obs_date in product.autocall_schedule.observation_dates:
                    if obs_date > valuation_date:
                        events.append(Event(
                            date=obs_date,
                            event_type=EventType.KI_CHECK,
                            payload={
                                "level": product.ki_barrier.level,
                                "direction": product.ki_barrier.direction.value,
                            }
                        ))
        
        # Maturity event
        if product.maturity_date > valuation_date:
            events.append(Event(
                date=product.maturity_date,
                event_type=EventType.MATURITY,
                payload={
                    "redemption": product.final_redemption,
                    "protection": product.protection_level,
                }
            ))
        
        return sorted(events)
    
    def evaluate_path(
        self,
        path: np.ndarray,
        initial_spots: np.ndarray,
        events: List[Event],
        date_indices: Dict[date, int],
        discount_factors: Dict[date, float],
        worst_of: bool = True,
        ki_barrier: Optional[float] = None,
        notional: float = 1.0
    ) -> PathState:
        """
        Evaluate single path through event timeline.
        
        STUB: Full implementation in Phase B.
        
        Args:
            path: Price path [num_steps, num_assets]
            initial_spots: Initial fixings [num_assets]
            events: Sorted event list
            date_indices: Mapping from date to path index
            discount_factors: DFs by date
            worst_of: Use worst-of performance
            ki_barrier: KI barrier level (for continuous monitoring)
            notional: Product notional
            
        Returns:
            PathState with accumulated cash flows and state
        """
        state = PathState()
        
        # STUB: Phase B will implement:
        # - Loop through events in order
        # - Check barrier conditions
        # - Accumulate discounted cash flows
        # - Update state (knocked_in, autocalled, etc.)
        
        return state
    
    def calculate_expected_cashflows(
        self,
        states: List[PathState],
        product: AutocallableNote,
        discount_factors: Dict[date, float]
    ) -> List[CashFlow]:
        """
        Calculate expected cash flows from path states.
        
        STUB: Full implementation in Phase B.
        """
        # Placeholder
        return []
