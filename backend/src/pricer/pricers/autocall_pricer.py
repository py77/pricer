"""
Autocallable pricer: ties together term sheet, grid, path generator, and event engine.

This is the main entry point for pricing autocallable structured products.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional, Dict, Any
import time
import numpy as np

from pricer.products.schema import TermSheet, load_term_sheet
from pricer.engines.grid import build_simulation_grid, SimulationGrid
from pricer.engines.path_generator import PathGenerator, PathGeneratorConfig, SimulatedPaths
from pricer.pricers.event_engine import EventEngine, EvaluationResult


@dataclass
class PricingConfig:
    """Configuration for pricing."""
    
    num_paths: int = 100_000
    seed: Optional[int] = None
    antithetic: bool = True
    block_size: int = 50_000


@dataclass
class PricingResult:
    """
    Complete pricing result.
    
    Includes PV, probabilities, Greeks (if computed), and diagnostics.
    """
    
    # Primary outputs
    pv: float
    pv_std_error: float
    
    # Probabilities and expectations
    autocall_probability: float
    ki_probability: float
    expected_coupon_count: float
    expected_life: float  # Years
    
    # Greeks (optional, computed in Phase C)
    delta: Dict[str, float] = field(default_factory=dict)
    vega: Dict[str, float] = field(default_factory=dict)
    
    # Diagnostics
    num_paths: int = 0
    num_steps: int = 0
    computation_time_ms: float = 0.0
    
    # Per-date breakdown
    autocall_prob_by_date: Dict[date, float] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "pv": self.pv,
            "pv_std_error": self.pv_std_error,
            "autocall_probability": self.autocall_probability,
            "ki_probability": self.ki_probability,
            "expected_coupon_count": self.expected_coupon_count,
            "expected_life": self.expected_life,
            "delta": self.delta,
            "vega": self.vega,
            "num_paths": self.num_paths,
            "num_steps": self.num_steps,
            "computation_time_ms": self.computation_time_ms,
        }


class AutocallPricer:
    """
    Pricer for Autocallable structured products.
    
    Orchestrates:
    1. Grid building from term sheet
    2. Path generation with Brownian bridge KI
    3. Event engine evaluation
    4. Greeks (via CRN bumping in Phase C)
    """
    
    def __init__(self, config: Optional[PricingConfig] = None) -> None:
        self.config = config or PricingConfig()
    
    def price(self, term_sheet: TermSheet) -> PricingResult:
        """
        Price an autocallable from a validated term sheet.
        
        Args:
            term_sheet: Validated TermSheet object
            
        Returns:
            PricingResult with PV and statistics
        """
        start_time = time.perf_counter()
        
        # 1. Build simulation grid
        grid = build_simulation_grid(term_sheet)
        
        # 2. Configure and create path generator
        pg_config = PathGeneratorConfig(
            num_paths=self.config.num_paths,
            seed=self.config.seed,
            antithetic=self.config.antithetic,
            block_size=self.config.block_size,
        )
        path_gen = PathGenerator(term_sheet, grid, pg_config)
        
        # 3. Generate paths
        paths = path_gen.generate()
        
        # 4. Create event engine and evaluate
        event_engine = EventEngine(term_sheet, grid)
        eval_result = event_engine.evaluate(paths)
        
        end_time = time.perf_counter()
        
        return PricingResult(
            pv=eval_result.pv,
            pv_std_error=eval_result.pv_std_error,
            autocall_probability=eval_result.autocall_probability,
            ki_probability=eval_result.ki_probability,
            expected_coupon_count=eval_result.expected_coupon_count,
            expected_life=eval_result.expected_life,
            num_paths=eval_result.num_paths,
            num_steps=eval_result.num_steps,
            computation_time_ms=(end_time - start_time) * 1000,
            autocall_prob_by_date=eval_result.autocall_prob_by_date,
        )
    
    def set_seed(self, seed: int) -> None:
        """Set random seed for reproducibility."""
        self.config.seed = seed


def price_from_json(
    json_path: str,
    num_paths: int = 100_000,
    seed: Optional[int] = None
) -> PricingResult:
    """
    Convenience function to price directly from JSON term sheet.
    
    Args:
        json_path: Path to JSON term sheet file
        num_paths: Number of Monte Carlo paths
        seed: Random seed for reproducibility
        
    Returns:
        PricingResult
    """
    term_sheet = load_term_sheet(json_path)
    config = PricingConfig(num_paths=num_paths, seed=seed)
    pricer = AutocallPricer(config)
    return pricer.price(term_sheet)


def print_pricing_report(ts: TermSheet, result: PricingResult) -> None:
    """Print formatted pricing report."""
    print("\n" + "=" * 70)
    print(f"PRICING REPORT: {ts.meta.product_id}")
    print("=" * 70)
    
    print(f"\n--- PRODUCT SUMMARY ---")
    print(f"  Underlyings:     {', '.join(u.id for u in ts.underlyings)}")
    print(f"  Notional:        {ts.meta.currency} {ts.meta.notional:,.0f}")
    print(f"  Valuation Date:  {ts.meta.valuation_date}")
    print(f"  Maturity Date:   {ts.meta.maturity_date}")
    if ts.ki_barrier:
        print(f"  KI Barrier:      {ts.ki_barrier.level:.0%} ({ts.ki_barrier.monitoring.value})")
    
    print(f"\n--- PRICING RESULTS ---")
    print(f"  PV:              {ts.meta.currency} {result.pv:,.2f}")
    print(f"  Std Error:       {ts.meta.currency} {result.pv_std_error:,.2f}")
    print(f"  PV as % of Notional: {result.pv / ts.meta.notional:.2%}")
    
    print(f"\n--- PROBABILITIES ---")
    print(f"  Autocall Prob:   {result.autocall_probability:.2%}")
    print(f"  KI Prob:         {result.ki_probability:.2%}")
    print(f"  Expected Coupons: {result.expected_coupon_count:.2f}")
    print(f"  Expected Life:   {result.expected_life:.2f} years")
    
    if result.autocall_prob_by_date:
        print(f"\n--- AUTOCALL BY DATE ---")
        for obs_date, prob in sorted(result.autocall_prob_by_date.items()):
            print(f"  {obs_date}: {prob:.2%}")
    
    if result.delta:
        print(f"\n--- GREEKS ---")
        for asset, delta in result.delta.items():
            print(f"  Delta {asset}: {delta:,.2f}")
        for asset, vega in result.vega.items():
            print(f"  Vega {asset}:  {vega:,.2f}")
    
    print(f"\n--- DIAGNOSTICS ---")
    print(f"  Paths:           {result.num_paths:,}")
    print(f"  Steps:           {result.num_steps}")
    print(f"  Time:            {result.computation_time_ms:.1f} ms")
    
    print("=" * 70)
