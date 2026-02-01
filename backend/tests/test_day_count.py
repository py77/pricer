"""Tests for day count conventions."""

import pytest
from datetime import date

from pricer.core.day_count import (
    DayCountConvention,
    day_count_fraction,
    year_fraction_to_days,
)


class TestDayCountFraction:
    """Tests for day_count_fraction function."""
    
    def test_act_360_half_year(self) -> None:
        """Test ACT/360 for roughly half a year."""
        start = date(2024, 1, 1)
        end = date(2024, 7, 1)
        
        result = day_count_fraction(start, end, DayCountConvention.ACT_360)
        
        # 182 days / 360 = 0.5055...
        assert result == pytest.approx(182 / 360, rel=1e-6)
    
    def test_act_365f_full_year(self) -> None:
        """Test ACT/365F for exactly one year."""
        start = date(2024, 1, 1)
        end = date(2025, 1, 1)
        
        result = day_count_fraction(start, end, DayCountConvention.ACT_365F)
        
        # 366 days (leap year) / 365 = 1.00274...
        assert result == pytest.approx(366 / 365, rel=1e-6)
    
    def test_thirty_360_quarter(self) -> None:
        """Test 30/360 for a quarter."""
        start = date(2024, 1, 15)
        end = date(2024, 4, 15)
        
        result = day_count_fraction(start, end, DayCountConvention.THIRTY_360)
        
        # 3 months * 30 days / 360 = 0.25
        assert result == pytest.approx(0.25, rel=1e-6)
    
    def test_same_date(self) -> None:
        """Test that same date returns zero."""
        d = date(2024, 6, 15)
        
        result = day_count_fraction(d, d, DayCountConvention.ACT_360)
        
        assert result == 0.0
    
    def test_end_before_start_raises(self) -> None:
        """Test that end < start raises error."""
        start = date(2024, 6, 15)
        end = date(2024, 1, 1)
        
        with pytest.raises(ValueError):
            day_count_fraction(start, end, DayCountConvention.ACT_360)


class TestYearFractionToDays:
    """Tests for year_fraction_to_days function."""
    
    def test_act_360_one_year(self) -> None:
        """Test converting 1 year to days for ACT/360."""
        result = year_fraction_to_days(1.0, DayCountConvention.ACT_360)
        assert result == 360
    
    def test_act_365f_one_year(self) -> None:
        """Test converting 1 year to days for ACT/365F."""
        result = year_fraction_to_days(1.0, DayCountConvention.ACT_365F)
        assert result == 365
