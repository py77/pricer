"""
Binomial and Trinomial tree pricing for American and European options.

Inspired by andleb/derivatives C++ library patterns.
"""

import numpy as np
from typing import Optional, Literal
from dataclasses import dataclass
from enum import Enum


class ExerciseStyle(str, Enum):
    """Option exercise style."""
    EUROPEAN = "european"
    AMERICAN = "american"


class OptionType(str, Enum):
    """Option type."""
    CALL = "call"
    PUT = "put"


@dataclass
class TreeResult:
    """Result of tree pricing."""
    price: float
    delta: float
    gamma: float
    theta: float
    early_exercise_boundary: Optional[np.ndarray] = None


class BinomialTree:
    """
    Cox-Ross-Rubinstein (CRR) binomial tree for option pricing.
    
    Supports European and American exercise for calls and puts.
    """
    
    def __init__(
        self,
        S: float,
        K: float,
        T: float,
        r: float,
        q: float,
        sigma: float,
        n_steps: int = 100
    ):
        """
        Initialize binomial tree.
        
        Args:
            S: Spot price
            K: Strike price
            T: Time to expiry (years)
            r: Risk-free rate (continuous)
            q: Dividend yield (continuous)
            sigma: Volatility
            n_steps: Number of time steps
        """
        self.S = S
        self.K = K
        self.T = T
        self.r = r
        self.q = q
        self.sigma = sigma
        self.n_steps = n_steps
        
        # Calculate tree parameters
        self.dt = T / n_steps
        self.u = np.exp(sigma * np.sqrt(self.dt))  # Up factor
        self.d = 1.0 / self.u  # Down factor
        self.discount = np.exp(-r * self.dt)
        
        # Risk-neutral probability
        self.p = (np.exp((r - q) * self.dt) - self.d) / (self.u - self.d)
        
    def price(
        self,
        option_type: OptionType = OptionType.CALL,
        exercise: ExerciseStyle = ExerciseStyle.EUROPEAN
    ) -> TreeResult:
        """
        Price option using binomial tree.
        
        Args:
            option_type: CALL or PUT
            exercise: EUROPEAN or AMERICAN
            
        Returns:
            TreeResult with price and Greeks
        """
        n = self.n_steps
        
        # Build spot tree at expiry
        spots = self.S * (self.u ** np.arange(n, -1, -1)) * (self.d ** np.arange(0, n + 1))
        
        # Option payoff at expiry
        if option_type == OptionType.CALL:
            values = np.maximum(spots - self.K, 0.0)
        else:
            values = np.maximum(self.K - spots, 0.0)
        
        # Early exercise boundary tracking
        early_exercise = np.full(n + 1, np.nan) if exercise == ExerciseStyle.AMERICAN else None
        
        # Backward induction
        for step in range(n - 1, -1, -1):
            # Spots at this step
            spots = self.S * (self.u ** np.arange(step, -1, -1)) * (self.d ** np.arange(0, step + 1))
            
            # Continuation value
            continuation = self.discount * (self.p * values[:-1] + (1 - self.p) * values[1:])
            
            if exercise == ExerciseStyle.AMERICAN:
                # Early exercise value
                if option_type == OptionType.CALL:
                    exercise_value = np.maximum(spots - self.K, 0.0)
                else:
                    exercise_value = np.maximum(self.K - spots, 0.0)
                
                # Find early exercise boundary
                exercise_optimal = exercise_value > continuation
                if np.any(exercise_optimal):
                    if option_type == OptionType.PUT:
                        # For put, boundary is highest spot where exercise is optimal
                        early_exercise[step] = spots[exercise_optimal][0]
                    else:
                        # For call, boundary is lowest spot where exercise is optimal
                        early_exercise[step] = spots[exercise_optimal][-1]
                
                values = np.maximum(continuation, exercise_value)
            else:
                values = continuation
        
        price = values[0]
        
        # Calculate Greeks using adjacent nodes
        # Delta: (f_u - f_d) / (S_u - S_d)
        if n >= 1:
            S_u = self.S * self.u
            S_d = self.S * self.d
            
            # Reprice at S_u and S_d
            tree_u = BinomialTree(S_u, self.K, self.T - self.dt, self.r, self.q, self.sigma, max(1, n - 1))
            tree_d = BinomialTree(S_d, self.K, self.T - self.dt, self.r, self.q, self.sigma, max(1, n - 1))
            
            f_u = tree_u.price(option_type, exercise).price
            f_d = tree_d.price(option_type, exercise).price
            
            delta = (f_u - f_d) / (S_u - S_d)
            
            # Gamma: change in delta
            tree_uu = BinomialTree(S_u * self.u, self.K, self.T - 2*self.dt, self.r, self.q, self.sigma, max(1, n - 2))
            tree_dd = BinomialTree(S_d * self.d, self.K, self.T - 2*self.dt, self.r, self.q, self.sigma, max(1, n - 2))
            
            f_uu = tree_uu.price(option_type, exercise).price if n >= 2 else max(S_u * self.u - self.K, 0) if option_type == OptionType.CALL else max(self.K - S_d * self.d, 0)
            f_dd = tree_dd.price(option_type, exercise).price if n >= 2 else max(S_d * self.d - self.K, 0) if option_type == OptionType.CALL else max(self.K - S_d * self.d, 0)
            f_ud = tree_u.price(option_type, exercise).price  # Approximation
            
            delta_u = (f_uu - f_ud) / (S_u * self.u - self.S)
            delta_d = (f_ud - f_dd) / (self.S - S_d * self.d)
            
            gamma = (delta_u - delta_d) / (0.5 * (S_u * self.u - S_d * self.d))
            
            # Theta: (f(t+dt) - f(t)) / dt
            theta = (f_ud - price) / self.dt / 365.0  # Per day
        else:
            delta = 1.0 if (option_type == OptionType.CALL and self.S > self.K) else (-1.0 if option_type == OptionType.PUT and self.S < self.K else 0.0)
            gamma = 0.0
            theta = 0.0
        
        return TreeResult(
            price=price,
            delta=delta,
            gamma=gamma,
            theta=theta,
            early_exercise_boundary=early_exercise
        )


