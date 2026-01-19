"""
PV decomposition for structured products.

Breaks down total PV into:
- Coupon PV: Expected present value of all coupon payments
- Redemption PV: Expected present value of principal redemption
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, Optional
import numpy as np

from pricer.products.schema import TermSheet
from pricer.pricers.autocall_pricer import PricingConfig
from pricer.engines.grid import build_simulation_grid
from pricer.engines.path_generator import PathGenerator, PathGeneratorConfig
from pricer.pricers.event_engine import EventEngine


@dataclass
class PVDecomposition:
    """
    Breakdown of PV into component parts.
    
    Attributes:
        coupon_pv: Expected PV of all coupon payments
        redemption_pv: Expected PV of redemption payments (autocall + maturity)
        autocall_redemption_pv: PV from autocall redemptions only
        maturity_redemption_pv: PV from maturity redemption only
        total_pv: Total PV (should equal coupon_pv + redemption_pv)
    """
    
    coupon_pv: float = 0.0
    redemption_pv: float = 0.0
    autocall_redemption_pv: float = 0.0
    maturity_redemption_pv: float = 0.0
    total_pv: float = 0.0
    
    # As percentage of notional
    coupon_pv_pct: float = 0.0
    redemption_pv_pct: float = 0.0
    
    # Diagnostics
    num_paths: int = 0
    
    def print_summary(self, currency: str = "USD") -> None:
        """Print formatted decomposition."""
        print("\n" + "=" * 60)
        print("PV DECOMPOSITION")
        print("=" * 60)
        
        print(f"\n{'Component':<30} {'PV':>15} {'% of Total':>12}")
        print("-" * 60)
        
        total = self.total_pv if self.total_pv != 0 else 1.0
        
        print(f"{'Coupon PV':<30} {currency} {self.coupon_pv:>10,.2f} {self.coupon_pv/total:>11.2%}")
        print(f"{'Autocall Redemption PV':<30} {currency} {self.autocall_redemption_pv:>10,.2f} {self.autocall_redemption_pv/total:>11.2%}")
        print(f"{'Maturity Redemption PV':<30} {currency} {self.maturity_redemption_pv:>10,.2f} {self.maturity_redemption_pv/total:>11.2%}")
        print("-" * 60)
        print(f"{'TOTAL PV':<30} {currency} {self.total_pv:>10,.2f} {'100.00%':>12}")
        print("=" * 60)


def compute_pv_decomposition(
    term_sheet: TermSheet,
    pricing_config: Optional[PricingConfig] = None
) -> PVDecomposition:
    """
    Compute PV decomposition by tracking cashflow sources.
    
    This runs a modified evaluation that tracks coupon vs redemption PV separately.
    
    Args:
        term_sheet: Validated term sheet
        pricing_config: MC configuration
        
    Returns:
        PVDecomposition with breakdown
    """
    pricing_config = pricing_config or PricingConfig()
    
    # Build simulation components
    grid = build_simulation_grid(term_sheet)
    
    pg_config = PathGeneratorConfig(
        num_paths=pricing_config.num_paths,
        seed=pricing_config.seed,
        antithetic=pricing_config.antithetic,
        block_size=pricing_config.block_size,
    )
    path_gen = PathGenerator(term_sheet, grid, pg_config)
    paths = path_gen.generate()
    
    num_paths = paths.spots.shape[0]
    notional = term_sheet.meta.notional
    
    # Get discount factors
    from pricer.core.day_count import DayCountConvention, day_count_fraction
    valuation = term_sheet.meta.valuation_date
    r = term_sheet.discount_curve.flat_rate or 0.0
    day_count = DayCountConvention(term_sheet.discount_curve.day_count.value)
    
    # Initial spots for performance
    spots_0 = np.array([u.spot for u in term_sheet.underlyings])
    
    # Path state
    alive = np.ones(num_paths, dtype=bool)
    unpaid_coupons = np.zeros(num_paths)
    
    # Separate accumulators
    coupon_pv = np.zeros(num_paths)
    autocall_redemption_pv = np.zeros(num_paths)
    maturity_redemption_pv = np.zeros(num_paths)
    
    obs_dates = term_sheet.schedules.observation_dates
    payment_dates = term_sheet.schedules.payment_dates
    autocall_levels = np.array(term_sheet.schedules.autocall_levels)
    coupon_barriers = np.array(term_sheet.schedules.coupon_barriers)
    coupon_rates = np.array(term_sheet.schedules.coupon_rates)
    
    worst_of = term_sheet.payoff.worst_of
    coupon_memory = term_sheet.payoff.coupon_memory
    coupon_on_autocall = term_sheet.payoff.coupon_on_autocall
    
    # Process each observation
    for obs_idx, obs_date in enumerate(obs_dates):
        if obs_date not in grid.observation_indices:
            continue
        
        grid_step = grid.observation_indices[obs_date]
        pmt_date = payment_dates[obs_idx]
        
        yf = day_count_fraction(valuation, pmt_date, day_count)
        df = np.exp(-r * yf)
        
        # Performance
        current_spots = paths.spots[:, grid_step, :]
        perf = current_spots / spots_0
        if worst_of:
            wof_perf = np.min(perf, axis=1)
        else:
            wof_perf = np.max(perf, axis=1)
        
        # Autocall check
        autocall_level = autocall_levels[obs_idx]
        autocall_triggered = alive & (wof_perf >= autocall_level)
        
        if np.any(autocall_triggered):
            # Redemption
            redemption = term_sheet.payoff.redemption_if_autocall * notional
            autocall_redemption_pv[autocall_triggered] += redemption * df
            
            # Coupon on autocall
            if coupon_on_autocall:
                coupon_rate = coupon_rates[obs_idx]
                if coupon_memory:
                    coupon_amount = (coupon_rate + unpaid_coupons[autocall_triggered]) * notional
                else:
                    coupon_amount = coupon_rate * notional
                coupon_pv[autocall_triggered] += coupon_amount * df
            
            alive[autocall_triggered] = False
        
        # Coupon check (alive paths)
        if np.any(alive):
            coupon_barrier = coupon_barriers[obs_idx]
            coupon_triggered = alive & (wof_perf >= coupon_barrier)
            
            if np.any(coupon_triggered):
                coupon_rate = coupon_rates[obs_idx]
                if coupon_memory:
                    coupon_amount = (coupon_rate + unpaid_coupons[coupon_triggered]) * notional
                    unpaid_coupons[coupon_triggered] = 0
                else:
                    coupon_amount = coupon_rate * notional
                
                coupon_pv[coupon_triggered] += coupon_amount * df
            
            # Memory update
            if coupon_memory:
                no_coupon = alive & ~coupon_triggered
                coupon_rate = coupon_rates[obs_idx]
                unpaid_coupons[no_coupon] += coupon_rate
    
    # Maturity
    maturity_step = grid.maturity_index
    if maturity_step >= 0 and np.any(alive):
        maturity_pmt_date = term_sheet.meta.maturity_payment_date
        yf_maturity = day_count_fraction(valuation, maturity_pmt_date, day_count)
        df_maturity = np.exp(-r * yf_maturity)
        
        # Final performance
        final_spots = paths.spots[:, maturity_step, :]
        final_perf = final_spots / spots_0
        if worst_of:
            wof_final = np.min(final_perf, axis=1)
        else:
            wof_final = np.max(final_perf, axis=1)
        
        # KI state
        knocked_in = paths.ki_state
        
        # Redemption
        for i in range(num_paths):
            if not alive[i]:
                continue
            
            if knocked_in[i]:
                if term_sheet.payoff.redemption_if_ki == "worst_performance":
                    redemption = wof_final[i] * notional
                elif term_sheet.payoff.redemption_if_ki == "fixed":
                    redemption = (term_sheet.payoff.ki_redemption_floor or 0.0) * notional
                else:  # floored
                    floor = term_sheet.payoff.ki_redemption_floor or 0.0
                    redemption = max(wof_final[i], floor) * notional
            else:
                redemption = term_sheet.payoff.redemption_if_no_ki * notional
            
            maturity_redemption_pv[i] += redemption * df_maturity
    
    # Aggregate
    total_coupon_pv = float(np.mean(coupon_pv))
    total_autocall_pv = float(np.mean(autocall_redemption_pv))
    total_maturity_pv = float(np.mean(maturity_redemption_pv))
    total_redemption_pv = total_autocall_pv + total_maturity_pv
    total_pv = total_coupon_pv + total_redemption_pv
    
    return PVDecomposition(
        coupon_pv=total_coupon_pv,
        redemption_pv=total_redemption_pv,
        autocall_redemption_pv=total_autocall_pv,
        maturity_redemption_pv=total_maturity_pv,
        total_pv=total_pv,
        coupon_pv_pct=total_coupon_pv / notional,
        redemption_pv_pct=total_redemption_pv / notional,
        num_paths=num_paths,
    )
