"""
Event engine for structured product payoff evaluation.

Implements deterministic evaluation order per observation date:
1. Autocall check (if met: pay redemption + optional coupon, stop)
2. Coupon check (if met: pay coupon with memory, reset unpaid)
3. Memory update (if coupon not met: accumulate unpaid)

At maturity:
- Compute final worst-of performance
- Apply redemption based on KI state
"""

from dataclasses import dataclass, field
from datetime import date
from typing import List, Dict, Tuple, Optional
import numpy as np

from pricer.products.schema import TermSheet
from pricer.engines.grid import SimulationGrid
from pricer.engines.path_generator import SimulatedPaths


@dataclass
class CashFlow:
    """A single cash flow."""
    
    date: date
    payment_date: date
    type: str           # "coupon", "autocall", "maturity"
    amount: float       # Undiscounted amount
    discount_factor: float = 1.0
    pv: float = 0.0     # Discounted amount


@dataclass
class PathResult:
    """Result for a single Monte Carlo path."""
    
    path_id: int
    cashflows: List[CashFlow] = field(default_factory=list)
    autocalled: bool = False
    autocall_step: int = -1
    knocked_in: bool = False
    final_performance: float = 1.0
    total_pv: float = 0.0
    num_coupons: int = 0


@dataclass
class EvaluationResult:
    """
    Aggregated result from event engine evaluation.
    
    Contains pathwise results and summary statistics.
    """
    
    # Summary statistics
    pv: float = 0.0
    pv_std_error: float = 0.0
    
    autocall_probability: float = 0.0
    ki_probability: float = 0.0
    expected_coupon_count: float = 0.0
    expected_life: float = 0.0  # Years
    
    # Per-observation statistics
    autocall_prob_by_date: Dict[date, float] = field(default_factory=dict)
    coupon_prob_by_date: Dict[date, float] = field(default_factory=dict)
    
    # Cashflow table (expected)
    expected_cashflows: List[CashFlow] = field(default_factory=list)
    
    # Diagnostics
    num_paths: int = 0
    num_steps: int = 0


