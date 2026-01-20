'use client';

import { useState, useEffect } from 'react';
import dynamic from 'next/dynamic';
import { priceProduct, getExampleSchema, fetchMarketData, PriceResponse, RunConfig } from '@/api/client';

// Dynamic import Monaco to avoid SSR issues
const MonacoEditor = dynamic(
    () => import('@monaco-editor/react'),
    { ssr: false, loading: () => <div className="loading"><div className="spinner" />Loading editor...</div> }
);

const DEFAULT_CONFIG: RunConfig = {
    paths: 100000,
    seed: 42,
    block_size: 50000,
};

function formatNumber(n: number, decimals = 2): string {
    return n.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

function formatPercent(n: number): string {
    return (n * 100).toFixed(2) + '%';
}

// Retro Window Component
function RetroWindow({ 
    title, 
    color = 'cyan', 
    children 
}: { 
    title: string; 
    color?: 'cyan' | 'yellow' | 'pink' | 'green' | 'blue';
    children: React.ReactNode;
}) {
    return (
        <div className="retro-window">
            <div className={`retro-title-bar ${color}`}>
                <div className="window-dots">
                    <div className="window-dot red"></div>
                    <div className="window-dot yellow"></div>
                    <div className="window-dot green"></div>
                </div>
                <span className="window-title">{title}</span>
                <div style={{ width: '44px' }}></div>
            </div>
            <div className="window-content">
                {children}
            </div>
        </div>
    );
}

export default function PricingPage() {
    const [termSheet, setTermSheet] = useState<string>('{}');
    const [config, setConfig] = useState<RunConfig>(DEFAULT_CONFIG);
    const [result, setResult] = useState<PriceResponse | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const [fetchingData, setFetchingData] = useState(false);

    // Load example on mount
    useEffect(() => {
        getExampleSchema()
            .then(schema => setTermSheet(JSON.stringify(schema, null, 2)))
            .catch(err => setError('Failed to load example: ' + err.message));
    }, []);

    const handleLoadExample = async () => {
        try {
            const schema = await getExampleSchema();
            setTermSheet(JSON.stringify(schema, null, 2));
            setError(null);
        } catch (err: any) {
            setError('Failed to load example: ' + err.message);
        }
    };

    const handleFetchLiveData = async () => {
        setFetchingData(true);
        setError(null);

        try {
            const parsed = JSON.parse(termSheet);

            // Extract tickers from term sheet
            const tickers: string[] = (parsed.underlyings || []).map((u: any) => u.id);
            if (tickers.length === 0) {
                throw new Error('No underlyings found in term sheet');
            }

            // Fetch live market data
            const marketData = await fetchMarketData(tickers);

            // Calculate date shift: from old valuation_date to today
            const oldValDate = new Date(parsed.meta?.valuation_date || new Date());
            const today = new Date();
            const dayShift = Math.round((today.getTime() - oldValDate.getTime()) / (1000 * 60 * 60 * 24));

            // Helper to shift a date string by dayShift days
            const shiftDate = (dateStr: string): string => {
                const d = new Date(dateStr);
                d.setDate(d.getDate() + dayShift);
                return d.toISOString().split('T')[0];
            };

            // Update meta dates
            const todayStr = today.toISOString().split('T')[0];
            parsed.meta = {
                ...parsed.meta,
                valuation_date: todayStr,
                trade_date: shiftDate(parsed.meta?.trade_date || todayStr),
                settlement_date: shiftDate(parsed.meta?.settlement_date || todayStr),
                maturity_date: shiftDate(parsed.meta?.maturity_date || todayStr),
                maturity_payment_date: shiftDate(parsed.meta?.maturity_payment_date || todayStr),
            };

            parsed.discount_curve = { ...parsed.discount_curve, flat_rate: marketData.risk_free_rate };

            // Update schedules dates
            if (parsed.schedules) {
                if (parsed.schedules.observation_dates) {
                    parsed.schedules.observation_dates = parsed.schedules.observation_dates.map(shiftDate);
                }
                if (parsed.schedules.payment_dates) {
                    parsed.schedules.payment_dates = parsed.schedules.payment_dates.map(shiftDate);
                }
            }

            // Update each underlying
            for (const underlying of parsed.underlyings || []) {
                const data = marketData.underlyings[underlying.id];
                if (data) {
                    underlying.spot = data.spot;
                    // Update vol term structure with historical vol and shifted dates
                    if (underlying.vol_model?.term_structure) {
                        underlying.vol_model.term_structure = underlying.vol_model.term_structure.map((v: any) => ({
                            date: shiftDate(v.date),
                            vol: data.historical_vol
                        }));
                    }
                    // Update dividend yield if continuous
                    if (underlying.dividend_model?.type === 'continuous') {
                        underlying.dividend_model.continuous_yield = data.dividend_yield || 0;
                    }
                    // Shift discrete dividend dates
                    if (underlying.dividend_model?.discrete_dividends) {
                        underlying.dividend_model.discrete_dividends = underlying.dividend_model.discrete_dividends.map((d: any) => ({
                            ...d,
                            ex_date: shiftDate(d.ex_date)
                        }));
                    }
                }
            }

            // Update correlations
            if (marketData.correlations && Object.keys(marketData.correlations).length > 0) {
                parsed.correlation = { pairwise: marketData.correlations };
            }

            setTermSheet(JSON.stringify(parsed, null, 2));
        } catch (err: any) {
            setError('Failed to fetch market data: ' + err.message);
        } finally {
            setFetchingData(false);
        }
    };

    const handleRunPricing = async () => {
        setLoading(true);
        setError(null);

        try {
            const parsed = JSON.parse(termSheet);
            const res = await priceProduct(parsed, config);
            setResult(res);
        } catch (err: any) {
            setError(err.message);
            setResult(null);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div>
            <div className="page-header">
                <h1 className="page-title">Pricing</h1>
                <p className="page-description">Price autocallable structured products with Monte Carlo simulation</p>
            </div>

            {/* Controls */}
            <RetroWindow title="Controls" color="yellow">
                <div className="controls-row">
                    <div className="control-group">
                        <label className="control-label">Paths</label>
                        <input
                            type="number"
                            className="control-input"
                            value={config.paths}
                            onChange={e => setConfig({ ...config, paths: parseInt(e.target.value) || 10000 })}
                        />
                    </div>
                    <div className="control-group">
                        <label className="control-label">Seed</label>
                        <input
                            type="number"
                            className="control-input"
                            value={config.seed}
                            onChange={e => setConfig({ ...config, seed: parseInt(e.target.value) || 42 })}
                        />
                    </div>
                    <div className="control-group">
                        <label className="control-label">Block Size</label>
                        <input
                            type="number"
                            className="control-input"
                            value={config.block_size}
                            onChange={e => setConfig({ ...config, block_size: parseInt(e.target.value) || 50000 })}
                        />
                    </div>
                    <button className="btn btn-secondary" onClick={handleLoadExample}>
                        Load Example
                    </button>
                    <button className="btn btn-secondary" onClick={handleFetchLiveData} disabled={fetchingData}>
                        {fetchingData ? 'Fetching...' : 'Fetch Live Data'}
                    </button>
                    <button className="btn btn-primary" onClick={handleRunPricing} disabled={loading}>
                        {loading ? 'Running...' : 'Run Pricing'}
                    </button>
                </div>
            </RetroWindow>

            {error && <div className="error-box" style={{ marginBottom: '1rem' }}>{error}</div>}

            <div className="editor-layout">
                {/* Editor Panel */}
                <div className="editor-panel">
                    <RetroWindow title="Term Sheet (JSON)" color="cyan">
                        <div className="editor-container" style={{ margin: '-12px', marginTop: '-12px' }}>
                            <MonacoEditor
                                height="400px"
                                language="json"
                                theme="vs"
                                value={termSheet}
                                onChange={(value) => setTermSheet(value || '{}')}
                                options={{
                                    minimap: { enabled: false },
                                    fontSize: 13,
                                    lineNumbers: 'on',
                                    scrollBeyondLastLine: false,
                                    wordWrap: 'on',
                                    fontFamily: 'Consolas, monospace',
                                }}
                            />
                        </div>
                    </RetroWindow>
                </div>

                {/* Results Panel */}
                <div className="results-panel">
                    {result ? (
                        <>
                            {/* Summary Cards */}
                            <RetroWindow title="Summary" color="green">
                                <div className="card-grid">
                                    <div className="card">
                                        <div className="stat-value">${formatNumber(result.summary.pv, 0)}</div>
                                        <div className="stat-label">Present Value</div>
                                    </div>
                                    <div className="card">
                                        <div className="stat-value">{formatPercent(result.summary.pv_pct_notional)}</div>
                                        <div className="stat-label">PV % of Notional</div>
                                    </div>
                                    <div className="card">
                                        <div className="stat-value">{formatPercent(result.summary.autocall_probability)}</div>
                                        <div className="stat-label">Autocall Prob</div>
                                    </div>
                                    <div className="card">
                                        <div className="stat-value">{formatPercent(result.summary.ki_probability)}</div>
                                        <div className="stat-label">KI Probability</div>
                                    </div>
                                    <div className="card">
                                        <div className="stat-value">{result.summary.expected_coupon_count.toFixed(2)}</div>
                                        <div className="stat-label">Expected Coupons</div>
                                    </div>
                                    <div className="card">
                                        <div className="stat-value">{result.summary.expected_life_years.toFixed(2)}y</div>
                                        <div className="stat-label">Expected Life</div>
                                    </div>
                                </div>
                            </RetroWindow>

                            {/* Decomposition */}
                            <RetroWindow title="PV Decomposition" color="pink">
                                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1rem' }}>
                                    <div>
                                        <div style={{ color: 'var(--success)', fontSize: '1.25rem', fontWeight: 700 }}>
                                            ${formatNumber(result.decomposition.coupon_pv, 0)}
                                        </div>
                                        <div className="stat-label">Coupon PV</div>
                                    </div>
                                    <div>
                                        <div style={{ color: 'var(--primary)', fontSize: '1.25rem', fontWeight: 700 }}>
                                            ${formatNumber(result.decomposition.autocall_redemption_pv, 0)}
                                        </div>
                                        <div className="stat-label">Autocall Redemption</div>
                                    </div>
                                    <div>
                                        <div style={{ color: 'var(--warning)', fontSize: '1.25rem', fontWeight: 700 }}>
                                            ${formatNumber(result.decomposition.maturity_redemption_pv, 0)}
                                        </div>
                                        <div className="stat-label">Maturity Redemption</div>
                                    </div>
                                </div>
                            </RetroWindow>

                            {/* Cashflows Table */}
                            <RetroWindow title="Expected Cashflows" color="blue">
                                <div className="table-container">
                                    <table>
                                        <thead>
                                            <tr>
                                                <th>Date</th>
                                                <th>Type</th>
                                                <th style={{ textAlign: 'right' }}>Probability</th>
                                                <th style={{ textAlign: 'right' }}>Expected Amt</th>
                                                <th style={{ textAlign: 'right' }}>PV Contrib</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {result.cashflows.map((cf, i) => (
                                                <tr key={i}>
                                                    <td>{cf.date}</td>
                                                    <td>{cf.type}</td>
                                                    <td style={{ textAlign: 'right' }}>{formatPercent(cf.probability)}</td>
                                                    <td style={{ textAlign: 'right' }}>${formatNumber(cf.expected_amount, 0)}</td>
                                                    <td style={{ textAlign: 'right' }}>${formatNumber(cf.pv_contribution, 0)}</td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </RetroWindow>

                            {/* Stats */}
                            <RetroWindow title="Statistics" color="cyan">
                                <div style={{ display: 'flex', gap: '2rem', fontSize: '13px' }}>
                                    <span>Paths: {result.summary.num_paths.toLocaleString()}</span>
                                    <span>Std Error: ${formatNumber(result.summary.pv_std_error)}</span>
                                    <span>Time: {result.summary.computation_time_ms.toFixed(0)}ms</span>
                                </div>
                            </RetroWindow>
                        </>
                    ) : (
                        <RetroWindow title="Results" color="green">
                            <div style={{ textAlign: 'center', padding: '2rem' }}>
                                <div style={{ fontSize: '2.5rem', marginBottom: '0.75rem' }}>📊</div>
                                <div style={{ color: 'var(--muted)' }}>
                                    Click "Run Pricing" to calculate PV and statistics
                                </div>
                            </div>
                        </RetroWindow>
                    )}
                </div>
            </div>
        </div>
    );
}
