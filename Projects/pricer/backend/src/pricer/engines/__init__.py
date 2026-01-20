"""Pricing engines: Path generation, grid building, and MC simulation."""

from pricer.engines.base import PricingEngine, PricingResult, CashFlow
from pricer.engines.grid import (
    SimulationGrid,
    GridEvent,
    EventType,
    build_simulation_grid,
    get_exdiv_schedule_for_underlying,
)
from pricer.engines.path_generator import (
    PathGenerator,
    PathGeneratorConfig,
    SimulatedPaths,
    build_correlation_matrix,
    validate_and_fix_correlation,
    compute_cholesky,
    brownian_bridge_hit_probability,
)
from pricer.engines.black_scholes import (
    bs_call_price,
    bs_put_price,
    bs_greeks,
    price_vanilla,
    implied_vol,
    Greeks,
    VanillaResult,
)
from pricer.engines.tree_pricer import (
    BinomialTree,
    TrinomialTree,
    price_american,
    price_european_tree,
    TreeResult,
    ExerciseStyle,
    OptionType,
)

__all__ = [
    "PricingEngine",
    "PricingResult",
    "CashFlow",
    "SimulationGrid",
    "GridEvent",
    "EventType",
    "build_simulation_grid",
    "get_exdiv_schedule_for_underlying",
    "PathGenerator",
    "PathGeneratorConfig",
    "SimulatedPaths",
    "build_correlation_matrix",
    "validate_and_fix_correlation",
    "compute_cholesky",
    "brownian_bridge_hit_probability",
    # Black-Scholes
    "bs_call_price",
    "bs_put_price",
    "bs_greeks",
    "price_vanilla",
    "implied_vol",
    "Greeks",
    "VanillaResult",
    # Tree pricing
    "BinomialTree",
    "TrinomialTree",
    "price_american",
    "price_european_tree",
    "TreeResult",
    "ExerciseStyle",
    "OptionType",
]

