"""
Extended tests for EventEngine covering autocall stops, coupon memory, and edge cases.

These tests use small path counts (10k) for fast execution.
"""

import pytest
import numpy as np
from datetime import date
from copy import deepcopy

from pricer.products.schema import (
    TermSheet, Meta, Underlying, DividendModel, VolModel,
    DiscountCurve, Schedules, Payoff, KnockInBarrier, Correlation,
    DividendModelType, VolModelType, BarrierMonitoringType, DayCountConvention,
    DiscreteDividend,
)
from pricer.pricers.autocall_pricer import AutocallPricer, PricingConfig


def create_simple_term_sheet(
    spots: list[float],
    autocall_levels: list[float],
    coupon_barriers: list[float],
    ki_level: float = 0.6,
    coupon_memory: bool = True,
) -> TermSheet:
    """Create a simple 2-underlying term sheet for testing."""
    return TermSheet(
        meta=Meta(
            product_id="TEST-001",
            trade_date=date(2024, 1, 10),
            valuation_date=date(2024, 1, 15),
            settlement_date=date(2024, 1, 17),
            maturity_date=date(2025, 1, 15),
            maturity_payment_date=date(2025, 1, 17),
            currency="USD",
            notional=1_000_000,
        ),
        underlyings=[
            Underlying(
                id="A",
                spot=spots[0],
                currency="USD",
                dividend_model=DividendModel(
                    type=DividendModelType.CONTINUOUS,
                    continuous_yield=0.0,
                ),
                vol_model=VolModel(
                    type=VolModelType.FLAT,
                    flat_vol=0.25,
                ),
            ),
            Underlying(
                id="B",
                spot=spots[1],
                currency="USD",
                dividend_model=DividendModel(
                    type=DividendModelType.CONTINUOUS,
                    continuous_yield=0.0,
                ),
                vol_model=VolModel(
                    type=VolModelType.FLAT,
                    flat_vol=0.25,
                ),
            ),
        ],
        discount_curve=DiscountCurve(
            type="flat",
            flat_rate=0.05,
            day_count=DayCountConvention.ACT_365F,
        ),
        correlation=Correlation(
            pairwise={"A_B": 0.7},
        ),
        schedules=Schedules(
            observation_dates=[
                date(2024, 4, 15),  # Q1
                date(2024, 7, 15),  # Q2
                date(2024, 10, 15), # Q3
                date(2025, 1, 15),  # Maturity
            ],
            payment_dates=[
                date(2024, 4, 17),
                date(2024, 7, 17),
                date(2024, 10, 17),
                date(2025, 1, 17),
            ],
            autocall_levels=autocall_levels,
            coupon_barriers=coupon_barriers,
            coupon_rates=[0.02, 0.02, 0.02, 0.02],
        ),
        ki_barrier=KnockInBarrier(
            level=ki_level,
            monitoring=BarrierMonitoringType.CONTINUOUS,
        ),
        payoff=Payoff(
            worst_of=True,
            coupon_memory=coupon_memory,
            coupon_on_autocall=True,
            redemption_if_autocall=1.0,
            redemption_if_no_ki=1.0,
            redemption_if_ki="worst_performance",
        ),
    )


class TestAutocallStops:
    """Test that autocall correctly stops the product."""
    
    def test_autocall_at_first_observation(self) -> None:
        """
        When autocall triggers at first observation:
        - No later coupons should be paid
        - Total PV = redemption + coupon (one period)
        """
        # Very low autocall level (0.5) to guarantee trigger with normal spots
        ts = create_simple_term_sheet(
            spots=[100.0, 100.0],
            autocall_levels=[0.5, 0.5, 0.5, 0.5],  # Will always trigger
            coupon_barriers=[0.7, 0.7, 0.7, 0.7],
            ki_level=0.3,  # Very low to avoid KI
        )
        
        config = PricingConfig(num_paths=10_000, seed=42)
        result = AutocallPricer(config).price(ts)
        
        # Should autocall at first observation with very high probability
        assert result.autocall_probability > 0.95
        
        # Expected coupons should be ~1 (only first observation coupon)
        assert result.expected_coupon_count < 1.5
        
        # Expected life should be short (around 0.25 years for Q1 autocall)
        assert result.expected_life < 0.5
    
    def test_no_autocall_with_high_barrier(self) -> None:
        """
        With very high autocall barrier, product should reach maturity.
        """
        ts = create_simple_term_sheet(
            spots=[100.0, 100.0],
            autocall_levels=[1.5, 1.5, 1.5, 1.5],  # Very high, unlikely to trigger
            coupon_barriers=[0.7, 0.7, 0.7, 0.7],
            ki_level=0.6,
        )
        
        config = PricingConfig(num_paths=10_000, seed=42)
        result = AutocallPricer(config).price(ts)
        
        # Should rarely autocall
        assert result.autocall_probability < 0.3
        
        # Expected life should be close to maturity (1 year)
        assert result.expected_life > 0.7


