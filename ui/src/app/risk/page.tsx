'use client';

import { useState, useEffect, useMemo } from 'react';
import dynamic from 'next/dynamic';
import { analyzeRisk, getExampleSchema, RiskResponse, RunConfig, BumpConfig } from '@/api/client';
import { Badge, Frame, GraveCard, MetricChip, RatingBars } from '@/components/ui';

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

    const parsedTermSheet = useMemo(() => {
        try {
            return JSON.parse(termSheet);
        } catch (err) {
            return null;
        }
    }, [termSheet]);

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
                <div className="page-title-row">
                    <div>
                        <h1 className="page-title">Risk Analysis</h1>
                        <p className="page-description">Calculate Greeks with CRN Monte Carlo</p>
                    </div>
                    <a className="btn" href="/">Pricing</a>
                </div>
            </div>

            {/* Controls */}
            <Frame title="Controls" subtitle="Run settings">
                <div className="controls-row">
                    <div className="control-group">
                        <label className="control-label" htmlFor="risk-paths">Paths</label>
                        <input
                            id="risk-paths"
                            type="number"
                            className="control-input"
                            value={runConfig.paths}
                            onChange={e => setRunConfig({ ...runConfig, paths: parseInt(e.target.value) || 10000 })}
                        />
                    </div>
                    <div className="control-group">
                        <label className="control-label" htmlFor="risk-seed">Seed</label>
                        <input
                            id="risk-seed"
                            type="number"
                            className="control-input"
                            value={runConfig.seed}
                            onChange={e => setRunConfig({ ...runConfig, seed: parseInt(e.target.value) || 42 })}
                        />
                    </div>
                    <div className="control-group">
                        <label className="control-label" htmlFor="risk-block">Block Size</label>
                        <input
                            id="risk-block"
                            type="number"
                            className="control-input"
                            value={runConfig.block_size}
                            onChange={e => setRunConfig({ ...runConfig, block_size: parseInt(e.target.value) || 50000 })}
                        />
                    </div>
                    <div className="control-group">
                        <label className="control-label" htmlFor="risk-spot">Spot Bump</label>
                        <input
                            id="risk-spot"
                            type="number"
                            className="control-input"
                            step="0.001"
                            value={bumpConfig.spot_bump}
                            onChange={e => setBumpConfig({ ...bumpConfig, spot_bump: parseFloat(e.target.value) || 0.01 })}
                        />
                    </div>
                    <div className="control-group">
                        <label className="control-label" htmlFor="risk-vol">Vol Bump</label>
                        <input
                            id="risk-vol"
                            type="number"
                            className="control-input"
                            step="0.001"
                            value={bumpConfig.vol_bump}
                            onChange={e => setBumpConfig({ ...bumpConfig, vol_bump: parseFloat(e.target.value) || 0.01 })}
                        />
                    </div>
                    <div className="checkbox-row">
                        <input
                            type="checkbox"
                            id="include-rho"
                            checked={bumpConfig.include_rho}
                            onChange={e => setBumpConfig({ ...bumpConfig, include_rho: e.target.checked })}
                        />
                        <label htmlFor="include-rho">Include Rho</label>
                    </div>
                    <button className="btn" onClick={handleLoadExample}>
                        Load Example
                    </button>
                    <button className="btn btn-primary" onClick={handleRunRisk} disabled={loading}>
                        {loading ? 'Running...' : 'Run Risk'}
                    </button>
                </div>
            </Frame>

            {error && <div className="error-box" style={{ marginBottom: '1.5rem' }}>{error}</div>}

            <div className="editor-layout">
                {/* Editor Panel */}
                <div className="editor-panel">
                    <Frame title="Term Sheet (JSON)" subtitle="Paste or edit">
                        {!parsedTermSheet && (
                            <div className="error-box" style={{ marginBottom: '1rem' }}>
                                Invalid JSON detected. Fix the JSON to run risk analysis.
                            </div>
                        )}
                        <div className="editor-container">
                            <MonacoEditor
                                height="100%"
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
                    </Frame>
                </div>

                {/* Results Panel */}
                <div className="results-panel">
                    {result ? (
                        <>
                            {/* Summary Cards */}
                            <Frame title="Summary" subtitle="Risk overview">
                                <GraveCard>
                                    <div className="card-header">
                                        <div className="card-title">Risk metrics</div>
                                        <Badge>Priced</Badge>
                                    </div>
                                    <div className="metric-grid">
                                        <MetricChip label="Price" value={`$${formatNumber(result.summary.pv, 0)}`} />
                                        <MetricChip label="Autocall Prob" value={formatPercent(result.summary.autocall_probability)} />
                                        <MetricChip label="KI Probability" value={formatPercent(result.summary.ki_probability)} />
                                        <MetricChip label="Expected Life" value={`${result.summary.expected_life_years.toFixed(2)}y`} />
                                    </div>
                                    <div className="results-meta">
                                        <span>Risk posture</span>
                                        <RatingBars value={result.summary.ki_probability * 5} color="orange" label="Risk rating" />
                                    </div>
                                </GraveCard>
                            </Frame>

                            {/* Greeks Table */}
                            <Frame title="Greeks (CRN Central Diff)" subtitle="Sensitivity table">
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
                            </Frame>

                            {/* Decomposition */}
                            <Frame title="PV Decomposition" subtitle="Component breakdown">
                                <div className="metric-grid">
                                    <MetricChip label="Coupon PV" value={`$${formatNumber(result.decomposition.coupon_pv, 0)}`} />
                                    <MetricChip
                                        label="Autocall Redemption"
                                        value={`$${formatNumber(result.decomposition.autocall_redemption_pv, 0)}`}
                                    />
                                    <MetricChip
                                        label="Maturity Redemption"
                                        value={`$${formatNumber(result.decomposition.maturity_redemption_pv, 0)}`}
                                    />
                                </div>
                            </Frame>

                            {/* Cashflows Table */}
                            <Frame title="Expected Cashflows" subtitle="Projected payoffs">
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
                            </Frame>

                            <Frame title="Statistics" subtitle="Simulation health">
                                <div className="results-meta">
                                    <span>Paths: {result.summary.num_paths.toLocaleString()}</span>
                                    <span>Std Error: ${formatNumber(result.summary.pv_std_error)}</span>
                                    <span>Time: {result.summary.computation_time_ms.toFixed(0)}ms</span>
                                </div>
                            </Frame>
                        </>
                    ) : (
                        <Frame title="Results" subtitle="Awaiting risk run">
                            <GraveCard>
                                <div className="card-header">
                                    <div className="card-title">No results yet</div>
                                    <Badge>Waiting</Badge>
                                </div>
                                <p className="card-description">
                                    Click run risk to calculate Greeks and sensitivity analysis.
                                </p>
                                <div className="card-footer">Hover for details</div>
                            </GraveCard>
                        </Frame>
                    )}
                </div>
            </div>
        </div>
    );
}
