/**
 * API client for Pricer backend.
 * Communicates with FastAPI server.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'https://pricer-api-883624022691.us-central1.run.app';

const DEFAULT_TIMEOUT = 30_000; // 30s for GET requests
const LONG_TIMEOUT = 120_000;   // 120s for POST requests (simulation can take time)

async function fetchWithTimeout(
    url: string,
    options: RequestInit & { timeout?: number } = {}
): Promise<Response> {
    const { timeout = DEFAULT_TIMEOUT, ...fetchOptions } = options;
    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), timeout);

    try {
        const response = await fetch(url, {
            ...fetchOptions,
            signal: controller.signal,
        });
        return response;
    } catch (err: unknown) {
        if (err instanceof Error && err.name === 'AbortError') {
            throw new Error(`Request timed out after ${timeout / 1000}s — the backend may be starting up (Render free tier). Try again in ~30s.`);
        }
        throw err;
    } finally {
        clearTimeout(id);
    }
}

// Types
export interface RunConfig {
    paths: number;
    seed: number;
    block_size: number;
}

export interface BumpConfig {
    spot_bump: number;
    vol_bump: number;
    include_rho: boolean;
}

export interface Summary {
    pv: number;
    pv_std_error: number;
    pv_pct_notional: number;
    autocall_probability: number;
    ki_probability: number;
    expected_coupon_count: number;
    expected_life_years: number;
    num_paths: number;
    computation_time_ms: number;
}

export interface CashflowEntry {
    date: string;
    payment_date: string;
    type: string;
    expected_amount: number;
    discount_factor: number;
    pv_contribution: number;
    probability: number;
}

export interface Decomposition {
    coupon_pv: number;
    redemption_pv: number;
    autocall_redemption_pv: number;
    maturity_redemption_pv: number;
    total_pv: number;
}

export interface Greeks {
    delta: Record<string, number>;
    delta_pct: Record<string, number>;
    vega: Record<string, number>;
    rho: number | null;
}

export interface PriceResponse {
    summary: Summary;
    cashflows: CashflowEntry[];
    decomposition: Decomposition;
}

export interface RiskResponse {
    summary: Summary;
    greeks: Greeks;
    cashflows: CashflowEntry[];
    decomposition: Decomposition;
}

export interface ApiError {
    detail: string;
}

// API Functions
export async function healthCheck(): Promise<{ status: string; version: string }> {
    const res = await fetchWithTimeout(`${API_BASE}/health`);
    if (!res.ok) throw new Error('API not available');
    return res.json();
}

export async function getExampleSchema(): Promise<Record<string, unknown>> {
    const res = await fetchWithTimeout(`${API_BASE}/schema`);
    if (!res.ok) throw new Error('Failed to fetch schema');
    return res.json();
}

export async function priceProduct(
    termSheet: Record<string, unknown>,
    runConfig: RunConfig
): Promise<PriceResponse> {
    const res = await fetchWithTimeout(`${API_BASE}/price`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            term_sheet: termSheet,
            run_config: runConfig,
        }),
        timeout: LONG_TIMEOUT,
    });

    if (!res.ok) {
        const error = await res.json();
        throw new Error(error.detail || `HTTP ${res.status}`);
    }

    return res.json();
}

export async function analyzeRisk(
    termSheet: Record<string, unknown>,
    runConfig: RunConfig,
    bumpConfig: BumpConfig
): Promise<RiskResponse> {
    const res = await fetchWithTimeout(`${API_BASE}/risk`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            term_sheet: termSheet,
            run_config: runConfig,
            bump_config: bumpConfig,
        }),
        timeout: LONG_TIMEOUT,
    });

    if (!res.ok) {
        const error = await res.json();
        throw new Error(error.detail || `HTTP ${res.status}`);
    }

    return res.json();
}

// Market Data Types
export interface MarketDataUnderlying {
    spot: number;
    currency: string;
    historical_vol: number;
    dividend_yield: number;
    vol_term_structure: Array<{ date: string; vol: number }>;
    dividends: Array<{ ex_date: string; amount: number }>;
}

export interface MarketDataResponse {
    as_of_date: string;
    underlyings: Record<string, MarketDataUnderlying>;
    correlations: Record<string, number>;
    risk_free_rate: number;
}

export async function fetchMarketData(tickers: string[]): Promise<MarketDataResponse> {
    const tickerList = tickers.join(',');
    const res = await fetchWithTimeout(`${API_BASE}/market-data?tickers=${encodeURIComponent(tickerList)}`);

    if (!res.ok) {
        const error = await res.json();
        throw new Error(error.detail || `HTTP ${res.status}`);
    }

    return res.json();
}

