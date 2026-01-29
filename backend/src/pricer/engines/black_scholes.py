"""
Black-Scholes analytical pricing formulas and Greeks.

Implements closed-form solutions for European options inspired by
andleb/derivatives C++ library patterns.
"""

import numpy as np
from scipy.stats import norm
from typing import NamedTuple, Optional
from dataclasses import dataclass


@dataclass
class Greeks:
    """Option Greeks (sensitivities)."""
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float


@dataclass
class VanillaResult:
    """Result of vanilla option pricing."""
    price: float
    greeks: Greeks
    
    
def d1(S: float, K: float, T: float, r: float, q: float, sigma: float) -> float:
    """
    Calculate d1 in Black-Scholes formula.
    
    Args:
        S: Spot price
        K: Strike price
        T: Time to expiry (years)
        r: Risk-free rate (continuous)
        q: Dividend yield (continuous)
        sigma: Volatility
        
    Returns:
        d1 value
    """
    if T <= 0 or sigma <= 0:
        return 0.0
    return (np.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))


def d2(S: float, K: float, T: float, r: float, q: float, sigma: float) -> float:
    """
    Calculate d2 in Black-Scholes formula.
    
    Args:
        S: Spot price
        K: Strike price
        T: Time to expiry (years)
        r: Risk-free rate (continuous)
        q: Dividend yield (continuous)
        sigma: Volatility
        
    Returns:
        d2 value
    """
    if T <= 0 or sigma <= 0:
        return 0.0
    return d1(S, K, T, r, q, sigma) - sigma * np.sqrt(T)


def bs_call_price(S: float, K: float, T: float, r: float, q: float, sigma: float) -> float:
    """
    Black-Scholes European call option price.
    
    Args:
        S: Spot price
        K: Strike price
        T: Time to expiry (years)
        r: Risk-free rate (continuous)
        q: Dividend yield (continuous)
        sigma: Volatility
        
    Returns:
        Call option price
    """
    if T <= 0:
        return max(S - K, 0.0)
    if sigma <= 0:
        # Degenerate case: forward price vs strike
        forward = S * np.exp((r - q) * T)
        return max(forward - K, 0.0) * np.exp(-r * T)
    
    d1_val = d1(S, K, T, r, q, sigma)
    d2_val = d2(S, K, T, r, q, sigma)
    
    return S * np.exp(-q * T) * norm.cdf(d1_val) - K * np.exp(-r * T) * norm.cdf(d2_val)


def bs_put_price(S: float, K: float, T: float, r: float, q: float, sigma: float) -> float:
    """
    Black-Scholes European put option price.
    
    Args:
        S: Spot price
        K: Strike price
        T: Time to expiry (years)
        r: Risk-free rate (continuous)
        q: Dividend yield (continuous)
        sigma: Volatility
        
    Returns:
        Put option price
    """
    if T <= 0:
        return max(K - S, 0.0)
    if sigma <= 0:
        forward = S * np.exp((r - q) * T)
        return max(K - forward, 0.0) * np.exp(-r * T)
    
    d1_val = d1(S, K, T, r, q, sigma)
    d2_val = d2(S, K, T, r, q, sigma)
    
    return K * np.exp(-r * T) * norm.cdf(-d2_val) - S * np.exp(-q * T) * norm.cdf(-d1_val)


def bs_greeks(S: float, K: float, T: float, r: float, q: float, sigma: float, is_call: bool = True) -> Greeks:
    """
    Calculate Black-Scholes Greeks.
    
    Args:
        S: Spot price
        K: Strike price  
        T: Time to expiry (years)
        r: Risk-free rate (continuous)
        q: Dividend yield (continuous)
        sigma: Volatility
        is_call: True for call, False for put
        
    Returns:
        Greeks object with delta, gamma, theta, vega, rho
    """
    if T <= 0 or sigma <= 0:
        # At expiry or zero vol
        if is_call:
            delta = 1.0 if S > K else 0.0
        else:
            delta = -1.0 if S < K else 0.0
        return Greeks(delta=delta, gamma=0.0, theta=0.0, vega=0.0, rho=0.0)
    
    d1_val = d1(S, K, T, r, q, sigma)
    d2_val = d2(S, K, T, r, q, sigma)
    
    sqrt_T = np.sqrt(T)
    exp_qT = np.exp(-q * T)
    exp_rT = np.exp(-r * T)
    
    # Standard normal PDF at d1
    pdf_d1 = norm.pdf(d1_val)
    
    # Gamma (same for calls and puts)
    gamma = exp_qT * pdf_d1 / (S * sigma * sqrt_T)
    
    # Vega (same for calls and puts) - per 1% vol move
    vega = S * exp_qT * pdf_d1 * sqrt_T / 100.0
    
    if is_call:
        # Call delta
        delta = exp_qT * norm.cdf(d1_val)
        
        # Call theta (per day)
        theta = (
            -S * exp_qT * pdf_d1 * sigma / (2 * sqrt_T)
            - r * K * exp_rT * norm.cdf(d2_val)
            + q * S * exp_qT * norm.cdf(d1_val)
        ) / 365.0
        
        # Call rho (per 1% rate move)
        rho = K * T * exp_rT * norm.cdf(d2_val) / 100.0
    else:
        # Put delta
        delta = exp_qT * (norm.cdf(d1_val) - 1)
        
        # Put theta (per day)
        theta = (
            -S * exp_qT * pdf_d1 * sigma / (2 * sqrt_T)
            + r * K * exp_rT * norm.cdf(-d2_val)
            - q * S * exp_qT * norm.cdf(-d1_val)
        ) / 365.0
        
        # Put rho (per 1% rate move)
        rho = -K * T * exp_rT * norm.cdf(-d2_val) / 100.0
    
    return Greeks(delta=delta, gamma=gamma, theta=theta, vega=vega, rho=rho)


