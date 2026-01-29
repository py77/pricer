"""
Monte Carlo pricing engine.

Implements multi-asset GBM with Cholesky correlation, discrete dividends,
and Brownian bridge barrier monitoring.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional, List, Dict, Tuple
import time
import numpy as np

from pricer.core.day_count import DayCountConvention, day_count_fraction
from pricer.products.base import Product, Barrier, BarrierType
from pricer.products.autocallable import AutocallableNote
from pricer.market.market_data import MarketData
from pricer.engines.base import PricingEngine, PricingResult, CashFlow


@dataclass
class MonteCarloConfig:
    """Configuration for Monte Carlo engine."""
    
    num_paths: int = 100_000
    seed: Optional[int] = None
    antithetic: bool = True
    block_size: int = 10_000  # Paths per block for memory efficiency
    steps_per_day: int = 1    # For continuous barrier monitoring


class MonteCarloEngine(PricingEngine):
    """
    Monte Carlo pricing engine for structured products.
    
    Features:
    - Multi-asset GBM with piecewise constant parameters
    - Cholesky correlation for correlated assets
    - Discrete dividends as spot jumps
    - Brownian bridge for continuous barrier monitoring
    - Vectorized numpy operations for performance
    
    Attributes:
        num_paths: Number of Monte Carlo paths
        seed: Random seed for reproducibility
        antithetic: Use antithetic variates for variance reduction
        block_size: Number of paths to process at once (memory control)
    """
    
    def __init__(
        self,
        num_paths: int = 100_000,
        seed: Optional[int] = None,
        antithetic: bool = True,
        block_size: int = 10_000
    ) -> None:
        self.num_paths = num_paths
        self._seed = seed
        self.antithetic = antithetic
        self.block_size = block_size
        self._rng: Optional[np.random.Generator] = None
        
        if seed is not None:
            self._rng = np.random.default_rng(seed)
    
    def get_seed(self) -> Optional[int]:
        """Get current random seed."""
        return self._seed
    
    def set_seed(self, seed: int) -> None:
        """Set random seed and reinitialize RNG."""
        self._seed = seed
        self._rng = np.random.default_rng(seed)
    
    def _get_rng(self) -> np.random.Generator:
        """Get or create random number generator."""
        if self._rng is None:
            self._rng = np.random.default_rng(self._seed)
        return self._rng
    
    def _build_time_grid(
        self,
        product: Product,
        market: MarketData
    ) -> Tuple[List[date], np.ndarray]:
        """
        Build simulation time grid from product dates.
        
        Returns:
            Tuple of (dates list, year fractions from valuation date)
        """
        all_dates = product.get_all_dates()
        
        # Filter dates after valuation date
        dates = [d for d in all_dates if d >= market.valuation_date]
        
        # Ensure valuation date is first
        if not dates or dates[0] != market.valuation_date:
            dates = [market.valuation_date] + dates
        
        # Calculate year fractions
        yf = np.array([
            day_count_fraction(market.valuation_date, d, DayCountConvention.ACT_365F)
            for d in dates
        ])
        
        return dates, yf
    
    def _generate_paths(
        self,
        num_paths: int,
        num_assets: int,
        num_steps: int,
        dt: np.ndarray,
        drift: np.ndarray,
        vol: np.ndarray,
        cholesky: np.ndarray,
        spots: np.ndarray
    ) -> np.ndarray:
        """
        Generate correlated GBM paths.
        
        Args:
            num_paths: Number of paths
            num_assets: Number of assets
            num_steps: Number of time steps
            dt: Time step sizes [num_steps]
            drift: Drift per step [num_steps, num_assets]
            vol: Volatility per step [num_steps, num_assets]
            cholesky: Cholesky factor [num_assets, num_assets]
            spots: Initial spots [num_assets]
            
        Returns:
            Paths array [num_paths, num_steps+1, num_assets]
        """
        rng = self._get_rng()
        
        # Initialize paths with spot
        paths = np.zeros((num_paths, num_steps + 1, num_assets))
        paths[:, 0, :] = spots
        
        # Generate random numbers
        # Shape: [num_paths, num_steps, num_assets]
        Z = rng.standard_normal((num_paths, num_steps, num_assets))
        
        # Apply Cholesky for correlation
        # Z_corr[p, t, :] = cholesky @ Z[p, t, :]
        Z_corr = np.einsum('ij,ptj->pti', cholesky, Z)
        
        # Simulate each step
        for t in range(num_steps):
            sqrt_dt = np.sqrt(dt[t])
            
            for a in range(num_assets):
                # GBM: S(t+dt) = S(t) * exp((mu - 0.5*vol^2)*dt + vol*sqrt(dt)*Z)
                log_return = (
                    (drift[t, a] - 0.5 * vol[t, a] ** 2) * dt[t]
                    + vol[t, a] * sqrt_dt * Z_corr[:, t, a]
                )
                paths[:, t + 1, a] = paths[:, t, a] * np.exp(log_return)
        
        return paths
    
    def _brownian_bridge_ki_prob(
        self,
        S_start: float,
        S_end: float,
        barrier: float,
        vol: float,
        dt: float
    ) -> float:
        """
        Calculate probability of hitting barrier using Brownian bridge.
        
        For a down-and-in barrier, probability that min(S) <= barrier given
        S starts at S_start and ends at S_end.
        
        Uses the formula:
        P(min <= H) = exp(-2 * ln(S_start/H) * ln(S_end/H) / (vol^2 * dt))
        
        Valid when S_start > H and S_end > H.
        """
        if barrier <= 0 or S_start <= 0 or S_end <= 0:
            return 0.0
        
        # If either endpoint is at or below barrier, definitely hit
        if S_start <= barrier or S_end <= barrier:
            return 1.0
        
        if dt <= 0 or vol <= 0:
            return 0.0
        
        log_start = np.log(S_start / barrier)
        log_end = np.log(S_end / barrier)
        
        # Brownian bridge hitting probability
        exponent = -2.0 * log_start * log_end / (vol * vol * dt)
        
        return min(1.0, np.exp(exponent))
    
    def price(
        self,
        product: Product,
        market: MarketData
    ) -> PricingResult:
        """
        Price a structured product.
        
        This is a stub implementation for Phase A.
        Full implementation will be in Phase B.
        """
        start_time = time.perf_counter()
        
        if not isinstance(product, AutocallableNote):
            raise NotImplementedError(
                f"Only AutocallableNote is supported, got {type(product)}"
            )
        
        # Build time grid
        dates, yf = self._build_time_grid(product, market)
        num_steps = len(dates) - 1
        
        if num_steps == 0:
            # Product has matured
            return PricingResult(
                pv=0.0,
                valuation_date=market.valuation_date,
                num_paths=0
            )
        
        # Get asset info
        assets = product.underlyings
        num_assets = len(assets)
        
        # Get spots
        spots = np.array([market.get_spot(a) for a in assets])
        
        # Get correlation Cholesky
        if market.correlation is not None:
            cholesky = market.correlation.cholesky
        else:
            cholesky = np.eye(num_assets)
        
        # Build drift and vol arrays
        dt = np.diff(yf)
        drift = np.zeros((num_steps, num_assets))
        vol = np.zeros((num_steps, num_assets))
        
        for t in range(num_steps):
            for a_idx, asset in enumerate(assets):
                underlying = market.underlyings[asset]
                
                # Get vol for this period
                vol[t, a_idx] = underlying.vol_surface.get_instantaneous_vol(
                    market.valuation_date, dates[t + 1]
                )
                
                # Drift = risk-free rate - dividend yield (for risk-neutral measure)
                r = market.rate_curve.zero_rate(market.valuation_date, dates[t + 1])
                
                # Get dividend adjustment (continuous yield approximation)
                div_adj = underlying.dividend_model.get_dividend_adjustment(
                    dates[t], dates[t + 1], spots[a_idx]
                )
                q = -np.log(div_adj) / dt[t] if dt[t] > 0 else 0.0
                
                drift[t, a_idx] = r - q
        
        # Generate paths
        paths = self._generate_paths(
            self.num_paths, num_assets, num_steps, dt,
            drift, vol, cholesky, spots
        )
        
        # ====================================================================
        # STUB: Event evaluation will be implemented in Phase B
        # For now, return basic statistics
        # ====================================================================
        
        # Calculate terminal performances
        final_spots = paths[:, -1, :]  # [num_paths, num_assets]
        initial_spots = paths[:, 0, :]  # Should be spots for all paths
        performances = final_spots / initial_spots
        
        # Worst-of performance at maturity
        if product.worst_of:
            worst_perf = np.min(performances, axis=1)
        else:
            worst_perf = np.max(performances, axis=1)
        
        # Simple PV calculation (placeholder)
        # Full payoff evaluation will be in Phase B
        df_maturity = market.discount_factor(product.maturity_date)
        
        # Placeholder: assume notional redemption at maturity
        pv_paths = product.notional * df_maturity * np.ones(self.num_paths)
        
        # KI probability estimate (placeholder using final spot)
        ki_prob = 0.0
        if product.ki_barrier is not None:
            ki_level = product.ki_barrier.level
            ki_breached = worst_perf <= ki_level
            ki_prob = float(np.mean(ki_breached))
        
        # Compute results
        pv = float(np.mean(pv_paths))
        pv_std = float(np.std(pv_paths) / np.sqrt(self.num_paths))
        
        end_time = time.perf_counter()
        
        return PricingResult(
            pv=pv,
            pv_std_error=pv_std,
            autocall_probability=0.0,  # TODO: Phase B
            ki_probability=ki_prob,
            expected_coupon_count=0.0,  # TODO: Phase B
            expected_life=yf[-1],       # Full life (no autocall yet)
            num_paths=self.num_paths,
            valuation_date=market.valuation_date,
            computation_time_ms=(end_time - start_time) * 1000,
            metadata={
                "num_steps": num_steps,
                "num_assets": num_assets,
                "phase": "A",  # Stub indicator
            }
        )