class EventEngine:
    """
    Event-driven payoff evaluation engine.
    
    Processes paths through observation dates, applying:
    - Autocall logic (worst-of barrier check)
    - Coupon logic (barrier check with memory)
    - Maturity redemption (based on KI state)
    """
    
    def __init__(self, term_sheet: TermSheet, grid: SimulationGrid) -> None:
        self.ts = term_sheet
        self.grid = grid
        
        # Extract parameters
        self.notional = term_sheet.meta.notional
        self.worst_of = term_sheet.payoff.worst_of
        self.coupon_memory = term_sheet.payoff.coupon_memory
        self.coupon_on_autocall = term_sheet.payoff.coupon_on_autocall
        
        # Schedules
        self.obs_dates = term_sheet.schedules.observation_dates
        self.payment_dates = term_sheet.schedules.payment_dates
        self.autocall_levels = np.array(term_sheet.schedules.autocall_levels)
        self.coupon_barriers = np.array(term_sheet.schedules.coupon_barriers)
        self.coupon_rates = np.array(term_sheet.schedules.coupon_rates)
        
        # Maturity
        self.maturity_date = term_sheet.meta.maturity_date
        self.maturity_payment_date = term_sheet.meta.maturity_payment_date
        
        # Initial spots for performance calculation
        self.spots_0 = np.array([u.spot for u in term_sheet.underlyings])
        
        # === GUARDRAILS ===
        self._validate_inputs()
        
        # Build discount factor lookup
        self._build_discount_factors()
    
    def _validate_inputs(self) -> None:
        """Validate inputs and raise on inconsistencies."""
        # Validate barrier levels are sensible
        for i, level in enumerate(self.autocall_levels):
            if level <= 0 or level > 2.0:
                raise ValueError(
                    f"Autocall level at obs {i} is {level}, must be in (0, 2.0]"
                )
        
        for i, level in enumerate(self.coupon_barriers):
            if level <= 0 or level > 2.0:
                raise ValueError(
                    f"Coupon barrier at obs {i} is {level}, must be in (0, 2.0]"
                )
        
        # Validate KI barrier if present
        if self.ts.ki_barrier is not None:
            ki_level = self.ts.ki_barrier.level
            if ki_level <= 0 or ki_level > 1.5:
                raise ValueError(
                    f"KI barrier level is {ki_level}, must be in (0, 1.5]"
                )
        
        # Validate schedule alignment
        n_obs = len(self.obs_dates)
        if len(self.payment_dates) != n_obs:
            raise ValueError(
                f"payment_dates length {len(self.payment_dates)} != obs_dates length {n_obs}"
            )
        if len(self.autocall_levels) != n_obs:
            raise ValueError(
                f"autocall_levels length {len(self.autocall_levels)} != obs_dates length {n_obs}"
            )
        if len(self.coupon_barriers) != n_obs:
            raise ValueError(
                f"coupon_barriers length {len(self.coupon_barriers)} != obs_dates length {n_obs}"
            )
        if len(self.coupon_rates) != n_obs:
            raise ValueError(
                f"coupon_rates length {len(self.coupon_rates)} != obs_dates length {n_obs}"
            )
        
        # Validate spots are positive
        if np.any(self.spots_0 <= 0):
            raise ValueError(
                f"All spot prices must be positive, got {self.spots_0}"
            )
    
    def _build_discount_factors(self) -> None:
        """Pre-compute discount factors for all payment dates."""
        from pricer.core.day_count import DayCountConvention, day_count_fraction
        
        valuation = self.ts.meta.valuation_date
        r = self.ts.discount_curve.flat_rate or 0.0
        day_count = DayCountConvention(self.ts.discount_curve.day_count.value)
        
        self.discount_factors: Dict[date, float] = {}
        
        # Observation payment dates
        for pmt_date in self.payment_dates:
            yf = day_count_fraction(valuation, pmt_date, day_count)
            self.discount_factors[pmt_date] = np.exp(-r * yf)
        
        # Maturity payment date
        yf = day_count_fraction(valuation, self.maturity_payment_date, day_count)
        self.discount_factors[self.maturity_payment_date] = np.exp(-r * yf)
    
    def _compute_performance(
        self,
        spots: np.ndarray,
        step: int
    ) -> np.ndarray:
        """
        Compute performance at a given step.
        
        Args:
            spots: Spot paths [num_paths, num_steps+1, num_assets]
            step: Grid step index
            
        Returns:
            Performance array [num_paths]
            For worst-of: min over assets
            For best-of: max over assets
        """
        current_spots = spots[:, step, :]  # [num_paths, num_assets]
        perf = current_spots / self.spots_0  # [num_paths, num_assets]
        
        if self.worst_of:
            return np.min(perf, axis=1)
        else:
            return np.max(perf, axis=1)
    
    def evaluate(self, paths: SimulatedPaths) -> EvaluationResult:
        """
        Evaluate paths through event timeline.
        
        Args:
            paths: Simulated paths from PathGenerator
            
        Returns:
            EvaluationResult with PV and statistics
        """
        num_paths = paths.spots.shape[0]
        num_assets = paths.spots.shape[2]
        
        # Path state
        alive = np.ones(num_paths, dtype=bool)  # Still active (not autocalled)
        unpaid_coupons = np.zeros(num_paths)    # Accumulated unpaid for memory
        
        # Accumulators
        total_pv = np.zeros(num_paths)
        coupon_count = np.zeros(num_paths)
        autocall_step = np.full(num_paths, -1, dtype=np.int32)
        
        # Per-date statistics
        autocall_counts: Dict[date, int] = {}
        coupon_counts: Dict[date, int] = {}
        
        # Process each observation date
        for obs_idx, obs_date in enumerate(self.obs_dates):
            if obs_date not in self.grid.observation_indices:
                continue
                
            grid_step = self.grid.observation_indices[obs_date]
            pmt_date = self.payment_dates[obs_idx]
            df = self.discount_factors.get(pmt_date, 1.0)
            
            # Compute worst-of performance
            perf = self._compute_performance(paths.spots, grid_step)
            
            # === 1. AUTOCALL CHECK ===
            autocall_level = self.autocall_levels[obs_idx]
            autocall_triggered = alive & (perf >= autocall_level)
            
            if np.any(autocall_triggered):
                # Redemption payment
                redemption = self.ts.payoff.redemption_if_autocall * self.notional
                total_pv[autocall_triggered] += redemption * df
                
                # Coupon on autocall (if enabled)
                if self.coupon_on_autocall:
                    coupon_rate = self.coupon_rates[obs_idx]
                    if self.coupon_memory:
                        coupon_amount = (coupon_rate + unpaid_coupons[autocall_triggered]) * self.notional
                    else:
                        coupon_amount = coupon_rate * self.notional
                    total_pv[autocall_triggered] += coupon_amount * df
                    coupon_count[autocall_triggered] += 1
                
                # Mark as autocalled
                autocall_step[autocall_triggered] = grid_step
                alive[autocall_triggered] = False
                
                autocall_counts[obs_date] = int(np.sum(autocall_triggered))
            
            # === 2. COUPON CHECK (for paths still alive) ===
            if np.any(alive):
                coupon_barrier = self.coupon_barriers[obs_idx]
                coupon_triggered = alive & (perf >= coupon_barrier)
                
                if np.any(coupon_triggered):
                    coupon_rate = self.coupon_rates[obs_idx]
                    
                    if self.coupon_memory:
                        # Pay current + accumulated unpaid
                        coupon_amount = (coupon_rate + unpaid_coupons[coupon_triggered]) * self.notional
                        unpaid_coupons[coupon_triggered] = 0  # Reset
                    else:
                        coupon_amount = coupon_rate * self.notional
                    
                    total_pv[coupon_triggered] += coupon_amount * df
                    coupon_count[coupon_triggered] += 1
                    
                    coupon_counts[obs_date] = coupon_counts.get(obs_date, 0) + int(np.sum(coupon_triggered))
                
                # === 3. MEMORY UPDATE (for paths that didn't get coupon) ===
                if self.coupon_memory:
                    no_coupon = alive & ~coupon_triggered
                    coupon_rate = self.coupon_rates[obs_idx]
                    unpaid_coupons[no_coupon] += coupon_rate
        
        # === MATURITY ===
        maturity_step = self.grid.maturity_index
        if maturity_step >= 0 and np.any(alive):
            df_maturity = self.discount_factors.get(self.maturity_payment_date, 1.0)
            
            # Final performance
            final_perf = self._compute_performance(paths.spots, maturity_step)
            
            # KI state
            knocked_in = paths.ki_state
            
            # Redemption based on KI state
            for i in range(num_paths):
                if not alive[i]:
                    continue
                
                if knocked_in[i]:
                    # KI occurred - redemption depends on performance
                    if self.ts.payoff.redemption_if_ki == "worst_performance":
                        redemption = final_perf[i] * self.notional
                    elif self.ts.payoff.redemption_if_ki == "fixed":
                        redemption = (self.ts.payoff.ki_redemption_floor or 0.0) * self.notional
                    else:  # "floored"
                        floor = self.ts.payoff.ki_redemption_floor or 0.0
                        redemption = max(final_perf[i], floor) * self.notional
                else:
                    # No KI - full redemption
                    redemption = self.ts.payoff.redemption_if_no_ki * self.notional
                
                total_pv[i] += redemption * df_maturity
        
        # Compute summary statistics
        pv = float(np.mean(total_pv))
        pv_std = float(np.std(total_pv) / np.sqrt(num_paths))
        
        autocall_prob = float(np.mean(autocall_step >= 0))
        ki_prob = float(np.mean(paths.ki_state))
        expected_coupons = float(np.mean(coupon_count))
        
        # Expected life (in years)
        # For autocalled paths, use autocall time; for others, use maturity
        life_years = np.where(
            autocall_step >= 0,
            self.grid.times[autocall_step],
            self.grid.times[maturity_step] if maturity_step >= 0 else 0
        )
        expected_life = float(np.mean(life_years))
        
        return EvaluationResult(
            pv=pv,
            pv_std_error=pv_std,
            autocall_probability=autocall_prob,
            ki_probability=ki_prob,
            expected_coupon_count=expected_coupons,
            expected_life=expected_life,
            autocall_prob_by_date={
                d: c / num_paths for d, c in autocall_counts.items()
            },
            coupon_prob_by_date={
                d: c / num_paths for d, c in coupon_counts.items()
            },
            num_paths=num_paths,
            num_steps=self.grid.num_steps,
        )