class TrinomialTree:
    """
    Trinomial tree for option pricing.
    
    More accurate than binomial tree, especially for barrier options.
    """
    
    def __init__(
        self,
        S: float,
        K: float,
        T: float,
        r: float,
        q: float,
        sigma: float,
        n_steps: int = 100,
        lambda_param: float = np.sqrt(2.0)
    ):
        """
        Initialize trinomial tree.
        
        Args:
            S: Spot price
            K: Strike price
            T: Time to expiry (years)
            r: Risk-free rate (continuous)
            q: Dividend yield (continuous)
            sigma: Volatility
            n_steps: Number of time steps
            lambda_param: Stretch parameter (sqrt(2) is standard)
        """
        self.S = S
        self.K = K
        self.T = T
        self.r = r
        self.q = q
        self.sigma = sigma
        self.n_steps = n_steps
        self.lam = lambda_param
        
        # Calculate tree parameters
        self.dt = T / n_steps
        self.u = np.exp(self.lam * sigma * np.sqrt(self.dt))
        self.d = 1.0 / self.u
        self.discount = np.exp(-r * self.dt)
        
        # Risk-neutral probabilities
        drift = (r - q) * self.dt
        variance = sigma**2 * self.dt
        
        # Up, middle, down probabilities
        self.p_u = (variance + drift**2 + drift * self.lam * sigma * np.sqrt(self.dt)) / (2 * self.lam**2 * variance)
        self.p_d = (variance + drift**2 - drift * self.lam * sigma * np.sqrt(self.dt)) / (2 * self.lam**2 * variance)
        self.p_m = 1.0 - self.p_u - self.p_d
        
        # Clamp probabilities
        self.p_u = max(0.0, min(1.0, self.p_u))
        self.p_d = max(0.0, min(1.0, self.p_d))
        self.p_m = max(0.0, 1.0 - self.p_u - self.p_d)
        
    def price(
        self,
        option_type: OptionType = OptionType.CALL,
        exercise: ExerciseStyle = ExerciseStyle.EUROPEAN
    ) -> TreeResult:
        """
        Price option using trinomial tree.
        
        Args:
            option_type: CALL or PUT
            exercise: EUROPEAN or AMERICAN
            
        Returns:
            TreeResult with price and Greeks
        """
        n = self.n_steps
        
        # Number of nodes at step i is 2*i + 1
        # Build spot tree at expiry
        j_values = np.arange(-n, n + 1)
        spots = self.S * (self.u ** j_values)
        
        # Option payoff at expiry
        if option_type == OptionType.CALL:
            values = np.maximum(spots - self.K, 0.0)
        else:
            values = np.maximum(self.K - spots, 0.0)
        
        # Backward induction
        for step in range(n - 1, -1, -1):
            j_values = np.arange(-step, step + 1)
            spots = self.S * (self.u ** j_values)
            
            # Continuation value
            new_values = np.zeros(2 * step + 1)
            for i, j in enumerate(j_values):
                # Map to indices in previous value array
                idx_u = j + 1 + (n - step - 1) + step  # Index in values array for up move
                idx_m = j + (n - step - 1) + step      # Index for middle (no move)
                idx_d = j - 1 + (n - step - 1) + step  # Index for down move
                
                # Actually simpler: treat values as centered at 0
                center_prev = n - step
                idx_u = (j + 1) + center_prev
                idx_m = j + center_prev
                idx_d = (j - 1) + center_prev
                
                continuation = self.discount * (
                    self.p_u * values[idx_u] + 
                    self.p_m * values[idx_m] + 
                    self.p_d * values[idx_d]
                )
                
                if exercise == ExerciseStyle.AMERICAN:
                    if option_type == OptionType.CALL:
                        exercise_value = max(spots[i] - self.K, 0.0)
                    else:
                        exercise_value = max(self.K - spots[i], 0.0)
                    new_values[i] = max(continuation, exercise_value)
                else:
                    new_values[i] = continuation
            
            values = new_values
        
        price = values[0]
        
        # Simplified Greeks (would need more careful implementation for production)
        delta = 0.0
        gamma = 0.0
        theta = 0.0
        
        if n >= 2:
            # Bump and reprice for delta
            bump = 0.01 * self.S
            tree_up = TrinomialTree(self.S + bump, self.K, self.T, self.r, self.q, self.sigma, n)
            tree_dn = TrinomialTree(self.S - bump, self.K, self.T, self.r, self.q, self.sigma, n)
            
            price_up = tree_up.price(option_type, exercise).price
            price_dn = tree_dn.price(option_type, exercise).price
            
            delta = (price_up - price_dn) / (2 * bump)
            gamma = (price_up - 2 * price + price_dn) / (bump ** 2)
            
            # Theta via time bump
            if self.T > self.dt:
                tree_t = TrinomialTree(self.S, self.K, self.T - self.dt, self.r, self.q, self.sigma, max(1, n-1))
                price_t = tree_t.price(option_type, exercise).price
                theta = (price_t - price) / self.dt / 365.0
        
        return TreeResult(price=price, delta=delta, gamma=gamma, theta=theta)


