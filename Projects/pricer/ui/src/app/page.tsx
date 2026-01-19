'use client';

import { useState, useEffect } from 'react';
import dynamic from 'next/dynamic';
import { priceProduct, getExampleSchema, PriceResponse, RunConfig } from '@/api/client';

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

export default function PricingPage() {
    const [termSheet, setTermSheet] = useState<string>('{}');
    const [config, setConfig] = useState<RunConfig>(DEFAULT_CONFIG);
    const [result, setResult] = useState<PriceResponse | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);

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
            <div className="card" style={{ marginBottom: '1.5rem' }}>
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
                    <button className="btn btn-primary" onClick={handleRunPricing} disabled={loading}>
                        {loading ? '⏳ Running...' : '▶ Run Pricing'}
                    </button>
                </div>
            </div>

            {error && <div className="error-box" style={{ marginBottom: '1.5rem' }}>{error}</div>}

            <div className="editor-layout">
                {/* Editor Panel */}
                <div className="editor-panel">
                    <div className="editor-header">
                        <span className="editor-title">Term Sheet (JSON)</span>
                    </div>
                    <div className="editor-container">
                        <MonacoEditor
                            height="100%"
                            language="json"
                            theme="vs-dark"
                            value={termSheet}
                            onChange={(value) => setTermSheet(value || '{}')}
                            options={{
                                minimap: { enabled: false },
                                fontSize: 13,
                                lineNumbers: 'on',
                                scrollBeyondLastLine: false,
                                wordWrap: 'on',
                            }}
                        />
                    </div>
                </div>

                {/* Results Panel */}
                <div className="results-panel">
                    {result ? (
                        <>
                            {/* Summary Cards */}
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

                            {/* Decomposition */}
                            <div className="card">
                                <h3 style={{ marginBottom: '1rem' }}>PV Decomposition</h3>
                                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1rem' }}>
                                    <div>
                                        <div style={{ color: 'var(--success)', fontSize: '1.25rem', fontWeight: 600 }}>
                                            ${formatNumber(result.decomposition.coupon_pv, 0)}
                                        </div>
                                        <div className="stat-label">Coupon PV</div>
                                    </div>
                                    <div>
                                        <div style={{ color: 'var(--primary)', fontSize: '1.25rem', fontWeight: 600 }}>
                                            ${formatNumber(result.decomposition.autocall_redemption_pv, 0)}
                                        </div>
                                        <div className="stat-label">Autocall Redemption</div>
                                    </div>
                                    <div>
                                        <div style={{ color: 'var(--warning)', fontSize: '1.25rem', fontWeight: 600 }}>
                                            ${formatNumber(result.decomposition.maturity_redemption_pv, 0)}
                                        </div>
                                        <div className="stat-label">Maturity Redemption</div>
                                    </div>
                                </div>
                            </div>

                            {/* Cashflows Table */}
                            <div className="card">
                                <h3 style={{ marginBottom: '1rem' }}>Expected Cashflows</h3>
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
                            </div>

                            {/* Stats */}
                            <div className="card">
                                <div style={{ display: 'flex', gap: '2rem', fontSize: '0.875rem', color: 'var(--muted)' }}>
                                    <span>Paths: {result.summary.num_paths.toLocaleString()}</span>
                                    <span>Std Error: ${formatNumber(result.summary.pv_std_error)}</span>
                                    <span>Time: {result.summary.computation_time_ms.toFixed(0)}ms</span>
                                </div>
                            </div>
                        </>
                    ) : (
                        <div className="card" style={{ textAlign: 'center', padding: '3rem' }}>
                            <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>📈</div>
                            <div style={{ color: 'var(--muted)' }}>
                                Click "Run Pricing" to calculate PV and statistics
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
