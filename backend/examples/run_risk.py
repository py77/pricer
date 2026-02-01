#!/usr/bin/env python3
"""
Example: Run full risk analysis with Greeks.

Usage:
    python examples/run_risk.py [term_sheet.json] [--paths N] [--seed S] [--block-size B]
"""

import sys
from pathlib import Path
import argparse
import traceback

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pricer.products.schema import load_term_sheet, print_term_sheet_summary
from pricer.pricers.autocall_pricer import (
    AutocallPricer,
    PricingConfig,
    print_pricing_report,
)
from pricer.risk.greeks import compute_greeks, BumpingConfig, GreeksResult
from pricer.reporting import (
    generate_cashflow_report,
    compute_pv_decomposition,
)


def print_greeks_table(result: GreeksResult, currency: str = "USD") -> None:
    """Print formatted Greeks table."""
    print("\n" + "=" * 70)
    print("GREEKS REPORT (Central Diff, CRN)")
    print("=" * 70)
    
    print(f"\n--- DELTA (dPV for 1% spot move) ---")
    print(f"{'Underlying':<15} {'Delta':>15} {'Delta %':>12}")
    print("-" * 45)
    for asset, delta in result.delta.items():
        delta_pct = result.delta_pct.get(asset, 0)
        print(f"{asset:<15} {delta:>15,.2f} {delta_pct:>11.2f}%")
    
    print(f"\n--- VEGA (dPV for 1 vol pt bump) ---")
    print(f"{'Underlying':<15} {'Vega':>15}")
    print("-" * 32)
    for asset, vega in result.vega.items():
        print(f"{asset:<15} {vega:>15,.2f}")
    
    if result.rho is not None:
        print(f"\n--- RHO (dPV for 1bp rate bump) ---")
        print(f"Rho: {result.rho:,.2f}")
    
    print("=" * 70)


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run risk analysis with Greeks on a structured product"
    )
    parser.add_argument(
        "term_sheet",
        type=str,
        nargs="?",
        default=str(Path(__file__).parent / "autocall_worstof_continuous_ki.json"),
        help="Path to JSON term sheet file"
    )
    parser.add_argument(
        "--paths", "-n",
        type=int,
        default=200_000,
        help="Number of Monte Carlo paths (default: 200,000)"
    )
    parser.add_argument(
        "--seed", "-s",
        type=int,
        default=42,
        help="Random seed for reproducibility"
    )
    parser.add_argument(
        "--block-size", "-b",
        type=int,
        default=50_000,
        help="Block size for memory efficiency (default: 50,000)"
    )
    parser.add_argument(
        "--no-greeks",
        action="store_true",
        help="Skip Greeks calculation (faster)"
    )
    parser.add_argument(
        "--rho",
        action="store_true",
        help="Include Rho (rate sensitivity) in Greeks"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print detailed output"
    )
    
    args = parser.parse_args()
    term_sheet_path = Path(args.term_sheet)
    
    print("=" * 70)
    print("STRUCTURED PRODUCTS RISK ANALYZER")
    print("=" * 70)
    
    try:
        # 1. Load and validate term sheet
        print(f"\n[1/5] Loading term sheet: {term_sheet_path.name}")
        ts = load_term_sheet(term_sheet_path)
        
        if args.verbose:
            print_term_sheet_summary(ts)
        else:
            print(f"      Product ID: {ts.meta.product_id}")
            print(f"      Underlyings: {', '.join(u.id for u in ts.underlyings)}")
            print(f"      Notional: {ts.meta.currency} {ts.meta.notional:,.0f}")
        
        # 2. Configure pricing
        print(f"\n[2/5] Running Monte Carlo simulation...")
        print(f"      Paths: {args.paths:,}")
        print(f"      Seed: {args.seed}")
        print(f"      Block Size: {args.block_size:,}")
        
        config = PricingConfig(
            num_paths=args.paths,
            seed=args.seed,
            antithetic=True,
            block_size=args.block_size,
        )
        pricer = AutocallPricer(config)
        result = pricer.price(ts)
        
        # 3. Print pricing results
        print(f"\n[3/5] Generating pricing report...")
        print_pricing_report(ts, result)
        
        # 4. Greeks calculation
        if not args.no_greeks:
            print(f"\n[4/5] Computing Greeks with CRN...")
            
            bump_config = BumpingConfig(
                delta_bump=0.01,      # 1% spot bump
                vega_bump=0.01,       # 1 vol point
                compute_rho=args.rho,
                use_central_diff=True,
            )
            
            greeks_result = compute_greeks(ts, config, bump_config)
            print_greeks_table(greeks_result, ts.meta.currency)
        else:
            print(f"\n[4/5] Skipping Greeks (--no-greeks)")
        
        # 5. PV Decomposition
        print(f"\n[5/5] Computing PV decomposition...")
        decomp = compute_pv_decomposition(ts, config)
        decomp.print_summary(ts.meta.currency)
        
        # Cashflow table
        print(f"\nGenerating cashflow table...")
        report = generate_cashflow_report(ts, config)
        report.print_cashflow_table()
        
        print(f"\n{'='*70}")
        print(f"ANALYSIS COMPLETE")
        print(f"  Total computation time: {result.computation_time_ms:.1f} ms (pricing)")
        print(f"{'='*70}")
        
        return 0
        
    except FileNotFoundError as e:
        print(f"\nERROR: {e}")
        return 1
        
    except Exception as e:
        print(f"\nERROR: {type(e).__name__}: {e}")
        if args.verbose:
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
