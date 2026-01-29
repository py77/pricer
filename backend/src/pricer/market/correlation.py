"""
Correlation matrix for multi-asset pricing.

Supports constant correlation with Cholesky decomposition.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
import numpy as np


@dataclass
class CorrelationMatrix:
    """
    Correlation matrix for multi-asset simulation.
    
    Provides Cholesky decomposition for correlated random number generation.
    
    Attributes:
        assets: List of asset identifiers in matrix order
        matrix: NxN correlation matrix (symmetric, positive semi-definite)
    """
    
    assets: List[str] = field(default_factory=list)
    matrix: np.ndarray = field(default_factory=lambda: np.array([[1.0]]))
    _cholesky: Optional[np.ndarray] = field(default=None, repr=False)
    
    def __post_init__(self) -> None:
        """Validate and compute Cholesky decomposition."""
        n = len(self.assets)
        
        if self.matrix.shape != (n, n):
            raise ValueError(
                f"Matrix shape {self.matrix.shape} doesn't match {n} assets"
            )
        
        # Validate symmetry
        if not np.allclose(self.matrix, self.matrix.T):
            raise ValueError("Correlation matrix must be symmetric")
        
        # Validate diagonal
        if not np.allclose(np.diag(self.matrix), 1.0):
            raise ValueError("Correlation matrix diagonal must be 1.0")
        
        # Validate range
        if np.any(self.matrix < -1.0) or np.any(self.matrix > 1.0):
            raise ValueError("Correlations must be in [-1, 1]")
        
        # Compute Cholesky decomposition
        self._compute_cholesky()
    
    def _compute_cholesky(self) -> None:
        """Compute Cholesky decomposition with fallback for near-singular matrices."""
        try:
            self._cholesky = np.linalg.cholesky(self.matrix)
        except np.linalg.LinAlgError:
            # Matrix is not positive definite, apply small regularization
            epsilon = 1e-10
            regularized = self.matrix + epsilon * np.eye(len(self.assets))
            self._cholesky = np.linalg.cholesky(regularized)
    
    @property
    def cholesky(self) -> np.ndarray:
        """Get Cholesky decomposition (lower triangular)."""
        if self._cholesky is None:
            self._compute_cholesky()
        return self._cholesky  # type: ignore
    
    def get_correlation(self, asset1: str, asset2: str) -> float:
        """Get correlation between two assets."""
        try:
            i = self.assets.index(asset1)
            j = self.assets.index(asset2)
            return float(self.matrix[i, j])
        except ValueError as e:
            raise ValueError(f"Asset not found in correlation matrix: {e}")
    
    def correlate(self, independent_normals: np.ndarray) -> np.ndarray:
        """
        Transform independent normal samples to correlated samples.
        
        Args:
            independent_normals: Array of shape (num_paths, num_assets)
                containing independent standard normal samples
                
        Returns:
            Array of same shape with correlated samples
        """
        # Z_corr = L @ Z_indep  for each path
        # L is lower triangular Cholesky factor
        return independent_normals @ self.cholesky.T
    
    @classmethod
    def from_dict(cls, assets: List[str], correlations: Dict[str, float]) -> "CorrelationMatrix":
        """
        Create correlation matrix from pairwise correlation dictionary.
        
        Args:
            assets: List of asset identifiers
            correlations: Dict with keys like "ASSET1_ASSET2" and values as correlations
            
        Returns:
            CorrelationMatrix instance
        """
        n = len(assets)
        matrix = np.eye(n)
        
        for i, asset_i in enumerate(assets):
            for j, asset_j in enumerate(assets):
                if i < j:
                    key = f"{asset_i}_{asset_j}"
                    alt_key = f"{asset_j}_{asset_i}"
                    
                    if key in correlations:
                        matrix[i, j] = correlations[key]
                        matrix[j, i] = correlations[key]
                    elif alt_key in correlations:
                        matrix[i, j] = correlations[alt_key]
                        matrix[j, i] = correlations[alt_key]
        
        return cls(assets=assets, matrix=matrix)
    
    @classmethod
    def identity(cls, assets: List[str]) -> "CorrelationMatrix":
        """Create identity (uncorrelated) correlation matrix."""
        n = len(assets)
        return cls(assets=assets, matrix=np.eye(n))
    
    @classmethod
    def uniform(cls, assets: List[str], correlation: float) -> "CorrelationMatrix":
        """Create uniform correlation matrix (all pairs have same correlation)."""
        n = len(assets)
        matrix = np.full((n, n), correlation)
        np.fill_diagonal(matrix, 1.0)
        return cls(assets=assets, matrix=matrix)
