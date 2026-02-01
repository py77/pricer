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

# Market data (optional - may not be installed)
try:
    from pricer.market import fetch_market_data_snapshot, MarketDataSnapshot
    HAS_MARKET_DATA = True
except ImportError:
    HAS_MARKET_DATA = False

# Vanilla pricing engines
from pricer.engines.black_scholes import (
    bs_call_price,
    bs_put_price,
    bs_greeks,
    price_vanilla,
    implied_vol,
    Greeks,
    VanillaResult,
)
from pricer.engines.tree_pricer import (
    BinomialTree,
    TrinomialTree,
    price_american,
    price_european_tree,
    TreeResult,
    ExerciseStyle,
    OptionType,
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
        "http://localhost:3001",
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


# ==============================================================================
# Market Data Endpoint
# ==============================================================================

class MarketDataResponse(BaseModel):
    """Response from /market-data endpoint."""
    as_of_date: str
    underlyings: Dict[str, Dict[str, Any]]
    correlations: Dict[str, float]
    risk_free_rate: float


@app.get("/market-data", response_model=MarketDataResponse)
async def get_market_data(tickers: str, maturity_years: int = 3):
    """
    Fetch live market data for given tickers.
    
    Args:
        tickers: Comma-separated list of tickers (e.g., "AAPL,GOOG,MSFT")
        maturity_years: Years to maturity for term structure (default 3)
        
    Returns:
        Market data including spot prices, volatility, dividends, correlations
    """
    if not HAS_MARKET_DATA:
        raise HTTPException(
            status_code=501,
            detail="Market data not available. Install yfinance: pip install yfinance"
        )
    
    try:
        ticker_list = [t.strip().upper() for t in tickers.split(",")]
        
        if not ticker_list:
            raise HTTPException(status_code=400, detail="No tickers provided")
        
        from datetime import date, timedelta
        valuation_date = date.today()
        maturity_date = valuation_date + timedelta(days=365 * maturity_years)
        
        snapshot = fetch_market_data_snapshot(
            ticker_list,
            valuation_date=valuation_date,
            maturity_date=maturity_date,
        )
        
        # Convert to JSON-serializable format
        underlyings_data = {}
        for ticker, data in snapshot.underlyings.items():
            underlyings_data[ticker] = {
                "spot": data.spot,
                "currency": data.currency,
                "historical_vol": data.historical_vol,
                "dividend_yield": data.dividend_yield,
                "vol_term_structure": [
                    {"date": v.date.isoformat(), "vol": v.vol}
                    for v in data.vol_term_structure
                ],
                "dividends": [
                    {"ex_date": d.ex_date.isoformat(), "amount": d.amount}
                    for d in data.dividends
                ],
            }
        
        return MarketDataResponse(
            as_of_date=snapshot.as_of_date.isoformat(),
            underlyings=underlyings_data,
            correlations=snapshot.correlations,
            risk_free_rate=snapshot.risk_free_rate,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Market data error: {str(e)}\n{traceback.format_exc()}"
        )


# ==============================================================================
# Vanilla Pricing Endpoints
# ==============================================================================

class VanillaPriceRequest(BaseModel):
    """Request for vanilla option pricing."""
    spot: float = Field(..., gt=0, description="Spot price")
    strike: float = Field(..., gt=0, description="Strike price")
    time_to_expiry: float = Field(..., gt=0, le=30, description="Time to expiry in years")
    rate: float = Field(default=0.05, description="Risk-free rate")
    dividend_yield: float = Field(default=0.0, ge=0, description="Continuous dividend yield")
    volatility: float = Field(..., gt=0, le=5.0, description="Volatility")
    is_call: bool = Field(default=True, description="True for call, False for put")
    exercise: str = Field(default="european", pattern="^(european|american)$")
    method: str = Field(default="black_scholes", pattern="^(black_scholes|binomial|trinomial)$")
    tree_steps: int = Field(default=200, ge=10, le=1000, description="Steps for tree pricing")


class VanillaPriceResponse(BaseModel):
    """Response from vanilla pricing."""
    price: float
    method: str
    delta: float
    gamma: float
    theta: float
    vega: Optional[float] = None
    rho: Optional[float] = None


class ImpliedVolRequest(BaseModel):
    """Request for implied volatility calculation."""
    price: float = Field(..., gt=0, description="Option market price")
    spot: float = Field(..., gt=0, description="Spot price")
    strike: float = Field(..., gt=0, description="Strike price")
    time_to_expiry: float = Field(..., gt=0, le=30, description="Time to expiry in years")
    rate: float = Field(default=0.05, description="Risk-free rate")
    dividend_yield: float = Field(default=0.0, ge=0, description="Continuous dividend yield")
    is_call: bool = Field(default=True, description="True for call, False for put")


class ImpliedVolResponse(BaseModel):
    """Response from implied volatility calculation."""
    implied_vol: Optional[float]
    converged: bool


@app.post("/vanilla/price", response_model=VanillaPriceResponse)
async def price_vanilla_option(request: VanillaPriceRequest):
    """
    Price a vanilla European or American option.
    
    Methods:
    - black_scholes: Closed-form Black-Scholes (European only)
    - binomial: CRR binomial tree
    - trinomial: Trinomial tree
    """
    try:
        S = request.spot
        K = request.strike
        T = request.time_to_expiry
        r = request.rate
        q = request.dividend_yield
        sigma = request.volatility
        is_call = request.is_call
        
        if request.method == "black_scholes":
            if request.exercise == "american":
                raise HTTPException(
                    status_code=400,
                    detail="Black-Scholes only supports European exercise. Use binomial or trinomial for American."
                )
            
            result = price_vanilla(S, K, T, r, q, sigma, is_call)
            return VanillaPriceResponse(
                price=result.price,
                method="black_scholes",
                delta=result.greeks.delta,
                gamma=result.greeks.gamma,
                theta=result.greeks.theta,
                vega=result.greeks.vega,
                rho=result.greeks.rho,
            )
        
        elif request.method == "binomial":
            tree = BinomialTree(S, K, T, r, q, sigma, request.tree_steps)
            exercise_style = ExerciseStyle.AMERICAN if request.exercise == "american" else ExerciseStyle.EUROPEAN
            option_type = OptionType.CALL if is_call else OptionType.PUT
            result = tree.price(option_type, exercise_style)
            
            return VanillaPriceResponse(
                price=result.price,
                method="binomial",
                delta=result.delta,
                gamma=result.gamma,
                theta=result.theta,
            )
        
        else:  # trinomial
            tree = TrinomialTree(S, K, T, r, q, sigma, request.tree_steps)
            exercise_style = ExerciseStyle.AMERICAN if request.exercise == "american" else ExerciseStyle.EUROPEAN
            option_type = OptionType.CALL if is_call else OptionType.PUT
            result = tree.price(option_type, exercise_style)
            
            return VanillaPriceResponse(
                price=result.price,
                method="trinomial",
                delta=result.delta,
                gamma=result.gamma,
                theta=result.theta,
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Pricing error: {str(e)}\n{traceback.format_exc()}"
        )


@app.post("/vanilla/implied-vol", response_model=ImpliedVolResponse)
async def calculate_implied_vol(request: ImpliedVolRequest):
    """
    Calculate implied volatility from option price.
    
    Uses Newton-Raphson with bisection fallback.
    """
    try:
        iv = implied_vol(
            price=request.price,
            S=request.spot,
            K=request.strike,
            T=request.time_to_expiry,
            r=request.rate,
            q=request.dividend_yield,
            is_call=request.is_call,
        )
        
        return ImpliedVolResponse(
            implied_vol=iv,
            converged=iv is not None,
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Implied vol error: {str(e)}\n{traceback.format_exc()}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

