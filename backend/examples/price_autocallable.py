#!/usr/bin/env python3
"""
Example: Price a worst-of autocallable note.

This script demonstrates the end-to-end pricing workflow:
1. Load product from JSON term sheet
2. Build market data
3. Run Monte Carlo pricing
4. Generate risk report

Usage:
    python examples/price_autocallable.py
"""

import sys
from pathlib import Path
from datetime import date

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pricer.products.schema import load_product
from pricer.market.market_data import MarketData
from pricer.market.rates import FlatRateCurve
from pricer.market.volatility import FlatVolatility, PiecewiseConstantVol
from pricer.market.dividends import ContinuousDividend
from pricer.market.correlation import CorrelationMatrix
from pricer.market.market_data import Underlying
from pricer.engines.monte_carlo import MonteCarloEngine
from pricer.risk.report import generate_report


def build_sample_market() -> MarketData:
    """
    Build sample market data for pricing.
    
    In production, this would load from a market data service.
    """
    valuation_date = date(2024, 1, 15)
    
    # Risk-free rate: 5% flat
    rate_curve = FlatRateCurve(rate=0.05)
    
    # Underlyings with vol term structure and dividends
    underlyings = {
        "AAPL": Underlying(
            ticker="AAPL",
            spot=185.0,
            vol_surface=PiecewiseConstantVol(tenors=[
                (date(2024, 7, 15), 0.28),   # 6M vol
                (date(2025, 1, 15), 0.26),   # 1Y vol  
                (date(2026, 1, 15), 0.24),   # 2Y vol
                (date(2027, 1, 15), 0.23),   # 3Y vol
            ]),
            dividend_model=ContinuousDividend(yield_rate=0.005),
            currency="USD",
        ),
        "GOOG": Underlying(
            ticker="GOOG",
            spot=140.0,
            vol_surface=PiecewiseConstantVol(tenors=[
                (date(2024, 7, 15), 0.32),
                (date(2025, 1, 15), 0.30),
                (date(2026, 1, 15), 0.28),
                (date(2027, 1, 15), 0.27),
            ]),
            dividend_model=ContinuousDividend(yield_rate=0.0),  # No dividend
            currency="USD",
        ),
        "MSFT": Underlying(
            ticker="MSFT",
            spot=390.0,
            vol_surface=PiecewiseConstantVol(tenors=[
                (date(2024, 7, 15), 0.25),
                (date(2025, 1, 15), 0.24),
                (date(2026, 1, 15), 0.23),
                (date(2027, 1, 15), 0.22),
            ]),
            dividend_model=ContinuousDividend(yield_rate=0.008),
            currency="USD",
        ),
    }
    
    # Correlation matrix
    assets = ["AAPL", "GOOG", "MSFT"]
    correlation = CorrelationMatrix.from_dict(assets, {
        "AAPL_GOOG": 0.65,
        "AAPL_MSFT": 0.70,
        "GOOG_MSFT": 0.60,
    })
    
    return MarketData(
        valuation_date=valuation_date,
        underlyings=underlyings,
        rate_curve=rate_curve,
        correlation=correlation,
    )


def main() -> None:
    """Main entry point."""
    print("=" * 60)
    print("Structured Products Pricer - Phase A Demo")
    print("=" * 60)
    
    # Load product from JSON
    term_sheet_path = Path(__file__).parent / "autocallable_wof.json"
    print(f"\n1. Loading product from: {term_sheet_path.name}")
    
    product = load_product(term_sheet_path)
    print(f"   Product ID: {product.product_id}")
    print(f"   Underlyings: {', '.join(product.underlyings)}")
    print(f"   Notional: ${product.notional:,.0f}")
    print(f"   Maturity: {product.maturity_date}")
    print(f"   Worst-of: {product.worst_of}")
    print(f"   Autocall dates: {len(product.autocall_schedule)}")
    print(f"   Coupon dates: {len(product.coupon_schedule)}")
    if product.ki_barrier:
        print(f"   KI Barrier: {product.ki_barrier.level:.0%} ({product.ki_barrier.barrier_type.value})")
    
    # Build market data
    print(f"\n2. Building market data...")
    market = build_sample_market()
    print(f"   Valuation date: {market.valuation_date}")
    for ticker, underlying in market.underlyings.items():
        vol = underlying.vol_surface.get_vol(market.valuation_date, product.maturity_date)
        print(f"   {ticker}: Spot=${underlying.spot:.2f}, Vol={vol:.1%}")
    
    # Run Monte Carlo pricing
    print(f"\n3. Running Monte Carlo simulation...")
    engine = MonteCarloEngine(
        num_paths=50_000,  # Reduced for demo
        seed=42,
        antithetic=True,
    )
    
    result = engine.price(product, market)
    
    print(f"   Paths: {result.num_paths:,}")
    print(f"   Time: {result.computation_time_ms:.1f} ms")
    
    # Generate and print report
    print(f"\n4. Generating risk report...")
    report = generate_report(product, result)
    report.print_summary()
    
    # Note about Phase A
    print("\n[NOTE] This is Phase A - event engine is stubbed.")
    print("Full payoff evaluation will be implemented in Phase B.")
    print("Greeks calculation will be implemented in Phase C.")


if __name__ == "__main__":
    main()
