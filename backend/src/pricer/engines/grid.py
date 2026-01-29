"""
Event grid builder for Monte Carlo simulation.

Builds time grid from term sheet with all relevant dates:
- Valuation date (start)
- Observation dates (autocall/coupon checks)
- Ex-dividend dates (spot jumps)
- Maturity date (final payoff)
"""

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import List, Dict, Set, Tuple, Optional
import numpy as np

from pricer.core.day_count import DayCountConvention, day_count_fraction
from pricer.products.schema import TermSheet


class EventType(str, Enum):
    """Types of events in the simulation grid."""
    
    VALUATION = "valuation"
    OBSERVATION = "observation"     # Autocall/coupon check
    EX_DIVIDEND = "ex_dividend"     # Discrete dividend ex-date
    MATURITY = "maturity"


@dataclass
class GridEvent:
    """A single event in the simulation grid."""
    
    date: date
    event_type: EventType
    time_years: float = 0.0          # Year fraction from valuation
    index: int = 0                   # Index in grid
    observation_index: Optional[int] = None  # Index in observation schedule
    underlying_id: Optional[str] = None      # For ex-dividend events
    dividend_amount: Optional[float] = None  # For ex-dividend events


@dataclass
class SimulationGrid:
    """
    Complete simulation grid with all events.
    
    Attributes:
        events: List of grid events, sorted by date
        dates: Unique sorted dates
        times: Year fractions for each date
        dt: Time increments between consecutive dates
        observation_indices: Map from observation date to grid index
        exdiv_indices: Map from (underlying, date) to grid index
    """
    
    events: List[GridEvent] = field(default_factory=list)
    dates: List[date] = field(default_factory=list)
    times: np.ndarray = field(default_factory=lambda: np.array([]))
    dt: np.ndarray = field(default_factory=lambda: np.array([]))
    
    # Lookup maps
    observation_indices: Dict[date, int] = field(default_factory=dict)
    exdiv_indices: Dict[Tuple[str, date], int] = field(default_factory=dict)
    maturity_index: int = -1
    
    @property
    def num_steps(self) -> int:
        """Number of simulation steps."""
        return len(self.dates) - 1
    
    def get_observation_grid_indices(self) -> List[int]:
        """Get grid indices for observation dates."""
        return [
            e.index for e in self.events 
            if e.event_type == EventType.OBSERVATION
        ]


def build_simulation_grid(
    term_sheet: TermSheet,
    day_count: DayCountConvention = DayCountConvention.ACT_365F
) -> SimulationGrid:
    """
    Build simulation grid from term sheet.
    
    Collects all relevant dates:
    1. Valuation date
    2. All observation dates
    3. All ex-dividend dates from discrete dividend schedules
    4. Maturity date
    
    Args:
        term_sheet: Validated term sheet
        day_count: Day count for year fractions
        
    Returns:
        SimulationGrid with events and time grid
    """
    valuation_date = term_sheet.meta.valuation_date
    
    # Collect all dates with their event types
    date_events: Dict[date, Set[EventType]] = {}
    
    # Valuation date
    date_events[valuation_date] = {EventType.VALUATION}
    
    # Observation dates
    for obs_date in term_sheet.schedules.observation_dates:
        if obs_date >= valuation_date:
            if obs_date not in date_events:
                date_events[obs_date] = set()
            date_events[obs_date].add(EventType.OBSERVATION)
    
    # Maturity date
    maturity_date = term_sheet.meta.maturity_date
    if maturity_date not in date_events:
        date_events[maturity_date] = set()
    date_events[maturity_date].add(EventType.MATURITY)
    
    # Ex-dividend dates for discrete dividends
    exdiv_info: Dict[date, List[Tuple[str, float]]] = {}  # date -> [(underlying, amount)]
    
    for underlying in term_sheet.underlyings:
        if underlying.dividend_model.discrete_dividends:
            for div in underlying.dividend_model.discrete_dividends:
                if div.ex_date > valuation_date and div.ex_date <= maturity_date:
                    if div.ex_date not in date_events:
                        date_events[div.ex_date] = set()
                    date_events[div.ex_date].add(EventType.EX_DIVIDEND)
                    
                    if div.ex_date not in exdiv_info:
                        exdiv_info[div.ex_date] = []
                    exdiv_info[div.ex_date].append((underlying.id, div.amount))
    
    # Sort dates
    sorted_dates = sorted(date_events.keys())
    
    # Build time array
    times = np.array([
        day_count_fraction(valuation_date, d, day_count)
        for d in sorted_dates
    ])
    
    # Build dt array
    dt = np.diff(times)
    dt = np.concatenate([[0.0], dt])  # First step has dt=0
    
    # Build events list
    events: List[GridEvent] = []
    observation_indices: Dict[date, int] = {}
    exdiv_indices: Dict[Tuple[str, date], int] = {}
    maturity_index = -1
    
    obs_counter = 0
    
    for idx, d in enumerate(sorted_dates):
        event_types = date_events[d]
        
        # Create event for each type at this date
        for etype in sorted(event_types, key=lambda x: x.value):
            event = GridEvent(
                date=d,
                event_type=etype,
                time_years=times[idx],
                index=idx,
            )
            
            if etype == EventType.OBSERVATION:
                # Find observation index in schedule
                try:
                    obs_idx = term_sheet.schedules.observation_dates.index(d)
                    event.observation_index = obs_idx
                    observation_indices[d] = idx
                except ValueError:
                    pass
            
            elif etype == EventType.EX_DIVIDEND:
                # Add exdiv info
                for underlying_id, amount in exdiv_info.get(d, []):
                    exdiv_event = GridEvent(
                        date=d,
                        event_type=etype,
                        time_years=times[idx],
                        index=idx,
                        underlying_id=underlying_id,
                        dividend_amount=amount,
                    )
                    events.append(exdiv_event)
                    exdiv_indices[(underlying_id, d)] = idx
                continue  # Skip adding the generic event
            
            elif etype == EventType.MATURITY:
                maturity_index = idx
            
            events.append(event)
    
    return SimulationGrid(
        events=events,
        dates=sorted_dates,
        times=times,
        dt=dt,
        observation_indices=observation_indices,
        exdiv_indices=exdiv_indices,
        maturity_index=maturity_index,
    )


def get_exdiv_schedule_for_underlying(
    grid: SimulationGrid,
    underlying_id: str
) -> List[Tuple[int, float]]:
    """
    Get ex-dividend schedule for a specific underlying.
    
    Returns:
        List of (grid_index, dividend_amount) tuples
    """
    result = []
    for event in grid.events:
        if (event.event_type == EventType.EX_DIVIDEND and 
            event.underlying_id == underlying_id):
            result.append((event.index, event.dividend_amount or 0.0))
    return result
