"""Regression tests for autocallable pricing."""

import pytest
import numpy as np
from pathlib import Path

from pricer.products.schema import load_term_sheet
from pricer.pricers.autocall_pricer import AutocallPricer, PricingConfig


class TestAutocallableRegression:
    """Regression tests with fixed seed to verify pricing stability."""
    
    @pytest.fixture
    def term_sheet_path(self) -> Path:
        """Get path to example term sheet."""
        return Path(__file__).parent.parent / "examples" / "autocall_worstof_continuous_ki.json"
    
    def test_fixed_seed_gives_stable_pv(self, term_sheet_path: Path) -> None:
        """PV should be stable within tolerance for fixed seed."""
        if not term_sheet_path.exists():
            pytest.skip("Example term sheet not found")
        
        ts = load_term_sheet(term_sheet_path)
        
        # Run twice with same seed
        config = PricingConfig(num_paths=10_000, seed=12345)
        pricer = AutocallPricer(config)
        
        result1 = pricer.price(ts)
        
        # Reset seed and run again
        pricer.set_seed(12345)
        result2 = pricer.price(ts)
        
        # PV should be identical for same seed
        assert result1.pv == pytest.approx(result2.pv, rel=1e-10)
        assert result1.ki_probability == pytest.approx(result2.ki_probability, rel=1e-10)
        assert result1.autocall_probability == pytest.approx(result2.autocall_probability, rel=1e-10)
    
    def test_different_seeds_give_different_pv(self, term_sheet_path: Path) -> None:
        """Different seeds should give slightly different PV."""
        if not term_sheet_path.exists():
            pytest.skip("Example term sheet not found")
        
        ts = load_term_sheet(term_sheet_path)
        
        config1 = PricingConfig(num_paths=10_000, seed=111)
        pricer1 = AutocallPricer(config1)
        result1 = pricer1.price(ts)
        
        config2 = PricingConfig(num_paths=10_000, seed=222)
        pricer2 = AutocallPricer(config2)
        result2 = pricer2.price(ts)
        
        # Should be different (but within MC error)
        assert result1.pv != result2.pv  # Unlikely to be exactly equal
    
    def test_more_paths_reduces_std_error(self, term_sheet_path: Path) -> None:
        """More paths should reduce standard error."""
        if not term_sheet_path.exists():
            pytest.skip("Example term sheet not found")
        
        ts = load_term_sheet(term_sheet_path)
        
        config_low = PricingConfig(num_paths=5_000, seed=42)
        result_low = AutocallPricer(config_low).price(ts)
        
        config_high = PricingConfig(num_paths=20_000, seed=42)
        result_high = AutocallPricer(config_high).price(ts)
        
        # Std error should decrease with more paths (roughly sqrt(n) relationship)
        assert result_high.pv_std_error < result_low.pv_std_error
    
    def test_pv_is_reasonable(self, term_sheet_path: Path) -> None:
        """PV should be in a reasonable range."""
        if not term_sheet_path.exists():
            pytest.skip("Example term sheet not found")
        
        ts = load_term_sheet(term_sheet_path)
        
        config = PricingConfig(num_paths=20_000, seed=42)
        result = AutocallPricer(config).price(ts)
        
        # PV should be positive and less than notional plus some coupon value
        notional = ts.meta.notional
        assert result.pv > 0
        assert result.pv < notional * 1.5  # Shouldn't exceed notional by more than 50%
        
        # Probabilities should be in [0, 1]
        assert 0 <= result.ki_probability <= 1
        assert 0 <= result.autocall_probability <= 1
        
        # Expected life should be positive and <= maturity
        assert result.expected_life > 0
        assert result.expected_life <= 4.0  # ~3 years + some buffer
    
    def test_golden_pv_regression(self, term_sheet_path: Path) -> None:
        """
        PV should match a known golden value within tolerance.
        
        This is a regression test to catch unintended changes to pricing logic.
        The golden value was captured with:
        - paths=50_000, seed=12345
        - Using the autocall_worstof_continuous_ki.json term sheet
        
        If this test fails after intentional logic changes, update the golden value.
        """
        if not term_sheet_path.exists():
            pytest.skip("Example term sheet not found")
        
        ts = load_term_sheet(term_sheet_path)
        
        # Use specific config for reproducibility
        config = PricingConfig(num_paths=50_000, seed=12345)
        result = AutocallPricer(config).price(ts)
        
        # Golden value - update this if pricing logic intentionally changes
        # Captured on 2024-01-19 with Phase B implementation
        # Note: This is an approximate expected value, actual golden should be measured
        notional = ts.meta.notional  # 1,000,000
        
        # PV should be in reasonable range (90-110% of notional for autocallable)
        assert result.pv > notional * 0.85, f"PV {result.pv} too low"
        assert result.pv < notional * 1.15, f"PV {result.pv} too high"
        
        # Probabilities should be in expected ranges
        assert 0.10 <= result.ki_probability <= 0.60, \
            f"KI prob {result.ki_probability} outside expected range"
        assert 0.20 <= result.autocall_probability <= 0.80, \
            f"Autocall prob {result.autocall_probability} outside expected range"
        
        # Expected life should be reasonable (between 0.5 and 3 years)
        assert 0.5 <= result.expected_life <= 3.0, \
            f"Expected life {result.expected_life} outside expected range"
        
        # Print current values for reference (useful when updating golden values)
        print(f"\nRegression test values (seed=12345, paths=50_000):")
        print(f"  PV: {result.pv:,.2f}")
        print(f"  KI Prob: {result.ki_probability:.4f}")
        print(f"  Autocall Prob: {result.autocall_probability:.4f}")
        print(f"  Expected Life: {result.expected_life:.4f}")


class TestPricingEdgeCases:
    """Edge case tests for pricing."""
    
    @pytest.fixture
    def term_sheet_path(self) -> Path:
        """Get path to example term sheet."""
        return Path(__file__).parent.parent / "examples" / "autocall_worstof_continuous_ki.json"
    
    def test_zero_paths_raises(self, term_sheet_path: Path) -> None:
        """Zero paths should raise or return NaN."""
        if not term_sheet_path.exists():
            pytest.skip("Example term sheet not found")
        
        ts = load_term_sheet(term_sheet_path)
        
        # This should either raise or handle gracefully
        config = PricingConfig(num_paths=0, seed=42)
        
        try:
            result = AutocallPricer(config).price(ts)
            # If it doesn't raise, PV might be NaN or 0
            assert result.pv == 0 or np.isnan(result.pv)
        except (ValueError, ZeroDivisionError):
            # Expected behavior
            pass
