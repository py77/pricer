/**
 * API client for Pricer backend.
 * Communicates with FastAPI server on port 8000.
 */

const API_BASE = 'http://localhost:8000';

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
    const res = await fetch(`${API_BASE}/health`);
    if (!res.ok) throw new Error('API not available');
    return res.json();
}

export async function getExampleSchema(): Promise<Record<string, unknown>> {
    const res = await fetch(`${API_BASE}/schema`);
    if (!res.ok) throw new Error('Failed to fetch schema');
    return res.json();
}

export async function priceProduct(
    termSheet: Record<string, unknown>,
    runConfig: RunConfig
): Promise<PriceResponse> {
    const res = await fetch(`${API_BASE}/price`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            term_sheet: termSheet,
            run_config: runConfig,
        }),
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
    const res = await fetch(`${API_BASE}/risk`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            term_sheet: termSheet,
            run_config: runConfig,
            bump_config: bumpConfig,
        }),
    });

    if (!res.ok) {
        const error = await res.json();
        throw new Error(error.detail || `HTTP ${res.status}`);
    }

    return res.json();
}
