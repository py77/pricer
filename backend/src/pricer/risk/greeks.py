"""
Greeks calculation via finite difference bumping with Common Random Numbers (CRN).

Implements:
- Delta: per-underlying spot bump (default 1% relative)
- Vega: per-underlying vol bump (default +1 vol point absolute)
- Rho: discount rate bump (default 1bp)
- Central differences for stable Greeks

CRN ensures same random paths for base and bumped scenarios.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, Any, List
from copy import deepcopy
import numpy as np
import logging

from pricer.products.schema import TermSheet, VolModelType
from pricer.pricers.autocall_pricer import AutocallPricer, PricingConfig, PricingResult


logger = logging.getLogger(__name__)


@dataclass
class BumpingConfig:
    """Configuration for Greeks calculation via bumping."""
    
    # Spot bump for delta (relative, e.g., 0.01 = 1%)
    delta_bump: float = 0.01
    
    # Vol bump for vega
    # If vega_bump_relative=False: absolute bump in vol points (e.g., 0.01 = +1 vol point)
    # If vega_bump_relative=True: relative bump (e.g., 0.01 = +1% of current vol)
    vega_bump: float = 0.01
    vega_bump_relative: bool = False
    
    # Rate bump for rho (absolute, e.g., 0.0001 = 1bp)
    rho_bump: float = 0.0001
    
    # Use central differences (up and down bump)
    use_central_diff: bool = True
    
    # Compute optional Greeks
    compute_rho: bool = False
    compute_correlation: bool = False


@dataclass
class GreeksResult:
    """
    Complete Greeks calculation result.
    
    Attributes:
        base_pv: Present value from base case
        base_pv_std_error: Standard error of base PV
        delta: Per-underlying delta (dPV/dSpot * Spot)
        vega: Per-underlying vega (dPV/dVol)
        rho: Rate sensitivity (dPV/dRate)
        diagnostics: Additional diagnostic information
    """
    
    base_pv: float
    base_pv_std_error: float
    
    # Per-underlying Greeks
    delta: Dict[str, float] = field(default_factory=dict)
    delta_pct: Dict[str, float] = field(default_factory=dict)  # Delta as % of notional
    vega: Dict[str, float] = field(default_factory=dict)
    
    # Portfolio-level Greeks
    rho: Optional[float] = None
    
    # Diagnostics
    diagnostics: Dict[str, Any] = field(default_factory=dict)
    
    def print_summary(self, notional: float = 1_000_000) -> None:
        """Print formatted Greeks summary."""
        print("\n" + "=" * 60)
        print("GREEKS REPORT")
        print("=" * 60)
        
        print(f"\n--- BASE CASE ---")
        print(f"  PV:           {self.base_pv:,.2f}")
        print(f"  Std Error:    {self.base_pv_std_error:,.2f}")
        
        if self.delta:
            print(f"\n--- DELTA (1% spot bump) ---")
            print(f"  {'Underlying':<12} {'Delta':>14} {'Delta %':>12}")
            print(f"  {'-'*12} {'-'*14} {'-'*12}")
            for asset, d in self.delta.items():
                d_pct = self.delta_pct.get(asset, d / notional * 100)
                print(f"  {asset:<12} {d:>14,.2f} {d_pct:>11.2f}%")
        
        if self.vega:
            print(f"\n--- VEGA (1 vol point bump) ---")
            print(f"  {'Underlying':<12} {'Vega':>14}")
            print(f"  {'-'*12} {'-'*14}")
            for asset, v in self.vega.items():
                print(f"  {asset:<12} {v:>14,.2f}")
        
        if self.rho is not None:
            print(f"\n--- RHO (1bp rate bump) ---")
            print(f"  Rho:          {self.rho:,.2f}")
        
        if self.diagnostics:
            print(f"\n--- DIAGNOSTICS ---")
            for key, val in self.diagnostics.items():
                if isinstance(val, float):
                    print(f"  {key}: {val:,.4f}")
                else:
                    print(f"  {key}: {val}")
        
        print("=" * 60)


def _bump_spot(term_sheet: TermSheet, asset_id: str, bump_pct: float) -> TermSheet:
    """Create term sheet with bumped spot for one underlying."""
    ts = deepcopy(term_sheet)
    
    for underlying in ts.underlyings:
        if underlying.id == asset_id:
            underlying.spot = underlying.spot * (1.0 + bump_pct)
            break
    
    return ts


def _bump_vol(
    term_sheet: TermSheet, 
    asset_id: str, 
    bump: float,
    relative: bool = False
) -> TermSheet:
    """Create term sheet with bumped vol for one underlying."""
    ts = deepcopy(term_sheet)
    
    for underlying in ts.underlyings:
        if underlying.id == asset_id:
            vol_model = underlying.vol_model
            
            if vol_model.type == VolModelType.FLAT:
                if vol_model.flat_vol is not None:
                    if relative:
                        vol_model.flat_vol = vol_model.flat_vol * (1.0 + bump)
                    else:
                        vol_model.flat_vol = vol_model.flat_vol + bump
            
            elif vol_model.type == VolModelType.PIECEWISE_CONSTANT:
                if vol_model.term_structure:
                    for tenor in vol_model.term_structure:
                        if relative:
                            tenor.vol = tenor.vol * (1.0 + bump)
                        else:
                            tenor.vol = tenor.vol + bump
            break
    
    return ts


def _bump_rate(term_sheet: TermSheet, bump: float) -> TermSheet:
    """Create term sheet with bumped discount rate."""
    ts = deepcopy(term_sheet)
    
    if ts.discount_curve.flat_rate is not None:
        ts.discount_curve.flat_rate = ts.discount_curve.flat_rate + bump
    
    return ts


def compute_greeks(
    term_sheet: TermSheet,
    pricing_config: PricingConfig,
    bump_config: Optional[BumpingConfig] = None
) -> GreeksResult:
    """
    Compute Greeks via finite difference bumping with CRN.
    
    Uses Common Random Numbers (same seed) for base and bumped scenarios
    to minimize noise in Greek estimates.
    
    Args:
        term_sheet: Product term sheet
        pricing_config: Configuration for MC pricer (paths, seed, etc.)
        bump_config: Configuration for Greek bumping
        
    Returns:
        GreeksResult with all computed Greeks
    """
    bump_config = bump_config or BumpingConfig()
    
    # Ensure we have a seed for CRN
    if pricing_config.seed is None:
        pricing_config.seed = 42
        logger.info("No seed provided, using default seed=42 for CRN")
    
    base_seed = pricing_config.seed
    
    # Get asset list
    asset_ids = [u.id for u in term_sheet.underlyings]
    notional = term_sheet.meta.notional
    
    # Create pricer
    pricer = AutocallPricer(pricing_config)
    
    # === BASE CASE ===
    pricer.set_seed(base_seed)
    base_result = pricer.price(term_sheet)
    base_pv = base_result.pv
    
    diagnostics: Dict[str, Any] = {
        "base_seed": base_seed,
        "num_paths": pricing_config.num_paths,
        "num_bump_scenarios": 0,
    }
    
    # === DELTA: per-underlying spot bump ===
    delta: Dict[str, float] = {}
    delta_pct: Dict[str, float] = {}
    
    for asset_id in asset_ids:
        if bump_config.use_central_diff:
            # Central difference: (PV_up - PV_down) / (2 * bump)
            ts_up = _bump_spot(term_sheet, asset_id, bump_config.delta_bump)
            ts_down = _bump_spot(term_sheet, asset_id, -bump_config.delta_bump)
            
            pricer.set_seed(base_seed)
            pv_up = pricer.price(ts_up).pv
            
            pricer.set_seed(base_seed)
            pv_down = pricer.price(ts_down).pv
            
            # Delta = dPV / d(Spot/Spot0) = dPV / (2 * bump)
            # This is the dollar delta for a 1% spot move
            raw_delta = (pv_up - pv_down) / (2.0 * bump_config.delta_bump)
            
            diagnostics["num_bump_scenarios"] += 2
        else:
            # Forward difference: (PV_up - PV_base) / bump
            ts_up = _bump_spot(term_sheet, asset_id, bump_config.delta_bump)
            
            pricer.set_seed(base_seed)
            pv_up = pricer.price(ts_up).pv
            
            raw_delta = (pv_up - base_pv) / bump_config.delta_bump
            
            diagnostics["num_bump_scenarios"] += 1
        
        delta[asset_id] = raw_delta
        delta_pct[asset_id] = raw_delta / notional * 100.0
    
    # === VEGA: per-underlying vol bump ===
    vega: Dict[str, float] = {}
    
    for asset_id in asset_ids:
        if bump_config.use_central_diff:
            ts_up = _bump_vol(
                term_sheet, asset_id, 
                bump_config.vega_bump, 
                relative=bump_config.vega_bump_relative
            )
            ts_down = _bump_vol(
                term_sheet, asset_id, 
                -bump_config.vega_bump,
                relative=bump_config.vega_bump_relative
            )
            
            pricer.set_seed(base_seed)
            pv_up = pricer.price(ts_up).pv
            
            pricer.set_seed(base_seed)
            pv_down = pricer.price(ts_down).pv
            
            # Vega = dPV / dVol (for 1 vol point = 0.01 bump)
            raw_vega = (pv_up - pv_down) / (2.0 * bump_config.vega_bump)
            
            diagnostics["num_bump_scenarios"] += 2
        else:
            ts_up = _bump_vol(
                term_sheet, asset_id,
                bump_config.vega_bump,
                relative=bump_config.vega_bump_relative
            )
            
            pricer.set_seed(base_seed)
            pv_up = pricer.price(ts_up).pv
            
            raw_vega = (pv_up - base_pv) / bump_config.vega_bump
            
            diagnostics["num_bump_scenarios"] += 1
        
        vega[asset_id] = raw_vega
    
    # === RHO: rate bump (optional) ===
    rho: Optional[float] = None
    
    if bump_config.compute_rho:
        if bump_config.use_central_diff:
            ts_up = _bump_rate(term_sheet, bump_config.rho_bump)
            ts_down = _bump_rate(term_sheet, -bump_config.rho_bump)
            
            pricer.set_seed(base_seed)
            pv_up = pricer.price(ts_up).pv
            
            pricer.set_seed(base_seed)
            pv_down = pricer.price(ts_down).pv
            
            # Rho = dPV / dRate (for 1bp = 0.0001 bump)
            rho = (pv_up - pv_down) / (2.0 * bump_config.rho_bump)
            
            diagnostics["num_bump_scenarios"] += 2
        else:
            ts_up = _bump_rate(term_sheet, bump_config.rho_bump)
            
            pricer.set_seed(base_seed)
            pv_up = pricer.price(ts_up).pv
            
            rho = (pv_up - base_pv) / bump_config.rho_bump
            
            diagnostics["num_bump_scenarios"] += 1
    
    return GreeksResult(
        base_pv=base_pv,
        base_pv_std_error=base_result.pv_std_error,
        delta=delta,
        delta_pct=delta_pct,
        vega=vega,
        rho=rho,
        diagnostics=diagnostics,
    )


class GreeksCalculator:
    """
    Calculator for Greeks with persistent configuration.
    
    Wraps compute_greeks with cached configuration.
    """
    
    def __init__(
        self,
        pricing_config: Optional[PricingConfig] = None,
        bump_config: Optional[BumpingConfig] = None
    ) -> None:
        self.pricing_config = pricing_config or PricingConfig()
        self.bump_config = bump_config or BumpingConfig()
    
    def calculate(self, term_sheet: TermSheet) -> GreeksResult:
        """Calculate all configured Greeks for a term sheet."""
        return compute_greeks(
            term_sheet,
            self.pricing_config,
            self.bump_config
        )
    
    def set_seed(self, seed: int) -> None:
        """Set random seed for CRN."""
        self.pricing_config.seed = seed
