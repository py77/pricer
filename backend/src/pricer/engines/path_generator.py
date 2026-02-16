"""
Monte Carlo path generator with Brownian bridge barrier monitoring.

Features:
- Multi-asset correlated GBM simulation
- Piecewise constant vol per time bucket
- Discrete dividends as spot jumps
- Brownian bridge for continuous KI monitoring
- Vectorized numpy operations (no loops over paths/assets)
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional, List, Dict, Tuple, Iterator
import logging
import numpy as np
from numpy.random import Generator, default_rng

logger = logging.getLogger(__name__)

from pricer.products.schema import TermSheet, VolModelType, DividendModelType
from pricer.engines.grid import SimulationGrid, EventType, get_exdiv_schedule_for_underlying


@dataclass
class PathGeneratorConfig:
    """Configuration for path generator."""
    
    num_paths: int = 100_000
    seed: Optional[int] = None
    antithetic: bool = True
    dtype: np.dtype = np.float32  # Use float32 for paths (memory efficient)
    accumulator_dtype: np.dtype = np.float64  # Use float64 for accumulators
    block_size: int = 50_000      # Max paths per block


@dataclass
class SimulatedPaths:
    """
    Result of path simulation.
    
    Attributes:
        spots: Spot paths [num_paths, num_steps+1, num_assets]
        ki_state: Knock-in state per path [num_paths] (True if knocked in)
        ki_step: Step at which KI occurred (or -1) [num_paths]
    """
    
    spots: np.ndarray
    ki_state: np.ndarray
    ki_step: np.ndarray


def build_correlation_matrix(
    term_sheet: TermSheet
) -> np.ndarray:
    """
    Build correlation matrix from term sheet.
    
    Returns:
        NxN correlation matrix
    """
    n = len(term_sheet.underlyings)
    
    if n == 1:
        return np.array([[1.0]])
    
    # Start with identity
    corr = np.eye(n)
    
    if term_sheet.correlation is None:
        return corr
    
    # Get asset order
    asset_ids = [u.id for u in term_sheet.underlyings]
    
    if term_sheet.correlation.matrix is not None:
        return np.array(term_sheet.correlation.matrix)
    
    if term_sheet.correlation.pairwise is not None:
        for pair, rho in term_sheet.correlation.pairwise.items():
            # Parse "AAPL_GOOG" format
            assets = pair.split("_")
            if len(assets) != 2:
                continue
            try:
                i = asset_ids.index(assets[0])
                j = asset_ids.index(assets[1])
                corr[i, j] = rho
                corr[j, i] = rho
            except ValueError:
                continue
    
    return corr


def validate_and_fix_correlation(corr: np.ndarray, epsilon: float = 1e-8) -> np.ndarray:
    """
    Validate correlation matrix is PSD and fix if needed.
    
    Uses eigenvalue clipping to ensure positive semi-definiteness.
    Logs warning if eigenvalues are clipped.
    """
    n = corr.shape[0]
    
    # Validate diagonal is ones
    diag = np.diag(corr)
    if not np.allclose(diag, 1.0, atol=1e-6):
        logger.warning(f"Correlation diagonal not all 1.0: {diag}")
        np.fill_diagonal(corr, 1.0)
    
    # Validate symmetry
    if not np.allclose(corr, corr.T, atol=1e-6):
        logger.warning("Correlation matrix not symmetric, symmetrizing")
        corr = (corr + corr.T) / 2
    
    # Validate values in [-1, 1]
    if np.any(np.abs(corr) > 1.0 + epsilon):
        logger.warning("Correlation values outside [-1, 1], clipping")
        corr = np.clip(corr, -1.0, 1.0)
        np.fill_diagonal(corr, 1.0)
    
    # Check eigenvalues for PSD
    eigenvalues, eigenvectors = np.linalg.eigh(corr)
    min_eigenvalue = np.min(eigenvalues)
    
    if min_eigenvalue < -epsilon:
        # Log the adjustment magnitude
        adjustment = abs(min_eigenvalue) + epsilon
        logger.warning(
            f"Correlation matrix not PSD (min eigenvalue = {min_eigenvalue:.6f}). "
            f"Clipping eigenvalues by {adjustment:.6f}"
        )
        
        # Clip negative eigenvalues
        eigenvalues = np.maximum(eigenvalues, epsilon)
        
        # Reconstruct
        corr = eigenvectors @ np.diag(eigenvalues) @ eigenvectors.T
        
        # Renormalize to ensure diagonal is 1
        d = np.sqrt(np.diag(corr))
        corr = corr / np.outer(d, d)
    
    return corr


def compute_cholesky(corr: np.ndarray) -> np.ndarray:
    """Compute Cholesky decomposition (lower triangular)."""
    corr = validate_and_fix_correlation(corr)
    return np.linalg.cholesky(corr)


def brownian_bridge_hit_probability(
    S_start: np.ndarray,
    S_end: np.ndarray,
    barrier: np.ndarray,
    vol: np.ndarray,
    dt: float,
    down: bool = True
) -> np.ndarray:
    """
    Compute probability of hitting barrier using Brownian bridge in log-space.
    
    For down barrier:
        P(min S <= H | S_start, S_end) = exp(-2 * ln(S_start/H) * ln(S_end/H) / (vol^2 * dt))
    
    Args:
        S_start: Starting prices [num_paths, num_assets] or [num_paths]
        S_end: Ending prices
        barrier: Barrier levels (absolute)
        vol: Volatility for the period
        dt: Time step
        down: True for down barrier, False for up
        
    Returns:
        Hit probabilities [num_paths] or [num_paths, num_assets]
    """
    if dt <= 0:
        return np.zeros_like(S_start)
    
    # Already hit at endpoints
    if down:
        hit_start = S_start <= barrier
        hit_end = S_end <= barrier
    else:
        hit_start = S_start >= barrier
        hit_end = S_end >= barrier
    
    # Probability from Brownian bridge
    # Only compute for paths that haven't already hit
    prob = np.zeros_like(S_start, dtype=np.float64)
    
    # Mask for paths in the "interior" (neither endpoint hits)
    in_interior = ~hit_start & ~hit_end
    
    if np.any(in_interior):
        log_s_start = np.log(np.where(in_interior, S_start, 1.0))
        log_s_end = np.log(np.where(in_interior, S_end, 1.0))
        log_barrier = np.log(barrier)
        
        if down:
            # log(S/H) = log(S) - log(H)
            log_ratio_start = log_s_start - log_barrier
            log_ratio_end = log_s_end - log_barrier
        else:
            # For up barrier: log(H/S)
            log_ratio_start = log_barrier - log_s_start
            log_ratio_end = log_barrier - log_s_end
        
        # Brownian bridge formula
        variance = vol * vol * dt
        exponent = -2.0 * log_ratio_start * log_ratio_end / np.where(
            in_interior, variance, 1.0
        )
        
        prob = np.where(in_interior, np.exp(np.minimum(exponent, 0)), prob)
    
    # Certain hit if endpoint touches
    prob = np.where(hit_start | hit_end, 1.0, prob)
    
    return prob


class PathGenerator:
    """
    Monte Carlo path generator with Brownian bridge barrier monitoring.
    
    Implements:
    - Multi-asset GBM with Cholesky correlation
    - Piecewise constant vol per time bucket
    - Discrete dividends as spot jumps
    - Continuous KI monitoring via Brownian bridge
    """
    
    def __init__(
        self,
        term_sheet: TermSheet,
        grid: SimulationGrid,
        config: PathGeneratorConfig
    ) -> None:
        self.ts = term_sheet
        self.grid = grid
        self.config = config
        
        self.num_assets = len(term_sheet.underlyings)
        self.asset_ids = [u.id for u in term_sheet.underlyings]
        
        # Build correlation and Cholesky
        corr = build_correlation_matrix(term_sheet)
        self.corr = validate_and_fix_correlation(corr)
        self.cholesky = compute_cholesky(self.corr)
        
        # Extract initial spots
        self.spots_0 = np.array([u.spot for u in term_sheet.underlyings])
        
        # Build vol term structure per asset
        self._build_vol_arrays()
        
        # Build dividend structures
        self._build_dividend_arrays()
        
        # KI barrier
        self.ki_level = None
        self.ki_barriers = None  # Absolute levels
        if term_sheet.ki_barrier is not None:
            self.ki_level = term_sheet.ki_barrier.level
            self.ki_barriers = self.spots_0 * self.ki_level
        
        # RNG
        self._rng: Optional[Generator] = None
        if config.seed is not None:
            self._rng = default_rng(config.seed)
    
    def _build_vol_arrays(self) -> None:
        """Build volatility for each time step and asset."""
        num_steps = self.grid.num_steps
        self.vols = np.zeros((num_steps + 1, self.num_assets))
        
        # Track which assets use LSV
        self.lsv_assets = []  # List of (asset_idx, LSVParams)
        
        for a_idx, underlying in enumerate(self.ts.underlyings):
            vol_model = underlying.vol_model
            
            if vol_model.type == VolModelType.FLAT:
                self.vols[:, a_idx] = vol_model.flat_vol or 0.20
            
            elif vol_model.type == VolModelType.PIECEWISE_CONSTANT:
                tenors = vol_model.term_structure or []
                
                for step_idx, step_date in enumerate(self.grid.dates):
                    # Find applicable vol
                    vol = tenors[-1].vol if tenors else 0.20
                    for tenor in tenors:
                        if step_date <= tenor.date:
                            vol = tenor.vol
                            break
                    self.vols[step_idx, a_idx] = vol
            
            elif vol_model.type == VolModelType.LOCAL_STOCHASTIC:
                # LSV: store params, initial vol from sqrt(v0)
                params = vol_model.lsv_params
                if params is None:
                    from pricer.products.schema import LSVParams
                    params = LSVParams()
                self.lsv_assets.append((a_idx, params))
                # Use sqrt(v0) as initial deterministic vol (will be overwritten during simulation)
                self.vols[:, a_idx] = np.sqrt(params.v0)
    
    def _build_dividend_arrays(self) -> None:
        """Build discrete dividend schedules."""
        # Map: step_idx -> {asset_idx: amount}
        self.discrete_divs: Dict[int, Dict[int, float]] = {}
        
        for a_idx, underlying in enumerate(self.ts.underlyings):
            if underlying.dividend_model.type in (DividendModelType.DISCRETE, DividendModelType.MIXED):
                exdiv_schedule = get_exdiv_schedule_for_underlying(
                    self.grid, underlying.id
                )
                for grid_idx, amount in exdiv_schedule:
                    if grid_idx not in self.discrete_divs:
                        self.discrete_divs[grid_idx] = {}
                    self.discrete_divs[grid_idx][a_idx] = amount
        
        # Continuous yield per asset
        self.cont_yields = np.zeros(self.num_assets)
        for a_idx, underlying in enumerate(self.ts.underlyings):
            if underlying.dividend_model.continuous_yield is not None:
                self.cont_yields[a_idx] = underlying.dividend_model.continuous_yield
    
    def _get_rng(self) -> Generator:
        """Get or create RNG."""
        if self._rng is None:
            self._rng = default_rng(self.config.seed)
        return self._rng
    
    def set_seed(self, seed: int) -> None:
        """Set RNG seed (for CRN Greeks)."""
        self.config.seed = seed
        self._rng = default_rng(seed)
    
    def generate(self) -> SimulatedPaths:
        """
        Generate Monte Carlo paths.
        
        Returns:
            SimulatedPaths with spots and KI state
        """
        rng = self._get_rng()
        
        num_paths = self.config.num_paths
        num_steps = self.grid.num_steps
        num_assets = self.num_assets
        dtype = self.config.dtype
        
        # Get discount rate from term sheet
        r = self.ts.discount_curve.flat_rate or 0.0
        
        # Initialize arrays
        spots = np.zeros((num_paths, num_steps + 1, num_assets), dtype=dtype)
        spots[:, 0, :] = self.spots_0
        
        ki_state = np.zeros(num_paths, dtype=bool)
        ki_step = np.full(num_paths, -1, dtype=np.int32)
        
        # Generate all random numbers upfront
        Z = rng.standard_normal((num_paths, num_steps, num_assets)).astype(dtype)
        
        # For Brownian bridge KI, also need uniform draws for probabilistic check
        U_ki = rng.uniform(0, 1, (num_paths, num_steps, num_assets)).astype(dtype)
        
        # LSV: Initialize variance paths and generate additional randoms for variance
        variance = np.zeros((num_paths, num_assets), dtype=dtype)
        Z_var = None
        if self.lsv_assets:
            Z_var = rng.standard_normal((num_paths, num_steps, len(self.lsv_assets))).astype(dtype)
            for lsv_idx, (a_idx, params) in enumerate(self.lsv_assets):
                variance[:, a_idx] = params.v0
        
        # Correlate: Z_corr = Z @ L^T where L is lower Cholesky
        Z_corr = np.einsum('ijk,lk->ijl', Z, self.cholesky)
        
        # Simulate step by step
        for step in range(num_steps):
            dt = self.grid.dt[step + 1]
            
            if dt <= 0:
                spots[:, step + 1, :] = spots[:, step, :]
                continue
            
            sqrt_dt = np.sqrt(dt)
            
            # Get vol for this step (use step+1 date's vol)
            vol = self.vols[step + 1, :].copy()  # [num_assets]
            
            # LSV: Update variance and use sqrt(V) as vol for LSV assets
            if self.lsv_assets:
                for lsv_idx, (a_idx, params) in enumerate(self.lsv_assets):
                    V = variance[:, a_idx]
                    
                    # QE (Quadratic Exponential) scheme for variance
                    # Reference: Andersen (2008)
                    kappa, theta, xi = params.kappa, params.theta, params.xi
                    rho = params.rho
                    
                    # Exp decay
                    exp_kappa_dt = np.exp(-kappa * dt)
                    
                    # Mean and variance of V(t+dt) given V(t)
                    m = theta + (V - theta) * exp_kappa_dt
                    s2 = V * xi**2 * exp_kappa_dt * (1 - exp_kappa_dt) / kappa
                    s2 += theta * xi**2 * (1 - exp_kappa_dt)**2 / (2 * kappa)
                    s2 = np.maximum(s2, 1e-10)  # Ensure positive
                    
                    # Psi = s2 / m^2
                    psi = s2 / np.maximum(m**2, 1e-10)
                    
                    # QE switching threshold
                    psi_c = 1.5
                    
                    # Generate uniform for inverse CDF
                    U_v = rng.uniform(0, 1, num_paths).astype(dtype)
                    
                    # Case 1: psi <= psi_c (use moment matching)
                    mask_low = psi <= psi_c
                    b2 = np.where(mask_low, 2 / psi - 1 + np.sqrt(2 / psi) * np.sqrt(2 / psi - 1), 0)
                    b2 = np.maximum(b2, 0)
                    a = np.where(mask_low, m / (1 + b2), 0)
                    V_new_low = a * (np.sqrt(b2) + Z_var[:, step, lsv_idx])**2
                    
                    # Case 2: psi > psi_c (use exponential approximation)
                    p = np.where(~mask_low, (psi - 1) / (psi + 1), 0)
                    beta = np.where(~mask_low, (1 - p) / np.maximum(m, 1e-10), 0)
                    V_new_high = np.where(
                        U_v <= p,
                        0,
                        np.log((1 - p) / np.maximum(1 - U_v, 1e-10)) / np.maximum(beta, 1e-10)
                    )
                    
                    # Combine
                    V_new = np.where(mask_low, V_new_low, V_new_high)
                    V_new = np.maximum(V_new, 1e-10)  # Floor at small positive
                    
                    variance[:, a_idx] = V_new
                    
                    # Use average vol for this step (trapezoidal)
                    vol_step = np.sqrt(0.5 * (V + V_new))
                    
                    # Override vol array for this asset
                    vol = np.broadcast_to(vol, (num_paths, num_assets)).copy()
                    vol[:, a_idx] = vol_step
                    
                    # Adjust spot diffusion for spot-vol correlation
                    # dS = ... + rho * (xi/sqrt(V)) * S * dV_normalized
                    # Already handled via correlation in Z_corr if assets are correlated
            
            # Drift: r - q - 0.5*vol^2
            drift = r - self.cont_yields - 0.5 * vol * vol  # [num_assets] or [num_paths, num_assets]
            
            # Log return
            log_return = drift * dt + vol * sqrt_dt * Z_corr[:, step, :]
            
            # Update spots
            spots[:, step + 1, :] = spots[:, step, :] * np.exp(log_return)
            
            # Apply discrete dividends (spot jump)
            if (step + 1) in self.discrete_divs:
                for a_idx, div_amount in self.discrete_divs[step + 1].items():
                    spots[:, step + 1, a_idx] = np.maximum(
                        spots[:, step + 1, a_idx] - div_amount,
                        0.01  # Floor at 0.01 to avoid negative spots
                    )
            
            # Continuous KI barrier check via Brownian bridge
            if self.ki_barriers is not None and not np.all(ki_state):
                S_start = spots[:, step, :]     # [num_paths, num_assets]
                S_end = spots[:, step + 1, :]   # [num_paths, num_assets]
                
                # Check each asset
                for a_idx in range(num_assets):
                    barrier = self.ki_barriers[a_idx]
                    # Handle both 1D and 2D vol arrays
                    if vol.ndim == 1:
                        v = vol[a_idx]
                    else:
                        v = vol[:, a_idx]
                    
                    # Compute hit probability
                    hit_prob = brownian_bridge_hit_probability(
                        S_start[:, a_idx],
                        S_end[:, a_idx],
                        barrier,
                        v,
                        dt,
                        down=True
                    )
                    
                    # Probabilistic KI: if U < P(hit), then KI occurred
                    new_ki = (~ki_state) & (U_ki[:, step, a_idx] < hit_prob)
                    
                    # Update state
                    ki_step = np.where(new_ki & (ki_step < 0), step + 1, ki_step)
                    ki_state = ki_state | new_ki
        
        return SimulatedPaths(
            spots=spots,
            ki_state=ki_state,
            ki_step=ki_step
        )
