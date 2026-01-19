"""
Risk reporting for structured products.

Generates formatted reports with PV, Greeks, and cashflow tables.
"""

from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional, Any
import json

from pricer.products.base import Product
from pricer.engines.base import PricingResult, CashFlow


@dataclass
class RiskReport:
    """
    Risk report for a structured product.
    
    Consolidates pricing result, Greeks, and cashflow analysis.
    """
    
    product_id: str
    valuation_date: date
    result: PricingResult
    greeks: Dict[str, float]
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize report to dictionary."""
        return {
            "product_id": self.product_id,
            "valuation_date": self.valuation_date.isoformat(),
            "pv": self.result.pv,
            "pv_std_error": self.result.pv_std_error,
            "autocall_probability": self.result.autocall_probability,
            "ki_probability": self.result.ki_probability,
            "expected_coupon_count": self.result.expected_coupon_count,
            "expected_life": self.result.expected_life,
            "greeks": self.greeks,
            "num_paths": self.result.num_paths,
            "computation_time_ms": self.result.computation_time_ms,
        }
    
    def to_json(self, indent: int = 2) -> str:
        """Serialize report to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)
    
    def print_summary(self) -> None:
        """Print formatted summary to console."""
        print(f"\n{'='*60}")
        print(f"Risk Report: {self.product_id}")
        print(f"Valuation Date: {self.valuation_date}")
        print(f"{'='*60}")
        
        print(f"\n--- Pricing ---")
        print(f"PV:              {self.result.pv:,.2f}")
        print(f"Std Error:       {self.result.pv_std_error:,.4f}")
        print(f"Paths:           {self.result.num_paths:,}")
        print(f"Time:            {self.result.computation_time_ms:.1f} ms")
        
        print(f"\n--- Probabilities ---")
        print(f"Autocall Prob:   {self.result.autocall_probability:.2%}")
        print(f"KI Prob:         {self.result.ki_probability:.2%}")
        print(f"Exp. Coupons:    {self.result.expected_coupon_count:.2f}")
        print(f"Exp. Life:       {self.result.expected_life:.2f} years")
        
        if self.greeks:
            print(f"\n--- Greeks ---")
            for name, value in sorted(self.greeks.items()):
                if name != "pv":
                    print(f"{name:15s} {value:,.4f}")
        
        print(f"\n{'='*60}\n")


def generate_report(
    product: Product,
    result: PricingResult,
    greeks: Optional[Dict[str, float]] = None
) -> RiskReport:
    """
    Generate risk report from pricing result.
    
    Args:
        product: Product that was priced
        result: Pricing result
        greeks: Optional Greeks dictionary
        
    Returns:
        RiskReport instance
    """
    return RiskReport(
        product_id=product.product_id,
        valuation_date=result.valuation_date or date.today(),
        result=result,
        greeks=greeks or {},
    )