def price_vanilla(
    S: float, K: float, T: float, r: float, q: float, sigma: float, is_call: bool = True
) -> VanillaResult:
    """
    Price a vanilla European option with Greeks.
    
    Args:
        S: Spot price
        K: Strike price
        T: Time to expiry (years)
        r: Risk-free rate (continuous)
        q: Dividend yield (continuous)
        sigma: Volatility
        is_call: True for call, False for put
        
    Returns:
        VanillaResult with price and Greeks
    """
    if is_call:
        price = bs_call_price(S, K, T, r, q, sigma)
    else:
        price = bs_put_price(S, K, T, r, q, sigma)
    
    greeks = bs_greeks(S, K, T, r, q, sigma, is_call)
    
    return VanillaResult(price=price, greeks=greeks)


def implied_vol(
    price: float,
    S: float,
    K: float,
    T: float,
    r: float,
    q: float,
    is_call: bool = True,
    initial_guess: float = 0.2,
    tol: float = 1e-8,
    max_iter: int = 100
) -> Optional[float]:
    """
    Calculate implied volatility using Newton-Raphson method.
    
    Args:
        price: Market price of option
        S: Spot price
        K: Strike price
        T: Time to expiry (years)
        r: Risk-free rate (continuous)
        q: Dividend yield (continuous)
        is_call: True for call, False for put
        initial_guess: Starting volatility guess
        tol: Convergence tolerance
        max_iter: Maximum iterations
        
    Returns:
        Implied volatility or None if not converged
    """
    if T <= 0:
        return None
    
    # Check bounds
    intrinsic = max(S * np.exp(-q * T) - K * np.exp(-r * T), 0.0) if is_call else max(K * np.exp(-r * T) - S * np.exp(-q * T), 0.0)
    if price < intrinsic - tol:
        return None  # Price below intrinsic
    
    sigma = initial_guess
    
    for _ in range(max_iter):
        if is_call:
            bs_price = bs_call_price(S, K, T, r, q, sigma)
        else:
            bs_price = bs_put_price(S, K, T, r, q, sigma)
        
        diff = bs_price - price
        
        if abs(diff) < tol:
            return sigma
        
        # Vega for Newton-Raphson (raw, not scaled)
        d1_val = d1(S, K, T, r, q, sigma)
        vega_raw = S * np.exp(-q * T) * norm.pdf(d1_val) * np.sqrt(T)
        
        if vega_raw < 1e-12:
            # Vega too small, try bisection fallback
            break
        
        sigma = sigma - diff / vega_raw
        
        # Keep sigma in reasonable bounds
        sigma = max(0.001, min(sigma, 5.0))
    
    # Fallback to bisection if Newton-Raphson fails
    return _implied_vol_bisection(price, S, K, T, r, q, is_call, tol, max_iter)


def _implied_vol_bisection(
    price: float,
    S: float,
    K: float,
    T: float,
    r: float,
    q: float,
    is_call: bool,
    tol: float,
    max_iter: int
) -> Optional[float]:
    """Bisection fallback for implied vol."""
    low, high = 0.001, 5.0
    
    for _ in range(max_iter):
        mid = (low + high) / 2
        
        if is_call:
            bs_price = bs_call_price(S, K, T, r, q, mid)
        else:
            bs_price = bs_put_price(S, K, T, r, q, mid)
        
        diff = bs_price - price
        
        if abs(diff) < tol:
            return mid
        
        if diff > 0:
            high = mid
        else:
            low = mid
    
    return (low + high) / 2  # Return best estimate


# Vectorized versions for efficiency
def bs_call_price_vec(
    S: np.ndarray, K: np.ndarray, T: np.ndarray, 
    r: np.ndarray, q: np.ndarray, sigma: np.ndarray
) -> np.ndarray:
    """Vectorized Black-Scholes call pricing."""
    sqrt_T = np.sqrt(np.maximum(T, 1e-10))
    d1_val = (np.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * sqrt_T)
    d2_val = d1_val - sigma * sqrt_T
    
    return S * np.exp(-q * T) * norm.cdf(d1_val) - K * np.exp(-r * T) * norm.cdf(d2_val)


def bs_put_price_vec(
    S: np.ndarray, K: np.ndarray, T: np.ndarray,
    r: np.ndarray, q: np.ndarray, sigma: np.ndarray
) -> np.ndarray:
    """Vectorized Black-Scholes put pricing."""
    sqrt_T = np.sqrt(np.maximum(T, 1e-10))
    d1_val = (np.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * sqrt_T)
    d2_val = d1_val - sigma * sqrt_T
    
    return K * np.exp(-r * T) * norm.cdf(-d2_val) - S * np.exp(-q * T) * norm.cdf(-d1_val)
