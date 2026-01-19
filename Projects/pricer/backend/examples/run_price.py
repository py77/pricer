#!/usr/bin/env python3
"""
Example: Load, validate, and price a structured product.

Usage:
    python examples/run_price.py [term_sheet.json] [--paths N] [--seed S] [--verbose]
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


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Price a structured product from JSON term sheet"
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
        default=50_000,
        help="Number of Monte Carlo paths"
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
        "--verbose", "-v",
        action="store_true",
        help="Print detailed output"
    )
    
    args = parser.parse_args()
    term_sheet_path = Path(args.term_sheet)
    
    print("=" * 70)
    print("STRUCTURED PRODUCTS PRICER")
    print("=" * 70)
    
    try:
        # 1. Load and validate term sheet
        print(f"\n[1/3] Loading term sheet: {term_sheet_path.name}")
        ts = load_term_sheet(term_sheet_path)
        
        if args.verbose:
            print_term_sheet_summary(ts)
        else:
            print(f"      Product ID: {ts.meta.product_id}")
            print(f"      Underlyings: {', '.join(u.id for u in ts.underlyings)}")
            print(f"      Notional: {ts.meta.currency} {ts.meta.notional:,.0f}")
        
        # 2. Configure and run pricer
        print(f"\n[2/3] Running Monte Carlo simulation...")
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
        
        # 3. Print results
        print(f"\n[3/3] Generating report...")
        print_pricing_report(ts, result)
        
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
