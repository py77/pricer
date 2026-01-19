"""Tests for Pydantic schema validation."""

import pytest
from datetime import date
import json
from pathlib import Path

from pricer.products.schema import (
    TermSheet,
    load_term_sheet,
    validate_term_sheet_json,
    Meta,
    Underlying,
    DividendModel,
    VolModel,
    Schedules,
    KnockInBarrier,
    DividendModelType,
    VolModelType,
    BarrierMonitoringType,
)


class TestDividendModel:
    """Tests for DividendModel validation."""
    
    def test_continuous_requires_yield(self) -> None:
        """Continuous model requires continuous_yield."""
        with pytest.raises(ValueError, match="continuous_yield required"):
            DividendModel(type=DividendModelType.CONTINUOUS)
    
    def test_continuous_valid(self) -> None:
        """Valid continuous dividend model."""
        model = DividendModel(
            type=DividendModelType.CONTINUOUS,
            continuous_yield=0.02
        )
        assert model.continuous_yield == 0.02
    
    def test_discrete_requires_dividends(self) -> None:
        """Discrete model requires discrete_dividends."""
        with pytest.raises(ValueError, match="discrete_dividends required"):
            DividendModel(type=DividendModelType.DISCRETE)


class TestVolModel:
    """Tests for VolModel validation."""
    
    def test_flat_requires_vol(self) -> None:
        """Flat model requires flat_vol."""
        with pytest.raises(ValueError, match="flat_vol required"):
            VolModel(type=VolModelType.FLAT)
    
    def test_flat_valid(self) -> None:
        """Valid flat vol model."""
        model = VolModel(type=VolModelType.FLAT, flat_vol=0.25)
        assert model.flat_vol == 0.25


class TestSchedules:
    """Tests for schedule alignment validation."""
    
    def test_aligned_schedules(self) -> None:
        """Valid aligned schedules."""
        schedules = Schedules(
            observation_dates=[date(2024, 7, 15), date(2025, 1, 15)],
            payment_dates=[date(2024, 7, 17), date(2025, 1, 17)],
            autocall_levels=[1.0, 1.0],
            coupon_barriers=[0.7, 0.7],
            coupon_rates=[0.02, 0.02]
        )
        assert len(schedules.observation_dates) == 2
    
    def test_misaligned_payment_dates(self) -> None:
        """Misaligned payment_dates raises error."""
        with pytest.raises(ValueError, match="payment_dates length"):
            Schedules(
                observation_dates=[date(2024, 7, 15), date(2025, 1, 15)],
                payment_dates=[date(2024, 7, 17)],  # Only 1
                autocall_levels=[1.0, 1.0],
                coupon_barriers=[0.7, 0.7],
                coupon_rates=[0.02, 0.02]
            )
    
    def test_observation_dates_must_increase(self) -> None:
        """Observation dates must be strictly increasing."""
        with pytest.raises(ValueError, match="strictly increasing"):
            Schedules(
                observation_dates=[date(2025, 1, 15), date(2024, 7, 15)],  # Reversed
                payment_dates=[date(2025, 1, 17), date(2024, 7, 17)],
                autocall_levels=[1.0, 1.0],
                coupon_barriers=[0.7, 0.7],
                coupon_rates=[0.02, 0.02]
            )


class TestKnockInBarrier:
    """Tests for barrier validation."""
    
    def test_valid_barrier(self) -> None:
        """Valid barrier level."""
        barrier = KnockInBarrier(level=0.6)
        assert barrier.level == 0.6
        assert barrier.monitoring == BarrierMonitoringType.CONTINUOUS
    
    def test_barrier_out_of_range(self) -> None:
        """Barrier level out of range."""
        with pytest.raises(ValueError):
            KnockInBarrier(level=2.0)
        with pytest.raises(ValueError):
            KnockInBarrier(level=0)


class TestTermSheetLoad:
    """Tests for term sheet loading."""
    
    def test_load_example_termsheet(self) -> None:
        """Load and validate example term sheet."""
        path = Path(__file__).parent.parent / "examples" / "autocall_worstof_continuous_ki.json"
        
        if path.exists():
            ts = load_term_sheet(path)
            
            assert ts.meta.product_id == "AC-WOF-2024-001"
            assert ts.meta.notional == 1_000_000
            assert len(ts.underlyings) == 3
            assert len(ts.schedules.observation_dates) == 6
            assert ts.ki_barrier is not None
            assert ts.ki_barrier.level == 0.6
    
    def test_file_not_found(self) -> None:
        """Missing file raises error."""
        with pytest.raises(FileNotFoundError):
            load_term_sheet("nonexistent.json")
