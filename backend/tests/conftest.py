"""
Shared pytest fixtures for pricer tests.

Provides reusable test data and configurations for unit and integration tests.
"""

import pytest
from datetime import date, timedelta
from typing import Dict, Any

from pricer.products.schema import (
    TermSheet,
    Meta,
    Underlying,
    DividendModel,
    VolModel,
    DividendModelType,
    VolModelType,
    DiscountCurve,
    Correlation,
    Schedules,
    Payoff,
    KnockInBarrier,
    BarrierMonitoringType,
    SettlementType,
    DayCountConvention,
)
from pricer.pricers.autocall_pricer import PricingConfig


@pytest.fixture
def valuation_date() -> date:
    """Standard valuation date for tests."""
    return date(2024, 1, 15)


@pytest.fixture
def maturity_date(valuation_date: date) -> date:
    """Standard maturity date (3 years from valuation)."""
    return valuation_date + timedelta(days=3 * 365)


@pytest.fixture
def pricing_config() -> PricingConfig:
    """Standard pricing configuration for tests."""
    return PricingConfig(
        num_paths=10_000,  # Smaller for faster tests
        seed=42,
        block_size=5_000,
    )


@pytest.fixture
def single_asset_underlying() -> Underlying:
    """Single underlying asset for testing."""
    return Underlying(
        id="AAPL",
        spot=150.0,
        currency="USD",
        dividend_model=DividendModel(
            type=DividendModelType.CONTINUOUS,
            continuous_yield=0.02,
        ),
        vol_model=VolModel(
            type=VolModelType.FLAT,
            flat_vol=0.25,
        ),
    )


@pytest.fixture
def multi_asset_underlyings() -> list[Underlying]:
    """Multiple underlying assets for worst-of testing."""
    return [
        Underlying(
            id="AAPL",
            spot=150.0,
            currency="USD",
            dividend_model=DividendModel(
                type=DividendModelType.CONTINUOUS,
                continuous_yield=0.02,
            ),
            vol_model=VolModel(
                type=VolModelType.FLAT,
                flat_vol=0.25,
            ),
        ),
        Underlying(
            id="GOOGL",
            spot=2800.0,
            currency="USD",
            dividend_model=DividendModel(
                type=DividendModelType.CONTINUOUS,
                continuous_yield=0.0,
            ),
            vol_model=VolModel(
                type=VolModelType.FLAT,
                flat_vol=0.30,
            ),
        ),
        Underlying(
            id="MSFT",
            spot=380.0,
            currency="USD",
            dividend_model=DividendModel(
                type=DividendModelType.CONTINUOUS,
                continuous_yield=0.01,
            ),
            vol_model=VolModel(
                type=VolModelType.FLAT,
                flat_vol=0.28,
            ),
        ),
    ]


@pytest.fixture
def discount_curve() -> DiscountCurve:
    """Standard discount curve for testing."""
    return DiscountCurve(
        type="flat",
        flat_rate=0.05,
        day_count=DayCountConvention.ACT_365F,
    )


@pytest.fixture
def correlation_matrix() -> Correlation:
    """Correlation matrix for multi-asset products."""
    return Correlation(
        pairwise={
            "AAPL_GOOGL": 0.6,
            "AAPL_MSFT": 0.7,
            "GOOGL_MSFT": 0.65,
        }
    )


@pytest.fixture
def autocall_schedules(valuation_date: date, maturity_date: date) -> Schedules:
    """Standard quarterly autocall observation schedule."""
    obs_dates = []
    current = valuation_date + timedelta(days=90)  # First obs in 3 months

    while current <= maturity_date:
        obs_dates.append(current)
        current += timedelta(days=90)  # Quarterly

    # Payment dates 2 business days after observation
    pay_dates = [d + timedelta(days=2) for d in obs_dates]
    n = len(obs_dates)

    return Schedules(
        observation_dates=obs_dates,
        payment_dates=pay_dates,
        autocall_levels=[1.0] * n,
        coupon_barriers=[1.0] * n,
        coupon_rates=[0.025] * n,  # 2.5% per quarter (~10% annual)
    )