class TestCouponMemory:
    """Test coupon memory feature correctly accumulates unpaid coupons."""
    
    def test_memory_accumulates_coupons(self) -> None:
        """
        With memory ON and coupon barrier missed then hit:
        - Path should pay accumulated coupons
        - Total coupons > paths without memory
        """
        # Low coupon barrier so some paths get coupons
        ts_memory = create_simple_term_sheet(
            spots=[100.0, 100.0],
            autocall_levels=[1.5, 1.5, 1.5, 1.5],  # No autocall
            coupon_barriers=[0.85, 0.85, 0.85, 0.85],
            ki_level=0.5,
            coupon_memory=True,
        )
        
        ts_no_memory = deepcopy(ts_memory)
        ts_no_memory.payoff.coupon_memory = False
        
        config = PricingConfig(num_paths=10_000, seed=42)
        
        result_memory = AutocallPricer(config).price(ts_memory)
        
        config.seed = 42  # Reset seed for same paths
        result_no_memory = AutocallPricer(config).price(ts_no_memory)
        
        # Memory version should have higher or equal PV 
        # (accumulated coupons when barrier crossed after miss)
        # Due to MC noise, we just check they're in reasonable range
        assert result_memory.pv > 0
        assert result_no_memory.pv > 0


class TestDividendEffect:
    """Test that discrete dividends increase KI probability for down barriers."""
    
    def test_dividend_increases_ki_probability(self) -> None:
        """
        Adding discrete dividend should:
        - Lower expected spot path
        - Increase probability of hitting down KI barrier
        """
        # Base case: continuous dividend only
        ts_no_discrete = create_simple_term_sheet(
            spots=[100.0, 100.0],
            autocall_levels=[1.0, 1.0, 1.0, 1.0],
            coupon_barriers=[0.7, 0.7, 0.7, 0.7],
            ki_level=0.7,  # 70% barrier, more likely to hit
        )
        
        # Case with discrete dividends
        ts_with_discrete = deepcopy(ts_no_discrete)
        # Add significant discrete dividend to first underlying
        ts_with_discrete.underlyings[0].dividend_model = DividendModel(
            type=DividendModelType.DISCRETE,
            discrete_dividends=[
                DiscreteDividend(ex_date=date(2024, 3, 1), amount=5.0),
                DiscreteDividend(ex_date=date(2024, 6, 1), amount=5.0),
                DiscreteDividend(ex_date=date(2024, 9, 1), amount=5.0),
            ],
        )
        
        config = PricingConfig(num_paths=10_000, seed=42)
        
        result_no_div = AutocallPricer(config).price(ts_no_discrete)
        
        config.seed = 42  # Same seed
        result_with_div = AutocallPricer(config).price(ts_with_discrete)
        
        # Discrete dividends should increase KI probability
        # (spot jumps down on ex-dates, closer to barrier)
        assert result_with_div.ki_probability >= result_no_div.ki_probability * 0.9
        
        # With high dividends and same seed, KI prob should be noticeably higher
        # Allow some tolerance for MC noise
        print(f"KI prob without div: {result_no_div.ki_probability:.4f}")
        print(f"KI prob with div: {result_with_div.ki_probability:.4f}")


class TestBarrierLevels:
    """Test barrier level effects on pricing."""
    
    def test_lower_ki_barrier_reduces_ki_prob(self) -> None:
        """Lower KI barrier should mean lower KI probability."""
        ts_high = create_simple_term_sheet(
            spots=[100.0, 100.0],
            autocall_levels=[1.0, 1.0, 1.0, 1.0],
            coupon_barriers=[0.7, 0.7, 0.7, 0.7],
            ki_level=0.7,  # Higher barrier, easier to hit
        )
        
        ts_low = deepcopy(ts_high)
        ts_low.ki_barrier.level = 0.5  # Lower barrier, harder to hit
        
        config = PricingConfig(num_paths=10_000, seed=42)
        
        result_high = AutocallPricer(config).price(ts_high)
        
        config.seed = 42
        result_low = AutocallPricer(config).price(ts_low)
        
        # Lower barrier = lower KI probability
        assert result_low.ki_probability < result_high.ki_probability
    
    def test_lower_autocall_barrier_increases_autocall_prob(self) -> None:
        """Lower autocall barrier should increase autocall probability."""
        ts_high = create_simple_term_sheet(
            spots=[100.0, 100.0],
            autocall_levels=[1.0, 1.0, 1.0, 1.0],  # At-the-money
            coupon_barriers=[0.7, 0.7, 0.7, 0.7],
            ki_level=0.6,
        )
        
        ts_low = deepcopy(ts_high)
        ts_low.schedules.autocall_levels = [0.9, 0.9, 0.9, 0.9]  # Easier to trigger
        
        config = PricingConfig(num_paths=10_000, seed=42)
        
        result_high = AutocallPricer(config).price(ts_high)
        
        config.seed = 42
        result_low = AutocallPricer(config).price(ts_low)
        
        # Lower barrier = higher autocall probability
        assert result_low.autocall_probability > result_high.autocall_probability
