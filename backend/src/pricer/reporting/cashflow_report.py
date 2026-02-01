"""
Cashflow report generation for structured products.

Produces detailed cashflow tables with expected amounts, discount factors,
and PV contributions per observation date.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import List, Dict, Optional, Any
import numpy as np

from pricer.products.schema import TermSheet
from pricer.pricers.autocall_pricer import PricingConfig, AutocallPricer
from pricer.pricers.event_engine import EvaluationResult
from pricer.engines.grid import build_simulation_grid, SimulationGrid
from pricer.engines.path_generator import PathGenerator, PathGeneratorConfig
from pricer.pricers.event_engine import EventEngine


@dataclass
class CashflowEntry:
    """A single expected cashflow entry."""
    
    date: date                  # Observation/maturity date
    payment_date: date          # Actual payment date
    type: str                   # "coupon", "autocall_redemption", "maturity_redemption"
    expected_amount: float      # Expected undiscounted amount
    discount_factor: float      # DF from valuation to payment date
    pv_contribution: float      # Expected discounted amount
    probability: float          # Probability of this cashflow occurring
    

@dataclass
class PathStatistics:
    """Statistics about path outcomes."""
    
    # Distribution of redemption time (step index -> count)
    redemption_time_distribution: Dict[int, int] = field(default_factory=dict)
    
    # Distribution by date
    autocall_by_date: Dict[date, float] = field(default_factory=dict)
    
    # Summary
    mean_life_years: float = 0.0
    median_life_years: float = 0.0


@dataclass
class PricingSummary:
    """High-level pricing summary."""
    
    pv: float
    pv_std_error: float
    pv_as_pct_notional: float
    
    autocall_probability: float
    ki_probability: float
    expected_coupon_count: float
    expected_life_years: float
    
    notional: float
    currency: str
    valuation_date: date
    
    def print_summary(self) -> None:
        """Print formatted summary."""
        print("\n" + "=" * 60)
        print("PRICING SUMMARY")
        print("=" * 60)
        print(f"  PV:                   {self.currency} {self.pv:,.2f}")
        print(f"  Std Error:            {self.currency} {self.pv_std_error:,.2f}")
        print(f"  PV as % of Notional:  {self.pv_as_pct_notional:.2%}")
        print(f"  Autocall Probability: {self.autocall_probability:.2%}")
        print(f"  KI Probability:       {self.ki_probability:.2%}")
        print(f"  Expected Coupons:     {self.expected_coupon_count:.2f}")
        print(f"  Expected Life:        {self.expected_life_years:.2f} years")
        print("=" * 60)


@dataclass
class CashflowReport:
    """
    Complete cashflow report for a structured product.
    
    Contains:
    - Expected cashflow table
    - Pricing summary
    - Path statistics
    """
    
    product_id: str
    valuation_date: date
    
    # Cashflow table
    cashflows: List[CashflowEntry] = field(default_factory=list)
    
    # Summary
    summary: Optional[PricingSummary] = None
    
    # Path statistics
    path_stats: Optional[PathStatistics] = None
    
    # Diagnostics
    num_paths: int = 0
    computation_time_ms: float = 0.0
    
    def print_cashflow_table(self) -> None:
        """Print formatted cashflow table."""
        print("\n" + "=" * 80)
        print("CASHFLOW TABLE")
        print("=" * 80)
        
        print(f"\n{'Date':<12} {'Type':<20} {'Prob':>8} {'Expected':>14} {'DF':>8} {'PV':>14}")
        print("-" * 80)
        
        total_pv = 0.0
        for cf in self.cashflows:
            print(
                f"{cf.date.isoformat():<12} "
                f"{cf.type:<20} "
                f"{cf.probability:>7.2%} "
                f"{cf.expected_amount:>14,.2f} "
                f"{cf.discount_factor:>8.4f} "
                f"{cf.pv_contribution:>14,.2f}"
            )
            total_pv += cf.pv_contribution
        
        print("-" * 80)
        print(f"{'TOTAL PV':<43} {' ':>8} {' ':>8} {total_pv:>14,.2f}")
        print("=" * 80)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "product_id": self.product_id,
            "valuation_date": self.valuation_date.isoformat(),
            "cashflows": [
                {
                    "date": cf.date.isoformat(),
                    "payment_date": cf.payment_date.isoformat(),
                    "type": cf.type,
                    "expected_amount": cf.expected_amount,
                    "discount_factor": cf.discount_factor,
                    "pv_contribution": cf.pv_contribution,
                    "probability": cf.probability,
                }
                for cf in self.cashflows
            ],
            "summary": {
                "pv": self.summary.pv if self.summary else 0,
                "autocall_probability": self.summary.autocall_probability if self.summary else 0,
                "ki_probability": self.summary.ki_probability if self.summary else 0,
            } if self.summary else None,
            "num_paths": self.num_paths,
        }


def generate_cashflow_report(
    term_sheet: TermSheet,
    pricing_config: Optional[PricingConfig] = None,
    include_path_stats: bool = True
) -> CashflowReport:
    """
    Generate a detailed cashflow report for a structured product.
    
    Args:
        term_sheet: Validated term sheet
        pricing_config: MC configuration (paths, seed)
        include_path_stats: Whether to compute path statistics
        
    Returns:
        CashflowReport with cashflow table and summary
    """
    import time
    start_time = time.perf_counter()
    
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
    
    # Evaluate with extended tracking
    event_engine = EventEngine(term_sheet, grid)
    eval_result = event_engine.evaluate(paths)
    
    num_paths = pricing_config.num_paths
    notional = term_sheet.meta.notional
    
    # Build cashflow entries from schedules
    cashflows: List[CashflowEntry] = []
    
    # Get discount factors
    from pricer.core.day_count import DayCountConvention, day_count_fraction
    valuation = term_sheet.meta.valuation_date
    r = term_sheet.discount_curve.flat_rate or 0.0
    day_count = DayCountConvention(term_sheet.discount_curve.day_count.value)
    
    # Per-observation cashflows
    for obs_idx, obs_date in enumerate(term_sheet.schedules.observation_dates):
        pmt_date = term_sheet.schedules.payment_dates[obs_idx]
        yf = day_count_fraction(valuation, pmt_date, day_count)
        df = np.exp(-r * yf)
        
        coupon_rate = term_sheet.schedules.coupon_rates[obs_idx]
        
        # Coupon probability (from evaluation result)
        coupon_prob = eval_result.coupon_prob_by_date.get(obs_date, 0.0)
        autocall_prob = eval_result.autocall_prob_by_date.get(obs_date, 0.0)
        
        # Coupon entry (simplified: expected coupon if not autocalled earlier)
        coupon_amount = coupon_rate * notional
        expected_coupon = coupon_amount * coupon_prob
        
        if coupon_prob > 0:
            cashflows.append(CashflowEntry(
                date=obs_date,
                payment_date=pmt_date,
                type="coupon",
                expected_amount=expected_coupon,
                discount_factor=df,
                pv_contribution=expected_coupon * df,
                probability=coupon_prob,
            ))
        
        # Autocall redemption entry
        if autocall_prob > 0:
            redemption = term_sheet.payoff.redemption_if_autocall * notional
            expected_redemption = redemption * autocall_prob
            
            cashflows.append(CashflowEntry(
                date=obs_date,
                payment_date=pmt_date,
                type="autocall_redemption",
                expected_amount=expected_redemption,
                discount_factor=df,
                pv_contribution=expected_redemption * df,
                probability=autocall_prob,
            ))
    
    # Maturity redemption
    maturity_pmt_date = term_sheet.meta.maturity_payment_date
    yf_maturity = day_count_fraction(valuation, maturity_pmt_date, day_count)
    df_maturity = np.exp(-r * yf_maturity)
    
    # Probability of reaching maturity = 1 - autocall_prob
    maturity_prob = 1.0 - eval_result.autocall_probability
    
    if maturity_prob > 0:
        # Compute actual expected redemption from MC paths
        # We need to get the actual per-path outcomes
        spots_0 = np.array([u.spot for u in term_sheet.underlyings])
        maturity_step = grid.maturity_index
        
        if maturity_step >= 0:
            # Rebuild alive state at maturity by retracing autocalls
            alive = np.ones(num_paths, dtype=bool)
            obs_dates = term_sheet.schedules.observation_dates
            autocall_levels = np.array(term_sheet.schedules.autocall_levels)
            worst_of = term_sheet.payoff.worst_of
            
            for obs_idx, obs_date in enumerate(obs_dates):
                if obs_date not in grid.observation_indices:
                    continue
                step = grid.observation_indices[obs_date]
                current_spots = paths.spots[:, step, :]
                perf = current_spots / spots_0
                if worst_of:
                    wof = np.min(perf, axis=1)
                else:
                    wof = np.max(perf, axis=1)
                ac_level = autocall_levels[obs_idx]
                alive[alive & (wof >= ac_level)] = False
            
            # For paths alive at maturity, compute redemption
            alive_paths = np.where(alive)[0]
            if len(alive_paths) > 0:
                final_spots = paths.spots[alive_paths, maturity_step, :]
                final_perf = final_spots / spots_0
                if worst_of:
                    wof_final = np.min(final_perf, axis=1)
                else:
                    wof_final = np.max(final_perf, axis=1)
                
                knocked_in_at_maturity = paths.ki_state[alive_paths]
                
                # Compute redemption per path at maturity
                redemption_per_path = np.zeros(len(alive_paths))
                
                # No KI paths
                no_ki_mask = ~knocked_in_at_maturity
                if np.any(no_ki_mask):
                    redemption_per_path[no_ki_mask] = term_sheet.payoff.redemption_if_no_ki * notional
                
                # KI paths
                ki_mask = knocked_in_at_maturity
                if np.any(ki_mask):
                    if term_sheet.payoff.redemption_if_ki == "worst_performance":
                        redemption_per_path[ki_mask] = wof_final[ki_mask] * notional
                    elif term_sheet.payoff.redemption_if_ki == "fixed":
                        floor = term_sheet.payoff.ki_redemption_floor or 0.0
                        redemption_per_path[ki_mask] = floor * notional
                    else:  # floored
                        floor = term_sheet.payoff.ki_redemption_floor or 0.0
                        redemption_per_path[ki_mask] = np.maximum(wof_final[ki_mask], floor) * notional
                
                # Probabilities (fraction of total paths)
                no_ki_count = np.sum(no_ki_mask)
                ki_count = np.sum(ki_mask)
                
                # No KI maturity cashflow
                if no_ki_count > 0:
                    no_ki_prob = no_ki_count / num_paths
                    no_ki_expected = np.mean(redemption_per_path[no_ki_mask]) * (no_ki_count / num_paths) * num_paths / no_ki_count
                    # Simpler: total expected = mean over all paths
                    no_ki_expected_total = np.sum(redemption_per_path[no_ki_mask]) / num_paths
                    
                    cashflows.append(CashflowEntry(
                        date=term_sheet.meta.maturity_date,
                        payment_date=maturity_pmt_date,
                        type="maturity_no_ki",
                        expected_amount=no_ki_expected_total,
                        discount_factor=df_maturity,
                        pv_contribution=no_ki_expected_total * df_maturity,
                        probability=no_ki_prob,
                    ))
                
                # KI maturity cashflow
                if ki_count > 0:
                    ki_prob = ki_count / num_paths
                    ki_expected_total = np.sum(redemption_per_path[ki_mask]) / num_paths
                    
                    cashflows.append(CashflowEntry(
                        date=term_sheet.meta.maturity_date,
                        payment_date=maturity_pmt_date,
                        type="maturity_with_ki",
                        expected_amount=ki_expected_total,
                        discount_factor=df_maturity,
                        pv_contribution=ki_expected_total * df_maturity,
                        probability=ki_prob,
                    ))
    
    # Build summary
    summary = PricingSummary(
        pv=eval_result.pv,
        pv_std_error=eval_result.pv_std_error,
        pv_as_pct_notional=eval_result.pv / notional,
        autocall_probability=eval_result.autocall_probability,
        ki_probability=eval_result.ki_probability,
        expected_coupon_count=eval_result.expected_coupon_count,
        expected_life_years=eval_result.expected_life,
        notional=notional,
        currency=term_sheet.meta.currency,
        valuation_date=valuation,
    )
    
    # Path statistics
    path_stats = None
    if include_path_stats:
        path_stats = PathStatistics(
            autocall_by_date=eval_result.autocall_prob_by_date,
            mean_life_years=eval_result.expected_life,
        )
    
    end_time = time.perf_counter()
    
    return CashflowReport(
        product_id=term_sheet.meta.product_id,
        valuation_date=valuation,
        cashflows=cashflows,
        summary=summary,
        path_stats=path_stats,
        num_paths=num_paths,
        computation_time_ms=(end_time - start_time) * 1000,
    )
