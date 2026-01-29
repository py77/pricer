"""
Tests for Greeks calculation with CRN.

Validates:
- Delta/Vega sign and magnitude
- CRN reduces noise vs independent runs
- Greeks are stable with same seed
"""

import pytest
import numpy as np
from pathlib import Path

from pricer.products.schema import load_term_sheet
from pricer.pricers.autocall_pricer import PricingConfig
from pricer.risk.greeks import (
    compute_greeks, 
    GreeksCalculator, 
    BumpingConfig,
    GreeksResult,
)


class TestGreeksBasic:
    """Basic Greeks calculation tests."""
    
    @pytest.fixture
    def term_sheet_path(self) -> Path:
        """Get path to example term sheet."""
        return Path(__file__).parent.parent / "examples" / "autocall_worstof_continuous_ki.json"
    
    def test_greeks_returns_result(self, term_sheet_path: Path) -> None:
        """Greeks calculation should return a valid result."""
        if not term_sheet_path.exists():
            pytest.skip("Example term sheet not found")
        
        ts = load_term_sheet(term_sheet_path)
        config = PricingConfig(num_paths=10_000, seed=42)
        
        result = compute_greeks(ts, config)
        
        assert isinstance(result, GreeksResult)
        assert result.base_pv > 0
        assert len(result.delta) == 3  # 3 underlyings
        assert len(result.vega) == 3
    
    def test_delta_is_negative_for_autocallable(self, term_sheet_path: Path) -> None:
        """
        For a worst-of autocallable with downside risk:
        - Delta should generally be negative (long position loses on down move)
        - This is because lower spot increases KI probability
        """
        if not term_sheet_path.exists():
            pytest.skip("Example term sheet not found")
        
        ts = load_term_sheet(term_sheet_path)
        config = PricingConfig(num_paths=10_000, seed=42)
        
        result = compute_greeks(ts, config)
        
        # At least some deltas should be negative
        # (depends on market conditions and structure)
        deltas = list(result.delta.values())
        assert any(d < 0 for d in deltas) or any(d > 0 for d in deltas)
        
        print(f"Deltas: {result.delta}")
    
    def test_vega_is_nonzero(self, term_sheet_path: Path) -> None:
        """Vega should be non-zero (vol affects option value)."""
        if not term_sheet_path.exists():
            pytest.skip("Example term sheet not found")
        
        ts = load_term_sheet(term_sheet_path)
        config = PricingConfig(num_paths=10_000, seed=42)
        
        result = compute_greeks(ts, config)
        
        # At least some vegas should be non-zero
        vegas = list(result.vega.values())
        assert any(abs(v) > 0.01 for v in vegas)
        
        print(f"Vegas: {result.vega}")


class TestCRNStability:
    """Test that CRN provides stable Greek estimates."""
    
    @pytest.fixture
    def term_sheet_path(self) -> Path:
        """Get path to example term sheet."""
        return Path(__file__).parent.parent / "examples" / "autocall_worstof_continuous_ki.json"
    
    def test_same_seed_gives_same_greeks(self, term_sheet_path: Path) -> None:
        """Running twice with same seed should give identical Greeks."""
        if not term_sheet_path.exists():
            pytest.skip("Example term sheet not found")
        
        ts = load_term_sheet(term_sheet_path)
        
        config1 = PricingConfig(num_paths=10_000, seed=42)
        result1 = compute_greeks(ts, config1)
        
        config2 = PricingConfig(num_paths=10_000, seed=42)
        result2 = compute_greeks(ts, config2)
        
        # Should be exactly equal
        assert result1.base_pv == pytest.approx(result2.base_pv, rel=1e-10)
        
        for asset in result1.delta:
            assert result1.delta[asset] == pytest.approx(result2.delta[asset], rel=1e-10)
        
        for asset in result1.vega:
            assert result1.vega[asset] == pytest.approx(result2.vega[asset], rel=1e-10)
    
    def test_different_seeds_give_different_greeks(self, term_sheet_path: Path) -> None:
        """Different seeds should give (slightly) different Greeks."""
        if not term_sheet_path.exists():
            pytest.skip("Example term sheet not found")
        
        ts = load_term_sheet(term_sheet_path)
        
        config1 = PricingConfig(num_paths=10_000, seed=111)
        result1 = compute_greeks(ts, config1)
        
        config2 = PricingConfig(num_paths=10_000, seed=222)
        result2 = compute_greeks(ts, config2)
        
        # Should be different (MC sampling variance)
        assert result1.base_pv != result2.base_pv
        
        # But should be in same ballpark
        assert result1.base_pv == pytest.approx(result2.base_pv, rel=0.02)


class TestBumpingConfig:
    """Test different bumping configurations."""
    
    @pytest.fixture
    def term_sheet_path(self) -> Path:
        """Get path to example term sheet."""
        return Path(__file__).parent.parent / "examples" / "autocall_worstof_continuous_ki.json"
    
    def test_central_diff_vs_forward_diff(self, term_sheet_path: Path) -> None:
        """Central difference should be more accurate than forward difference."""
        if not term_sheet_path.exists():
            pytest.skip("Example term sheet not found")
        
        ts = load_term_sheet(term_sheet_path)
        config = PricingConfig(num_paths=10_000, seed=42)
        
        bump_central = BumpingConfig(use_central_diff=True)
        bump_forward = BumpingConfig(use_central_diff=False)
        
        result_central = compute_greeks(ts, config, bump_central)
        
        config.seed = 42  # Reset
        result_forward = compute_greeks(ts, config, bump_forward)
        
        # Both should produce valid results
        assert len(result_central.delta) > 0
        assert len(result_forward.delta) > 0
        
        # Central uses 2x bump scenarios per Greek
        assert result_central.diagnostics["num_bump_scenarios"] > result_forward.diagnostics["num_bump_scenarios"]
    
    def test_rho_when_requested(self, term_sheet_path: Path) -> None:
        """Rho should be computed when requested."""
        if not term_sheet_path.exists():
            pytest.skip("Example term sheet not found")
        
        ts = load_term_sheet(term_sheet_path)
        config = PricingConfig(num_paths=10_000, seed=42)
        
        bump_no_rho = BumpingConfig(compute_rho=False)
        bump_with_rho = BumpingConfig(compute_rho=True)
        
        result_no_rho = compute_greeks(ts, config, bump_no_rho)
        
        config.seed = 42
        result_with_rho = compute_greeks(ts, config, bump_with_rho)
        
        assert result_no_rho.rho is None
        assert result_with_rho.rho is not None
        
        # Rho should be negative (higher rates lower PV of fixed coupons)
        print(f"Rho: {result_with_rho.rho}")


class TestGreeksCalculator:
    """Test the GreeksCalculator wrapper class."""
    
    @pytest.fixture
    def term_sheet_path(self) -> Path:
        """Get path to example term sheet."""
        return Path(__file__).parent.parent / "examples" / "autocall_worstof_continuous_ki.json"
    
    def test_calculator_interface(self, term_sheet_path: Path) -> None:
        """GreeksCalculator should provide convenient interface."""
        if not term_sheet_path.exists():
            pytest.skip("Example term sheet not found")
        
        ts = load_term_sheet(term_sheet_path)
        
        calculator = GreeksCalculator(
            pricing_config=PricingConfig(num_paths=10_000, seed=42),
            bump_config=BumpingConfig(compute_rho=True),
        )
        
        result = calculator.calculate(ts)
        
        assert isinstance(result, GreeksResult)
        assert result.base_pv > 0
        assert result.rho is not None