def price_american(
    S: float,
    K: float,
    T: float,
    r: float,
    q: float,
    sigma: float,
    is_call: bool = True,
    n_steps: int = 200,
    tree_type: Literal["binomial", "trinomial"] = "binomial"
) -> TreeResult:
    """
    Convenience function to price American options.
    
    Args:
        S: Spot price
        K: Strike price
        T: Time to expiry (years)
        r: Risk-free rate (continuous)
        q: Dividend yield (continuous)
        sigma: Volatility
        is_call: True for call, False for put
        n_steps: Number of tree steps
        tree_type: "binomial" or "trinomial"
        
    Returns:
        TreeResult with price and Greeks
    """
    option_type = OptionType.CALL if is_call else OptionType.PUT
    
    if tree_type == "trinomial":
        tree = TrinomialTree(S, K, T, r, q, sigma, n_steps)
    else:
        tree = BinomialTree(S, K, T, r, q, sigma, n_steps)
    
    return tree.price(option_type, ExerciseStyle.AMERICAN)


def price_european_tree(
    S: float,
    K: float,
    T: float,
    r: float,
    q: float,
    sigma: float,
    is_call: bool = True,
    n_steps: int = 200,
    tree_type: Literal["binomial", "trinomial"] = "binomial"
) -> TreeResult:
    """
    Price European options using tree (for comparison with BS).
    
    Args:
        S: Spot price
        K: Strike price
        T: Time to expiry (years)
        r: Risk-free rate (continuous)
        q: Dividend yield (continuous)
        sigma: Volatility
        is_call: True for call, False for put
        n_steps: Number of tree steps
        tree_type: "binomial" or "trinomial"
        
    Returns:
        TreeResult with price and Greeks
    """
    option_type = OptionType.CALL if is_call else OptionType.PUT
    
    if tree_type == "trinomial":
        tree = TrinomialTree(S, K, T, r, q, sigma, n_steps)
    else:
        tree = BinomialTree(S, K, T, r, q, sigma, n_steps)
    
    return tree.price(option_type, ExerciseStyle.EUROPEAN)
