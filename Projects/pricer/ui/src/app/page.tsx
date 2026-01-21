'use client';

import { useState, useEffect, useMemo } from 'react';
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
    const [showJson, setShowJson] = useState(false);

    const parsedTermSheet = useMemo(() => {
        try {
            return JSON.parse(termSheet);
        } catch (err) {
            return null;
        }
    }, [termSheet]);

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

    const updateTermSheet = (updater: (draft: any) => void) => {
        if (!parsedTermSheet) {
            return;
        }
        const draft = JSON.parse(JSON.stringify(parsedTermSheet));
        updater(draft);
        setTermSheet(JSON.stringify(draft, null, 2));
    };

    const parseNumber = (value: string, fallback = 0) => {
        const parsed = Number.parseFloat(value);
        return Number.isNaN(parsed) ? fallback : parsed;
    };

    const handleMetaChange = (field: string, value: string | number) => {
        updateTermSheet(draft => {
            draft.meta = { ...draft.meta, [field]: value };
        });
    };

    const handleUnderlyingChange = (index: number, field: string, value: string | number) => {
        updateTermSheet(draft => {
            const underlyings = [...(draft.underlyings || [])];
            if (!underlyings[index]) {
                return;
            }
            underlyings[index] = { ...underlyings[index], [field]: value };
            draft.underlyings = underlyings;
        });
    };

    const handleDividendTypeChange = (index: number, value: string) => {
        updateTermSheet(draft => {
            const underlyings = [...(draft.underlyings || [])];
            if (!underlyings[index]) {
                return;
            }
            underlyings[index] = {
                ...underlyings[index],
                dividend_model: value === 'continuous'
                    ? { type: 'continuous', continuous_yield: underlyings[index].dividend_model?.continuous_yield ?? 0 }
                    : { type: 'discrete', discrete_dividends: underlyings[index].dividend_model?.discrete_dividends ?? [] }
            };
            draft.underlyings = underlyings;
        });
    };

    const handleContinuousYieldChange = (index: number, value: string) => {
        updateTermSheet(draft => {
            const underlyings = [...(draft.underlyings || [])];
            if (!underlyings[index]) {
                return;
            }
            underlyings[index] = {
                ...underlyings[index],
                dividend_model: {
                    ...(underlyings[index].dividend_model || { type: 'continuous' }),
                    type: 'continuous',
                    continuous_yield: parseNumber(value, 0)
                }
            };
            draft.underlyings = underlyings;
        });
    };

    const handleScheduleChange = (index: number, field: string, value: string | number) => {
        updateTermSheet(draft => {
            const schedules = {
                observation_dates: [],
                payment_dates: [],
                autocall_levels: [],
                coupon_barriers: [],
                coupon_rates: [],
                ...draft.schedules
            };
            const next = [...(schedules as any)[field]];
            next[index] = value;
            draft.schedules = { ...schedules, [field]: next };
        });
    };

    const handlePayoffChange = (field: string, value: string | number | boolean) => {
        updateTermSheet(draft => {
            draft.payoff = { ...draft.payoff, [field]: value };
        });
    };

    const handleKiChange = (field: string, value: string | number) => {
        updateTermSheet(draft => {
            draft.ki_barrier = { ...draft.ki_barrier, [field]: value };
        });
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
                    <RetroWindow title="Term Sheet Builder" color="cyan">
                        {!parsedTermSheet && (
                            <div className="error-box" style={{ marginBottom: '1rem' }}>
                                Invalid JSON detected. Fix the JSON to continue using the builder.
                            </div>
                        )}
                        <div className="term-sheet-section">
                            <div className="term-sheet-section-title">Product Overview</div>
                            <div className="term-sheet-grid">
                                <div className="form-group">
                                    <label className="form-label">Product ID</label>
                                    <input
                                        className="form-input"
                                        type="text"
                                        value={parsedTermSheet?.meta?.product_id ?? ''}
                                        onChange={(e) => handleMetaChange('product_id', e.target.value)}
                                        disabled={!parsedTermSheet}
                                    />
                                </div>
                                <div className="form-group">
                                    <label className="form-label">Currency</label>
                                    <input
                                        className="form-input"
                                        type="text"
                                        value={parsedTermSheet?.meta?.currency ?? ''}
                                        onChange={(e) => handleMetaChange('currency', e.target.value)}
                                        disabled={!parsedTermSheet}
                                    />
                                </div>
                                <div className="form-group">
                                    <label className="form-label">Notional</label>
                                    <input
                                        className="form-input"
                                        type="number"
                                        value={parsedTermSheet?.meta?.notional ?? ''}
                                        onChange={(e) => handleMetaChange('notional', parseNumber(e.target.value, 0))}
                                        disabled={!parsedTermSheet}
                                    />
                                </div>
                            </div>
                        </div>

                        <div className="term-sheet-section">
                            <div className="term-sheet-section-title">Key Dates</div>
                            <div className="term-sheet-grid">
                                <div className="form-group">
                                    <label className="form-label">Trade Date</label>
                                    <input
                                        className="form-input"
                                        type="date"
                                        value={parsedTermSheet?.meta?.trade_date ?? ''}
                                        onChange={(e) => handleMetaChange('trade_date', e.target.value)}
                                        disabled={!parsedTermSheet}
                                    />
                                </div>
                                <div className="form-group">
                                    <label className="form-label">Valuation Date</label>
                                    <input
                                        className="form-input"
                                        type="date"
                                        value={parsedTermSheet?.meta?.valuation_date ?? ''}
                                        onChange={(e) => handleMetaChange('valuation_date', e.target.value)}
                                        disabled={!parsedTermSheet}
                                    />
                                </div>
                                <div className="form-group">
                                    <label className="form-label">Settlement Date</label>
                                    <input
                                        className="form-input"
                                        type="date"
                                        value={parsedTermSheet?.meta?.settlement_date ?? ''}
                                        onChange={(e) => handleMetaChange('settlement_date', e.target.value)}
                                        disabled={!parsedTermSheet}
                                    />
                                </div>
                                <div className="form-group">
                                    <label className="form-label">Maturity Date</label>
                                    <input
                                        className="form-input"
                                        type="date"
                                        value={parsedTermSheet?.meta?.maturity_date ?? ''}
                                        onChange={(e) => handleMetaChange('maturity_date', e.target.value)}
                                        disabled={!parsedTermSheet}
                                    />
                                </div>
                                <div className="form-group">
                                    <label className="form-label">Payment Date</label>
                                    <input
                                        className="form-input"
                                        type="date"
                                        value={parsedTermSheet?.meta?.maturity_payment_date ?? ''}
                                        onChange={(e) => handleMetaChange('maturity_payment_date', e.target.value)}
                                        disabled={!parsedTermSheet}
                                    />
                                </div>
                            </div>
                        </div>

                        <div className="term-sheet-section">
                            <div className="term-sheet-section-title">Underlyings</div>
                            <div className="term-sheet-underlyings">
                                {(parsedTermSheet?.underlyings || []).map((underlying: any, index: number) => (
                                    <div className="term-sheet-card" key={`${underlying.id}-${index}`}>
                                        <div className="term-sheet-card-title">
                                            <span>{underlying.id || `Underlying ${index + 1}`}</span>
                                            <span className="pill">{underlying.vol_model?.type ?? 'model'}</span>
                                        </div>
                                        <div className="term-sheet-grid">
                                            <div className="form-group">
                                                <label className="form-label">Ticker</label>
                                                <input
                                                    className="form-input"
                                                    type="text"
                                                    value={underlying.id ?? ''}
                                                    onChange={(e) => handleUnderlyingChange(index, 'id', e.target.value)}
                                                    disabled={!parsedTermSheet}
                                                />
                                            </div>
                                            <div className="form-group">
                                                <label className="form-label">Spot</label>
                                                <input
                                                    className="form-input"
                                                    type="number"
                                                    value={underlying.spot ?? ''}
                                                    onChange={(e) => handleUnderlyingChange(index, 'spot', parseNumber(e.target.value, 0))}
                                                    disabled={!parsedTermSheet}
                                                />
                                            </div>
                                            <div className="form-group">
                                                <label className="form-label">Dividend Type</label>
                                                <select
                                                    className="form-input"
                                                    value={underlying.dividend_model?.type ?? 'continuous'}
                                                    onChange={(e) => handleDividendTypeChange(index, e.target.value)}
                                                    disabled={!parsedTermSheet}
                                                >
                                                    <option value="continuous">Continuous</option>
                                                    <option value="discrete">Discrete</option>
                                                </select>
                                            </div>
                                            {underlying.dividend_model?.type === 'continuous' ? (
                                                <div className="form-group">
                                                    <label className="form-label">Dividend Yield</label>
                                                    <input
                                                        className="form-input"
                                                        type="number"
                                                        step="0.0001"
                                                        value={underlying.dividend_model?.continuous_yield ?? 0}
                                                        onChange={(e) => handleContinuousYieldChange(index, e.target.value)}
                                                        disabled={!parsedTermSheet}
                                                    />
                                                </div>
                                            ) : (
                                                <div className="form-group">
                                                    <label className="form-label">Discrete Dividends</label>
                                                    <input
                                                        className="form-input"
                                                        type="text"
                                                        value={`${underlying.dividend_model?.discrete_dividends?.length ?? 0} entries`}
                                                        disabled
                                                    />
                                                </div>
                                            )}
                                            <div className="form-group">
                                                <label className="form-label">Vol Params</label>
                                                <input
                                                    className="form-input"
                                                    type="text"
                                                    value={underlying.vol_model?.type === 'local_stochastic'
                                                        ? `v0 ${underlying.vol_model?.lsv_params?.v0 ?? '-'} | xi ${underlying.vol_model?.lsv_params?.xi ?? '-'}`
                                                        : underlying.vol_model?.type ?? 'N/A'}
                                                    disabled
                                                />
                                            </div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>

                        <div className="term-sheet-section">
                            <div className="term-sheet-section-title">Schedule & Coupons</div>
                            <div className="table-container term-sheet-table">
                                <table>
                                    <thead>
                                        <tr>
                                            <th>Obs Date</th>
                                            <th>Pay Date</th>
                                            <th>Autocall</th>
                                            <th>Coupon Barrier</th>
                                            <th>Coupon Rate</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {(parsedTermSheet?.schedules?.observation_dates || []).map((date: string, index: number) => (
                                            <tr key={`schedule-${index}`}>
                                                <td>
                                                    <input
                                                        className="table-input"
                                                        type="date"
                                                        value={date}
                                                        onChange={(e) => handleScheduleChange(index, 'observation_dates', e.target.value)}
                                                        disabled={!parsedTermSheet}
                                                    />
                                                </td>
                                                <td>
                                                    <input
                                                        className="table-input"
                                                        type="date"
                                                        value={parsedTermSheet?.schedules?.payment_dates?.[index] ?? ''}
                                                        onChange={(e) => handleScheduleChange(index, 'payment_dates', e.target.value)}
                                                        disabled={!parsedTermSheet}
                                                    />
                                                </td>
                                                <td>
                                                    <input
                                                        className="table-input"
                                                        type="number"
                                                        step="0.01"
                                                        value={parsedTermSheet?.schedules?.autocall_levels?.[index] ?? 0}
                                                        onChange={(e) => handleScheduleChange(index, 'autocall_levels', parseNumber(e.target.value, 0))}
                                                        disabled={!parsedTermSheet}
                                                    />
                                                </td>
                                                <td>
                                                    <input
                                                        className="table-input"
                                                        type="number"
                                                        step="0.01"
                                                        value={parsedTermSheet?.schedules?.coupon_barriers?.[index] ?? 0}
                                                        onChange={(e) => handleScheduleChange(index, 'coupon_barriers', parseNumber(e.target.value, 0))}
                                                        disabled={!parsedTermSheet}
                                                    />
                                                </td>
                                                <td>
                                                    <input
                                                        className="table-input"
                                                        type="number"
                                                        step="0.01"
                                                        value={parsedTermSheet?.schedules?.coupon_rates?.[index] ?? 0}
                                                        onChange={(e) => handleScheduleChange(index, 'coupon_rates', parseNumber(e.target.value, 0))}
                                                        disabled={!parsedTermSheet}
                                                    />
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>

                        <div className="term-sheet-section">
                            <div className="term-sheet-section-title">Protection & Redemption</div>
                            <div className="term-sheet-grid">
                                <div className="form-group">
                                    <label className="form-label">KI Barrier</label>
                                    <input
                                        className="form-input"
                                        type="number"
                                        step="0.01"
                                        value={parsedTermSheet?.ki_barrier?.level ?? 0}
                                        onChange={(e) => handleKiChange('level', parseNumber(e.target.value, 0))}
                                        disabled={!parsedTermSheet}
                                    />
                                </div>
                                <div className="form-group">
                                    <label className="form-label">KI Monitoring</label>
                                    <select
                                        className="form-input"
                                        value={parsedTermSheet?.ki_barrier?.monitoring ?? 'continuous'}
                                        onChange={(e) => handleKiChange('monitoring', e.target.value)}
                                        disabled={!parsedTermSheet}
                                    >
                                        <option value="continuous">Continuous</option>
                                        <option value="discrete">Discrete</option>
                                    </select>
                                </div>
                                <div className="form-group">
                                    <label className="form-label">Worst Of</label>
                                    <select
                                        className="form-input"
                                        value={(parsedTermSheet?.payoff?.worst_of ?? false).toString()}
                                        onChange={(e) => handlePayoffChange('worst_of', e.target.value === 'true')}
                                        disabled={!parsedTermSheet}
                                    >
                                        <option value="true">Yes</option>
                                        <option value="false">No</option>
                                    </select>
                                </div>
                                <div className="form-group">
                                    <label className="form-label">Coupon Memory</label>
                                    <select
                                        className="form-input"
                                        value={(parsedTermSheet?.payoff?.coupon_memory ?? false).toString()}
                                        onChange={(e) => handlePayoffChange('coupon_memory', e.target.value === 'true')}
                                        disabled={!parsedTermSheet}
                                    >
                                        <option value="true">Yes</option>
                                        <option value="false">No</option>
                                    </select>
                                </div>
                                <div className="form-group">
                                    <label className="form-label">Settlement</label>
                                    <select
                                        className="form-input"
                                        value={parsedTermSheet?.payoff?.settlement ?? 'cash'}
                                        onChange={(e) => handlePayoffChange('settlement', e.target.value)}
                                        disabled={!parsedTermSheet}
                                    >
                                        <option value="cash">Cash</option>
                                        <option value="physical">Physical</option>
                                    </select>
                                </div>
                                <div className="form-group">
                                    <label className="form-label">Autocall Redemption</label>
                                    <input
                                        className="form-input"
                                        type="number"
                                        step="0.01"
                                        value={parsedTermSheet?.payoff?.redemption_if_autocall ?? 0}
                                        onChange={(e) => handlePayoffChange('redemption_if_autocall', parseNumber(e.target.value, 0))}
                                        disabled={!parsedTermSheet}
                                    />
                                </div>
                                <div className="form-group">
                                    <label className="form-label">No KI Redemption</label>
                                    <input
                                        className="form-input"
                                        type="number"
                                        step="0.01"
                                        value={parsedTermSheet?.payoff?.redemption_if_no_ki ?? 0}
                                        onChange={(e) => handlePayoffChange('redemption_if_no_ki', parseNumber(e.target.value, 0))}
                                        disabled={!parsedTermSheet}
                                    />
                                </div>
                                <div className="form-group">
                                    <label className="form-label">KI Redemption</label>
                                    <select
                                        className="form-input"
                                        value={parsedTermSheet?.payoff?.redemption_if_ki ?? 'worst_performance'}
                                        onChange={(e) => handlePayoffChange('redemption_if_ki', e.target.value)}
                                        disabled={!parsedTermSheet}
                                    >
                                        <option value="worst_performance">Worst Performance</option>
                                        <option value="par">Par</option>
                                        <option value="performance">Performance</option>
                                    </select>
                                </div>
                                <div className="form-group">
                                    <label className="form-label">KI Redemption Floor</label>
                                    <input
                                        className="form-input"
                                        type="number"
                                        step="0.01"
                                        value={parsedTermSheet?.payoff?.ki_redemption_floor ?? 0}
                                        onChange={(e) => handlePayoffChange('ki_redemption_floor', parseNumber(e.target.value, 0))}
                                        disabled={!parsedTermSheet}
                                    />
                                </div>
                            </div>
                        </div>

                        <div className="term-sheet-section">
                            <div className="term-sheet-section-title">Market Data</div>
                            <div className="term-sheet-grid">
                                <div className="form-group">
                                    <label className="form-label">Discount Curve</label>
                                    <input
                                        className="form-input"
                                        type="number"
                                        step="0.0001"
                                        value={parsedTermSheet?.discount_curve?.flat_rate ?? 0}
                                        onChange={(e) => updateTermSheet(draft => {
                                            draft.discount_curve = {
                                                ...draft.discount_curve,
                                                flat_rate: parseNumber(e.target.value, 0)
                                            };
                                        })}
                                        disabled={!parsedTermSheet}
                                    />
                                </div>
                                <div className="form-group">
                                    <label className="form-label">Correlation Pairs</label>
                                    <input
                                        className="form-input"
                                        type="text"
                                        value={`${Object.keys(parsedTermSheet?.correlation?.pairwise ?? {}).length} pairs`}
                                        disabled
                                    />
                                </div>
                            </div>
                        </div>

                        <div className="term-sheet-actions">
                            <button className="btn btn-secondary" onClick={() => setShowJson(!showJson)}>
                                {showJson ? 'Hide JSON' : 'Advanced JSON'}
                            </button>
                        </div>

                        {showJson && (
                            <div className="editor-container" style={{ marginTop: '0.75rem' }}>
                                <MonacoEditor
                                    height="320px"
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
                        )}
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
