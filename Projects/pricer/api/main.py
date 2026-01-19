"""
FastAPI wrapper for structured products pricer.

Provides HTTP endpoints for pricing and risk analysis.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any
from datetime import date
import traceback

# Import backend (installed as editable package)
from pricer.products.schema import TermSheet, load_term_sheet
from pricer.pricers.autocall_pricer import AutocallPricer, PricingConfig
from pricer.risk.greeks import compute_greeks, BumpingConfig, GreeksResult
from pricer.reporting import (
    generate_cashflow_report,
    compute_pv_decomposition,
    CashflowReport,
    PVDecomposition,
)


app = FastAPI(
    title="Structured Products Pricer API",
    description="API for pricing autocallable structured products with Greeks",
    version="1.0.0",
)

# CORS for UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://pricer-six.vercel.app",
        "https://*.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==============================================================================
# Request/Response Models
# ==============================================================================

class RunConfig(BaseModel):
    """Configuration for Monte Carlo simulation."""
    paths: int = Field(default=100_000, ge=1000, le=1_000_000)
    seed: Optional[int] = Field(default=42)
    block_size: int = Field(default=50_000, ge=1000)


class BumpConfig(BaseModel):
    """Configuration for Greeks calculation."""
    spot_bump: float = Field(default=0.01, gt=0, le=0.10)
    vol_bump: float = Field(default=0.01, gt=0, le=0.10)
    include_rho: bool = Field(default=False)


class PriceRequest(BaseModel):
    """Request body for /price endpoint."""
    term_sheet: Dict[str, Any]
    run_config: Optional[RunConfig] = None


class RiskRequest(BaseModel):
    """Request body for /risk endpoint."""
    term_sheet: Dict[str, Any]
    run_config: Optional[RunConfig] = None
    bump_config: Optional[BumpConfig] = None


class CashflowEntryResponse(BaseModel):
    """Single cashflow entry."""
    date: str
    payment_date: str
    type: str
    expected_amount: float
    discount_factor: float
    pv_contribution: float
    probability: float


class DecompositionResponse(BaseModel):
    """PV decomposition breakdown."""
    coupon_pv: float
    redemption_pv: float
    autocall_redemption_pv: float
    maturity_redemption_pv: float
    total_pv: float


class SummaryResponse(BaseModel):
    """Pricing summary."""
    pv: float
    pv_std_error: float
    pv_pct_notional: float
    autocall_probability: float
    ki_probability: float
    expected_coupon_count: float
    expected_life_years: float
    num_paths: int
    computation_time_ms: float


class PriceResponse(BaseModel):
    """Response from /price endpoint."""
    summary: SummaryResponse
    cashflows: List[CashflowEntryResponse]
    decomposition: DecompositionResponse


class GreeksResponse(BaseModel):
    """Greeks data."""
    delta: Dict[str, float]
    delta_pct: Dict[str, float]
    vega: Dict[str, float]
    rho: Optional[float] = None


class RiskResponse(BaseModel):
    """Response from /risk endpoint."""
    summary: SummaryResponse
    greeks: GreeksResponse
    cashflows: List[CashflowEntryResponse]
    decomposition: DecompositionResponse


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str


class ErrorResponse(BaseModel):
    """Error response."""
    error: str
    detail: str


# ==============================================================================
# Endpoints
# ==============================================================================

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(status="healthy", version="1.0.0")


@app.get("/schema")
async def get_example_schema():
    """Get example term sheet schema."""
    import json
    from pathlib import Path
    
    example_path = Path(__file__).parent.parent / "backend" / "examples" / "autocall_worstof_continuous_ki.json"
    
    if not example_path.exists():
        raise HTTPException(status_code=404, detail="Example schema not found")
    
    with open(example_path) as f:
        return json.load(f)


@app.post("/price", response_model=PriceResponse)
async def price_product(request: PriceRequest):
    """
    Price a structured product.
    
    Returns PV, summary statistics, cashflow table, and PV decomposition.
    """
    try:
        # Validate and parse term sheet
        ts = TermSheet(**request.term_sheet)
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid term sheet: {str(e)}"
        )
    
    try:
        # Set up pricing config
        run_cfg = request.run_config or RunConfig()
        config = PricingConfig(
            num_paths=run_cfg.paths,
            seed=run_cfg.seed,
            block_size=run_cfg.block_size,
        )
        
        # Run pricing
        pricer = AutocallPricer(config)
        result = pricer.price(ts)
        
        # Generate cashflow report
        report = generate_cashflow_report(ts, config)
        
        # Compute PV decomposition
        decomp = compute_pv_decomposition(ts, config)
        
        # Build response
        notional = ts.meta.notional
        
        summary = SummaryResponse(
            pv=result.pv,
            pv_std_error=result.pv_std_error,
            pv_pct_notional=result.pv / notional,
            autocall_probability=result.autocall_probability,
            ki_probability=result.ki_probability,
            expected_coupon_count=result.expected_coupon_count,
            expected_life_years=result.expected_life,
            num_paths=result.num_paths,
            computation_time_ms=result.computation_time_ms,
        )
        
        cashflows = [
            CashflowEntryResponse(
                date=cf.date.isoformat(),
                payment_date=cf.payment_date.isoformat(),
                type=cf.type,
                expected_amount=cf.expected_amount,
                discount_factor=cf.discount_factor,
                pv_contribution=cf.pv_contribution,
                probability=cf.probability,
            )
            for cf in report.cashflows
        ]
        
        decomposition = DecompositionResponse(
            coupon_pv=decomp.coupon_pv,
            redemption_pv=decomp.redemption_pv,
            autocall_redemption_pv=decomp.autocall_redemption_pv,
            maturity_redemption_pv=decomp.maturity_redemption_pv,
            total_pv=decomp.total_pv,
        )
        
        return PriceResponse(
            summary=summary,
            cashflows=cashflows,
            decomposition=decomposition,
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Pricing error: {str(e)}\n{traceback.format_exc()}"
        )


@app.post("/risk", response_model=RiskResponse)
async def analyze_risk(request: RiskRequest):
    """
    Run risk analysis with Greeks.
    
    Returns PV, Greeks (Delta, Vega, optional Rho), cashflows, and decomposition.
    """
    try:
        # Validate and parse term sheet
        ts = TermSheet(**request.term_sheet)
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid term sheet: {str(e)}"
        )
    
    try:
        # Set up configs
        run_cfg = request.run_config or RunConfig()
        bump_cfg = request.bump_config or BumpConfig()
        
        pricing_config = PricingConfig(
            num_paths=run_cfg.paths,
            seed=run_cfg.seed,
            block_size=run_cfg.block_size,
        )
        
        bumping_config = BumpingConfig(
            delta_bump=bump_cfg.spot_bump,
            vega_bump=bump_cfg.vol_bump,
            compute_rho=bump_cfg.include_rho,
            use_central_diff=True,
        )
        
        # Compute Greeks
        greeks_result = compute_greeks(ts, pricing_config, bumping_config)
        
        # Run base pricing for detailed stats
        pricer = AutocallPricer(pricing_config)
        pricing_result = pricer.price(ts)
        
        # Generate cashflow report
        report = generate_cashflow_report(ts, pricing_config)
        
        # Compute PV decomposition
        decomp = compute_pv_decomposition(ts, pricing_config)
        
        # Build response
        notional = ts.meta.notional
        
        summary = SummaryResponse(
            pv=greeks_result.base_pv,
            pv_std_error=greeks_result.base_pv_std_error,
            pv_pct_notional=greeks_result.base_pv / notional,
            autocall_probability=pricing_result.autocall_probability,
            ki_probability=pricing_result.ki_probability,
            expected_coupon_count=pricing_result.expected_coupon_count,
            expected_life_years=pricing_result.expected_life,
            num_paths=run_cfg.paths,
            computation_time_ms=pricing_result.computation_time_ms,
        )
        
        greeks = GreeksResponse(
            delta=greeks_result.delta,
            delta_pct=greeks_result.delta_pct,
            vega=greeks_result.vega,
            rho=greeks_result.rho,
        )
        
        cashflows = [
            CashflowEntryResponse(
                date=cf.date.isoformat(),
                payment_date=cf.payment_date.isoformat(),
                type=cf.type,
                expected_amount=cf.expected_amount,
                discount_factor=cf.discount_factor,
                pv_contribution=cf.pv_contribution,
                probability=cf.probability,
            )
            for cf in report.cashflows
        ]
        
        decomposition = DecompositionResponse(
            coupon_pv=decomp.coupon_pv,
            redemption_pv=decomp.redemption_pv,
            autocall_redemption_pv=decomp.autocall_redemption_pv,
            maturity_redemption_pv=decomp.maturity_redemption_pv,
            total_pv=decomp.total_pv,
        )
        
        return RiskResponse(
            summary=summary,
            greeks=greeks,
            cashflows=cashflows,
            decomposition=decomposition,
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Risk analysis error: {str(e)}\n{traceback.format_exc()}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
