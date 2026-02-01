"""
Structured Products Pricer - Production-grade pricing library.

A comprehensive library for pricing autocallable structured products using
Monte Carlo simulation with advanced features including:
- Multi-asset correlated GBM with Cholesky decomposition
- Brownian bridge continuous barrier monitoring
- Piecewise constant volatility models
- Discrete and continuous dividends
- Comprehensive Greeks calculation with Common Random Numbers

Example:
    >>> from pricer import TermSheet, AutocallPricer, PricingConfig
    >>> ts = TermSheet(**term_sheet_dict)
    >>> pricer = AutocallPricer(PricingConfig(num_paths=100_000))
    >>> result = pricer.price(ts)
    >>> print(f"PV: {result.pv:.2f}")
"""

__version__ = "0.1.0"

# Core product schemas
from pricer.products.schema import (
    TermSheet,
    Meta,
    Underlying,
    DividendModel,
    VolModel,
    DiscountCurve,
    Correlation,
    Schedule,
    Autocall,
    KnockIn,
    Coupon,
    Redemption,
    load_term_sheet,
    validate_term_sheet_json,
    print_term_sheet_summary,
    # Enums
    DayCountConvention,
    BusinessDayRule,
    Calendar,
    DividendModelType,
    VolModelType,
    BarrierMonitoringType,
    SettlementType,
)

# Pricing
from pricer.pricers.autocall_pricer import (
    AutocallPricer,
    PricingConfig,
)
from pricer.engines.base import PricingResult

# Risk analysis
from pricer.risk.greeks import (
    compute_greeks,
    BumpingConfig,
    GreeksResult,
)

# Reporting
from pricer.reporting import (
    generate_cashflow_report,
    compute_pv_decomposition,
    CashflowReport,
    CashflowEntry,
    PVDecomposition,
)

# Engines (for advanced usage)
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

# Market data (optional)
try:
    from pricer.market import (
        fetch_market_data_snapshot,
        MarketDataSnapshot,
    )
    _HAS_MARKET_DATA = True
except ImportError:
    _HAS_MARKET_DATA = False

__all__ = [
    # Version
    "__version__",
    # Core schemas
    "TermSheet",
    "Meta",
    "Underlying",
    "DividendModel",
    "VolModel",
    "DiscountCurve",
    "Correlation",
    "Schedule",
    "Autocall",
    "KnockIn",
    "Coupon",
    "Redemption",
    "load_term_sheet",
    "validate_term_sheet_json",
    "print_term_sheet_summary",
    # Enums
    "DayCountConvention",
    "BusinessDayRule",
    "Calendar",
    "DividendModelType",
    "VolModelType",
    "BarrierMonitoringType",
    "SettlementType",
    # Pricing
    "AutocallPricer",
    "PricingConfig",
    "PricingResult",
    # Risk
    "compute_greeks",
    "BumpingConfig",
    "GreeksResult",
    # Reporting
    "generate_cashflow_report",
    "compute_pv_decomposition",
    "CashflowReport",
    "CashflowEntry",
    "PVDecomposition",
    # Vanilla engines
    "bs_call_price",
    "bs_put_price",
    "bs_greeks",
    "price_vanilla",
    "implied_vol",
    "Greeks",
    "VanillaResult",
    "BinomialTree",
    "TrinomialTree",
    "price_american",
    "price_european_tree",
    "TreeResult",
    "ExerciseStyle",
    "OptionType",
]

# Add market data to __all__ if available
if _HAS_MARKET_DATA:
    __all__.extend([
        "fetch_market_data_snapshot",
        "MarketDataSnapshot",
    ])
