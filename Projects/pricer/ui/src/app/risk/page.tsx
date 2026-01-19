'use client';

import { useState, useEffect } from 'react';
import dynamic from 'next/dynamic';
import { analyzeRisk, getExampleSchema, RiskResponse, RunConfig, BumpConfig } from '@/api/client';

const MonacoEditor = dynamic(
    () => import('@monaco-editor/react'),
    { ssr: false, loading: () => <div className="loading"><div className="spinner" />Loading editor...</div> }
);

const DEFAULT_RUN_CONFIG: RunConfig = {
    paths: 100000,
    seed: 42,
    block_size: 50000,
};

const DEFAULT_BUMP_CONFIG: BumpConfig = {
    spot_bump: 0.01,
    vol_bump: 0.01,
    include_rho: false,
};

function formatNumber(n: number, decimals = 2): string {
    return n.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

function formatPercent(n: number): string {
    return (n * 100).toFixed(2) + '%';
}

export default function RiskPage() {
    const [termSheet, setTermSheet] = useState<string>('{}');
    const [runConfig, setRunConfig] = useState<RunConfig>(DEFAULT_RUN_CONFIG);
    const [bumpConfig, setBumpConfig] = useState<BumpConfig>(DEFAULT_BUMP_CONFIG);
    const [result, setResult] = useState<RiskResponse | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);

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

    const handleRunRisk = async () => {
        setLoading(true);
        setError(null);

        try {
            const parsed = JSON.parse(termSheet);
            const res = await analyzeRisk(parsed, runConfig, bumpConfig);
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
                <h1 className="page-title">Risk Analysis</h1>
                <p className="page-description">Calculate Greeks with Common Random Numbers (CRN)</p>
            </div>

            {/* Controls */}
            <div className="card" style={{ marginBottom: '1.5rem' }}>
                <div className="controls-row">
                    <div className="control-group">
                        <label className="control-label">Paths</label>
                        <input
                            type="number"
                            className="control-input"
                            value={runConfig.paths}
                            onChange={e => setRunConfig({ ...runConfig, paths: parseInt(e.target.value) || 10000 })}
                        />
                    </div>
                    <div className="control-group">
                        <label className="control-label">Seed</label>
                        <input
                            type="number"
                            className="control-input"
                            value={runConfig.seed}
                            onChange={e => setRunConfig({ ...runConfig, seed: parseInt(e.target.value) || 42 })}
                        />
                    </div>
                    <div className="control-group">
                        <label className="control-label">Spot Bump</label>
                        <input
                            type="number"
                            className="control-input"
                            step="0.001"
                            value={bumpConfig.spot_bump}
                            onChange={e => setBumpConfig({ ...bumpConfig, spot_bump: parseFloat(e.target.value) || 0.01 })}
                        />
                    </div>
                    <div className="control-group">
                        <label className="control-label">Vol Bump</label>
                        <input
                            type="number"
                            className="control-input"
                            step="0.001"
                            value={bumpConfig.vol_bump}
                            onChange={e => setBumpConfig({ ...bumpConfig, vol_bump: parseFloat(e.target.value) || 0.01 })}
                        />
                    </div>
                    <div className="control-group" style={{ flexDirection: 'row', alignItems: 'center', gap: '0.5rem' }}>
                        <input
                            type="checkbox"
                            id="include-rho"
                            checked={bumpConfig.include_rho}
                            onChange={e => setBumpConfig({ ...bumpConfig, include_rho: e.target.checked })}
                        />
                        <label htmlFor="include-rho" style={{ fontSize: '0.875rem' }}>Include Rho</label>
                    </div>
                    <button className="btn btn-secondary" onClick={handleLoadExample}>
                        Load Example
                    </button>
                    <button className="btn btn-primary" onClick={handleRunRisk} disabled={loading}>
                        {loading ? '⏳ Running...' : '▶ Run Risk'}
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
                                    <div className="stat-value">{formatPercent(result.summary.autocall_probability)}</div>
                                    <div className="stat-label">Autocall Prob</div>
                                </div>
                                <div className="card">
                                    <div className="stat-value">{formatPercent(result.summary.ki_probability)}</div>
                                    <div className="stat-label">KI Probability</div>
                                </div>
                                <div className="card">
                                    <div className="stat-value">{result.summary.expected_life_years.toFixed(2)}y</div>
                                    <div className="stat-label">Expected Life</div>
                                </div>
                            </div>

                            {/* Greeks Table */}
                            <div className="card">
                                <h3 style={{ marginBottom: '1rem' }}>Greeks (CRN Central Diff)</h3>
                                <div className="table-container">
                                    <table>
                                        <thead>
                                            <tr>
                                                <th>Underlying</th>
                                                <th style={{ textAlign: 'right' }}>Delta</th>
                                                <th style={{ textAlign: 'right' }}>Delta %</th>
                                                <th style={{ textAlign: 'right' }}>Vega</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {Object.keys(result.greeks.delta).map(asset => (
                                                <tr key={asset}>
                                                    <td style={{ fontWeight: 500 }}>{asset}</td>
                                                    <td style={{ textAlign: 'right' }}>${formatNumber(result.greeks.delta[asset], 0)}</td>
                                                    <td style={{ textAlign: 'right' }}>{formatNumber(result.greeks.delta_pct[asset], 2)}%</td>
                                                    <td style={{ textAlign: 'right' }}>${formatNumber(result.greeks.vega[asset], 0)}</td>
                                                </tr>
                                            ))}
                                            {result.greeks.rho !== null && (
                                                <tr>
                                                    <td style={{ fontWeight: 500 }}>Rho (1bp)</td>
                                                    <td style={{ textAlign: 'right' }} colSpan={3}>${formatNumber(result.greeks.rho, 0)}</td>
                                                </tr>
                                            )}
                                        </tbody>
                                    </table>
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
                                                <th style={{ textAlign: 'right' }}>PV Contrib</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {result.cashflows.map((cf, i) => (
                                                <tr key={i}>
                                                    <td>{cf.date}</td>
                                                    <td>{cf.type}</td>
                                                    <td style={{ textAlign: 'right' }}>{formatPercent(cf.probability)}</td>
                                                    <td style={{ textAlign: 'right' }}>${formatNumber(cf.pv_contribution, 0)}</td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        </>
                    ) : (
                        <div className="card" style={{ textAlign: 'center', padding: '3rem' }}>
                            <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>📊</div>
                            <div style={{ color: 'var(--muted)' }}>
                                Click "Run Risk" to calculate Greeks and sensitivity analysis
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