@pytest.fixture
def simple_autocall_term_sheet(
    valuation_date: date,
    maturity_date: date,
    single_asset_underlying: Underlying,
    discount_curve: DiscountCurve,
    autocall_schedules: Schedules,
) -> TermSheet:
    """Simple single-asset autocall term sheet for basic testing."""
    return TermSheet(
        meta=Meta(
            product_id="TEST-SIMPLE-001",
            trade_date=valuation_date - timedelta(days=5),
            valuation_date=valuation_date,
            settlement_date=valuation_date + timedelta(days=2),
            maturity_date=maturity_date,
            maturity_payment_date=maturity_date + timedelta(days=2),
            currency="USD",
            notional=1_000_000.0,
        ),
        underlyings=[single_asset_underlying],
        discount_curve=discount_curve,
        correlation=None,  # Single asset, no correlation needed
        schedules=autocall_schedules,
        ki_barrier=KnockInBarrier(
            level=0.70,  # 70% knock-in barrier
            monitoring=BarrierMonitoringType.CONTINUOUS,
        ),
        payoff=Payoff(
            worst_of=False,
            coupon_memory=True,
            coupon_on_autocall=True,
            redemption_if_autocall=1.0,
            redemption_if_no_ki=1.0,
            redemption_if_ki="worst_performance",
        ),
    )


@pytest.fixture
def worst_of_autocall_term_sheet(
    valuation_date: date,
    maturity_date: date,
    multi_asset_underlyings: list[Underlying],
    discount_curve: DiscountCurve,
    correlation_matrix: Correlation,
    autocall_schedules: Schedules,
) -> TermSheet:
    """Worst-of multi-asset autocall term sheet for comprehensive testing."""
    return TermSheet(
        meta=Meta(
            product_id="TEST-WOF-001",
            trade_date=valuation_date - timedelta(days=5),
            valuation_date=valuation_date,
            settlement_date=valuation_date + timedelta(days=2),
            maturity_date=maturity_date,
            maturity_payment_date=maturity_date + timedelta(days=2),
            currency="USD",
            notional=1_000_000.0,
        ),
        underlyings=multi_asset_underlyings,
        discount_curve=discount_curve,
        correlation=correlation_matrix,
        schedules=autocall_schedules,
        ki_barrier=KnockInBarrier(
            level=0.65,  # 65% knock-in barrier (worst-of)
            monitoring=BarrierMonitoringType.CONTINUOUS,
        ),
        payoff=Payoff(
            worst_of=True,
            coupon_memory=True,
            coupon_on_autocall=True,
            redemption_if_autocall=1.0,
            redemption_if_no_ki=1.0,
            redemption_if_ki="worst_performance",
        ),
    )


@pytest.fixture
def term_sheet_dict(simple_autocall_term_sheet: TermSheet) -> Dict[str, Any]:
    """Term sheet as dictionary for JSON serialization testing."""
    return simple_autocall_term_sheet.model_dump(mode="json")


# Parametrized fixtures for testing different scenarios

@pytest.fixture(params=[
    BarrierMonitoringType.CONTINUOUS,
    BarrierMonitoringType.DISCRETE,
])
def barrier_monitoring_type(request) -> BarrierMonitoringType:
    """Parametrized barrier monitoring types."""
    return request.param


@pytest.fixture(params=[
    VolModelType.FLAT,
    VolModelType.PIECEWISE_CONSTANT,
])
def vol_model_type(request) -> VolModelType:
    """Parametrized volatility model types."""
    return request.param


@pytest.fixture(params=[
    DividendModelType.CONTINUOUS,
    DividendModelType.DISCRETE,
])
def dividend_model_type(request) -> DividendModelType:
    """Parametrized dividend model types."""
    return request.param


# Helper functions for test assertions

def assert_pv_in_range(pv: float, notional: float, min_pct: float = 0.5, max_pct: float = 1.5):
    """Assert that PV is within reasonable range of notional."""
    assert min_pct * notional <= pv <= max_pct * notional, \
        f"PV {pv} outside expected range [{min_pct * notional}, {max_pct * notional}]"


def assert_probability_valid(prob: float):
    """Assert that probability is between 0 and 1."""
    assert 0.0 <= prob <= 1.0, f"Probability {prob} not in [0, 1]"


def assert_greeks_reasonable(delta: float, vega: float, notional: float):
    """Assert that Greeks are within reasonable bounds."""
    # Delta should be between -notional and +notional
    assert abs(delta) <= notional, f"Delta {delta} exceeds notional {notional}"

    # Vega should be positive and reasonable
    assert vega >= 0, f"Vega {vega} is negative"
    assert vega <= notional, f"Vega {vega} exceeds notional {notional}"
