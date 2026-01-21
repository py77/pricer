'use client';

import { useState, useEffect, useMemo, useRef } from 'react';
import dynamic from 'next/dynamic';
import { priceProduct, getExampleSchema, fetchMarketData, PriceResponse, RunConfig } from '@/api/client';
import { Badge, Frame, GraveCard, MetricChip, PillButton, RatingBars, SearchBar } from '@/components/ui';

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

type InstrumentCard = {
    id: string;
    title: string;
    year: string;
    description: string;
    category: string;
    metric: string;
    badge: string;
    ratings: {
        rebuild: number;
        scale: number;
        market: number;
    };
};

type ProtectionInputId =
    | 'ki_level'
    | 'ki_monitoring'
    | 'worst_of'
    | 'coupon_memory'
    | 'settlement'
    | 'autocall_redemption'
    | 'no_ki_redemption'
    | 'ki_redemption'
    | 'ki_redemption_floor';

const PROTECTION_INPUTS_BY_INSTRUMENT: Record<string, ProtectionInputId[]> = {
    autocallable: [
        'ki_level',
        'ki_monitoring',
        'worst_of',
        'coupon_memory',
        'settlement',
        'autocall_redemption',
        'no_ki_redemption',
        'ki_redemption',
        'ki_redemption_floor',
    ],
    'reverse-convertible': [
        'ki_level',
        'ki_monitoring',
        'worst_of',
        'settlement',
        'no_ki_redemption',
        'ki_redemption',
        'ki_redemption_floor',
    ],
};

const CATEGORY_PILLS = [
    'All',
    'Autocallable',
    'Reverse Convertible',
];

const INSTRUMENTS: InstrumentCard[] = [
    {
        id: 'autocallable',
        title: 'Autocallable',
        year: '2024',
        description: 'Barrier autocallable with quarterly observations and memory coupons.',
        category: 'Autocallable',
        metric: 'CALLABLE',
        badge: 'STRUCTURED',
        ratings: { rebuild: 4, scale: 3, market: 5 },
    },
    {
        id: 'reverse-convertible',
        title: 'Reverse Convertible',
        year: '2024',
        description: 'Short put profile with enhanced coupon and physical settlement risk.',
        category: 'Reverse Convertible',
        metric: 'BUFFERED',
        badge: 'EQUITY',
        ratings: { rebuild: 2, scale: 3, market: 4 },
    },
];

const NASDAQ_TICKERS = [
    'AAPL',
    'ABNB',
    'ADBE',
    'ADI',
    'ADP',
    'ADSK',
    'AMAT',
    'AMD',
    'AMGN',
    'AMZN',
    'ASML',
    'AVGO',
    'BIDU',
    'BKNG',
    'CDNS',
    'CHTR',
    'CMCSA',
    'COST',
    'CRWD',
    'CSCO',
    'CSX',
    'CTAS',
    'CTSH',
    'DDOG',
    'DLTR',
    'DOCU',
    'EA',
    'EXC',
    'FAST',
    'FTNT',
    'GILD',
    'GOOG',
    'GOOGL',
    'HON',
    'IDXX',
    'ILMN',
    'INTC',
    'INTU',
    'ISRG',
    'JD',
    'KDP',
    'KHC',
    'KLAC',
    'LRCX',
    'LULU',
    'MAR',
    'MCHP',
    'MDLZ',
    'MELI',
    'META',
    'MNST',
    'MRNA',
    'MRVL',
    'MSFT',
    'MU',
    'NFLX',
    'NTES',
    'NVDA',
    'NXPI',
    'ORLY',
    'PANW',
    'PAYX',
    'PCAR',
    'PDD',
    'PEP',
    'PYPL',
    'QCOM',
    'REGN',
    'ROST',
    'SBUX',
    'SIRI',
    'SNPS',
    'TEAM',
    'TMUS',
    'TSLA',
    'TXN',
    'VRSK',
    'VRTX',
    'WBD',
    'WDAY',
    'XEL',
    'ZM',
    'ZS',
];

const getTickerOptions = (currentId?: string) => {
    if (currentId && !NASDAQ_TICKERS.includes(currentId)) {
        return [currentId, ...NASDAQ_TICKERS];
    }
    return NASDAQ_TICKERS;
};

export default function PricingPage() {
    const [termSheet, setTermSheet] = useState<string>('{}');
    const [config, setConfig] = useState<RunConfig>(DEFAULT_CONFIG);
    const [result, setResult] = useState<PriceResponse | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const [fetchingData, setFetchingData] = useState(false);
    const [showJson, setShowJson] = useState(false);
    const [searchTerm, setSearchTerm] = useState('');
    const [activeCategory, setActiveCategory] = useState('All');
    const [selectedInstrumentId, setSelectedInstrumentId] = useState('autocallable');
    const pricerRef = useRef<HTMLDivElement>(null);

    const parsedTermSheet = useMemo(() => {
        try {
            return JSON.parse(termSheet);
        } catch (err) {
            return null;
        }
    }, [termSheet]);

    const filteredInstruments = useMemo(() => {
        const normalizedSearch = searchTerm.trim().toLowerCase();
        return INSTRUMENTS.filter((instrument) => {
            const matchesCategory = activeCategory === 'All' || instrument.category === activeCategory;
            if (!matchesCategory) {
                return false;
            }
            if (!normalizedSearch) {
                return true;
            }
            return (
                instrument.title.toLowerCase().includes(normalizedSearch) ||
                instrument.description.toLowerCase().includes(normalizedSearch)
            );
        });
    }, [activeCategory, searchTerm]);

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

    const buildUnderlyingTemplate = (draft: any, reference?: any) => {
        const base = reference ? JSON.parse(JSON.stringify(reference)) : {};
        const currency = draft?.meta?.currency ?? 'USD';
        return {
            id: '',
            spot: base.spot ?? 0,
            currency: base.currency ?? currency,
            dividend_model: base.dividend_model
                ? {
                    ...base.dividend_model,
                    continuous_yield: base.dividend_model?.continuous_yield ?? 0,
                    discrete_dividends: base.dividend_model?.discrete_dividends ?? [],
                }
                : { type: 'continuous', continuous_yield: 0 },
            vol_model: base.vol_model ?? {
                type: 'local_stochastic',
                lsv_params: {
                    v0: 0.1,
                    theta: 0.1,
                    kappa: 2,
                    xi: 0.3,
                    rho: -0.7,
                },
            },
        };
    };

    const pruneCorrelationPairs = (draft: any, validIds: string[]) => {
        if (!draft.correlation?.pairwise) {
            return;
        }
        const validSet = new Set(validIds.filter(Boolean));
        const nextPairs = Object.fromEntries(
            Object.entries(draft.correlation.pairwise).filter(([pair]) => {
                const [left, right] = pair.split('_');
                return validSet.has(left) && validSet.has(right);
            })
        );
        draft.correlation = { ...draft.correlation, pairwise: nextPairs };
    };

    const handleMetaChange = (field: string, value: string | number) => {
        updateTermSheet(draft => {
            draft.meta = { ...draft.meta, [field]: value };
        });
    };

    const handleUnderlyingCountChange = (value: string) => {
        const desiredCount = Math.max(1, Math.floor(parseNumber(value, 1)));
        updateTermSheet(draft => {
            const underlyings = [...(draft.underlyings || [])];
            if (underlyings.length > desiredCount) {
                underlyings.splice(desiredCount);
            } else if (underlyings.length < desiredCount) {
                const reference = underlyings[underlyings.length - 1] ?? underlyings[0];
                for (let i = underlyings.length; i < desiredCount; i += 1) {
                    underlyings.push(buildUnderlyingTemplate(draft, reference));
                }
            }
            draft.underlyings = underlyings;
            pruneCorrelationPairs(draft, underlyings.map((item: any) => item.id));
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

    const handleSelectInstrument = (instrumentId: string) => {
        setSelectedInstrumentId(instrumentId);
        requestAnimationFrame(() => {
            pricerRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        });
    };

    const selectedInstrument = INSTRUMENTS.find((instrument) => instrument.id === selectedInstrumentId);
    const protectionInputs = PROTECTION_INPUTS_BY_INSTRUMENT[selectedInstrumentId]
        ?? PROTECTION_INPUTS_BY_INSTRUMENT.autocallable;

    return (
        <div>
            <div className="page-header">
                <div className="page-title-row">
                    <div>
                        <h1 className="page-title">Structured Products Pricer</h1>
                        <p className="page-description">Price structured products with high-contrast templates</p>
                    </div>
                    <a className="btn" href="/risk">Risk</a>
                </div>
                <SearchBar
                    value={searchTerm}
                    onChange={setSearchTerm}
                    placeholder="SEARCH INSTRUMENTS..."
                />
                <div className="pill-row" role="tablist" aria-label="Instrument categories">
                    {CATEGORY_PILLS.map((pill) => (
                        <PillButton
                            key={pill}
                            active={activeCategory === pill}
                            onClick={() => setActiveCategory(pill)}
                            role="tab"
                            aria-selected={activeCategory === pill}
                        >
                            {pill}
                        </PillButton>
                    ))}
                </div>
            </div>

            <Frame
                title="Instrument templates"
                subtitle={`${filteredInstruments.length} templates available`}
            >
                <div className="card-grid">
                    {filteredInstruments.map((instrument) => (
                        <GraveCard
                            key={instrument.id}
                            as="button"
                            className={selectedInstrumentId === instrument.id ? 'grave-card--active' : ''}
                            onClick={() => handleSelectInstrument(instrument.id)}
                            aria-label={`Open ${instrument.title} pricer`}
                        >
                            <div className="card-header">
                                <div className="card-title">{instrument.title}</div>
                                <div className="card-year">{instrument.year}</div>
                            </div>
                            <p className="card-description">{instrument.description}</p>
                            <div className="card-row">
                                <MetricChip label="Metric" value={instrument.metric} />
                                <Badge>{instrument.badge}</Badge>
                            </div>
                            <div className="card-footer">Hover for details</div>
                            <div className="card-ratings">
                                <div className="rating-group">
                                    <span className="rating-label">
                                        <span className="rating-icon" aria-hidden />
                                        Rebuild
                                    </span>
                                    <RatingBars value={instrument.ratings.rebuild} color="orange" label="Rebuild rating" />
                                </div>
                                <div className="rating-group">
                                    <span className="rating-label">
                                        <span className="rating-icon" aria-hidden />
                                        Scale
                                    </span>
                                    <RatingBars value={instrument.ratings.scale} color="blue" label="Scale rating" />
                                </div>
                                <div className="rating-group">
                                    <span className="rating-label">
                                        <span className="rating-icon" aria-hidden />
                                        Market
                                    </span>
                                    <RatingBars value={instrument.ratings.market} color="orange" label="Market rating" />
                                </div>
                            </div>
                        </GraveCard>
                    ))}
                </div>
            </Frame>

            <div ref={pricerRef} />

            <Frame
                title={`Pricer workspace · ${selectedInstrument?.title ?? 'Instrument'}`}
                subtitle="Configure inputs and run pricing"
            >
                <div className="controls-row">
                    <div className="control-group">
                        <label className="control-label" htmlFor="paths-input">Paths</label>
                        <input
                            id="paths-input"
                            type="number"
                            className="control-input"
                            value={config.paths}
                            onChange={e => setConfig({ ...config, paths: parseInt(e.target.value) || 10000 })}
                        />
                    </div>
                    <div className="control-group">
                        <label className="control-label" htmlFor="seed-input">Seed</label>
                        <input
                            id="seed-input"
                            type="number"
                            className="control-input"
                            value={config.seed}
                            onChange={e => setConfig({ ...config, seed: parseInt(e.target.value) || 42 })}
                        />
                    </div>
                    <div className="control-group">
                        <label className="control-label" htmlFor="block-input">Block Size</label>
                        <input
                            id="block-input"
                            type="number"
                            className="control-input"
                            value={config.block_size}
                            onChange={e => setConfig({ ...config, block_size: parseInt(e.target.value) || 50000 })}
                        />
                    </div>
                    <button className="btn" onClick={handleLoadExample}>
                        Load Example
                    </button>
                    <button className="btn" onClick={handleFetchLiveData} disabled={fetchingData}>
                        {fetchingData ? 'Fetching...' : 'Fetch Live Data'}
                    </button>
                    <button className="btn btn-primary" onClick={handleRunPricing} disabled={loading}>
                        {loading ? 'Running...' : 'Run Pricing'}
                    </button>
                </div>
            </Frame>

            {error && <div className="error-box" style={{ marginBottom: '1rem' }}>{error}</div>}

            <div className="editor-layout">
                <div className="editor-panel">
                    <Frame title="Term Sheet Builder" subtitle="Autocallable configuration">
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
                            <div className="term-sheet-underlyings-header">
                                <div className="form-group">
                                    <label className="form-label">Number of underlyings</label>
                                    <input
                                        className="form-input"
                                        type="number"
                                        min={1}
                                        value={(parsedTermSheet?.underlyings || []).length || 1}
                                        onChange={(e) => handleUnderlyingCountChange(e.target.value)}
                                        disabled={!parsedTermSheet}
                                    />
                                </div>
                            </div>
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
                                                <select
                                                    className={`form-input ${underlying.id ? '' : 'form-select-scroll'}`}
                                                    value={underlying.id ?? ''}
                                                    onChange={(e) => handleUnderlyingChange(index, 'id', e.target.value)}
                                                    disabled={!parsedTermSheet}
                                                    size={underlying.id ? 1 : 6}
                                                >
                                                    <option value="">Select ticker</option>
                                                    {getTickerOptions(underlying.id).map((ticker) => (
                                                        <option key={`${ticker}-${index}`} value={ticker}>
                                                            {ticker}
                                                        </option>
                                                    ))}
                                                </select>
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
                                {protectionInputs.includes('ki_level') && (
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
                                )}
                                {protectionInputs.includes('ki_monitoring') && (
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
                                )}
                                {protectionInputs.includes('worst_of') && (
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
                                )}
                                {protectionInputs.includes('coupon_memory') && (
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
                                )}
                                {protectionInputs.includes('settlement') && (
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
                                )}
                                {protectionInputs.includes('autocall_redemption') && (
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
                                )}
                                {protectionInputs.includes('no_ki_redemption') && (
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
                                )}
                                {protectionInputs.includes('ki_redemption') && (
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
                                )}
                                {protectionInputs.includes('ki_redemption_floor') && (
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
                                )}
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
                    </Frame>
                </div>

                {/* Results Panel */}
                <div className="results-panel">
                    {result ? (
                        <>
                            {/* Summary Cards */}
                            <Frame title="Summary" subtitle="Key pricing metrics">
                                <GraveCard>
                                    <div className="card-header">
                                        <div className="card-title">Pricing output</div>
                                        <Badge>Priced</Badge>
                                    </div>
                                    <div className="metric-grid">
                                        <MetricChip label="Price" value={`$${formatNumber(result.summary.pv, 0)}`} />
                                        <MetricChip label="PV % Notional" value={formatPercent(result.summary.pv_pct_notional)} />
                                        <MetricChip label="Autocall Prob" value={formatPercent(result.summary.autocall_probability)} />
                                        <MetricChip label="KI Probability" value={formatPercent(result.summary.ki_probability)} />
                                        <MetricChip label="Expected Coupons" value={result.summary.expected_coupon_count.toFixed(2)} />
                                        <MetricChip label="Expected Life" value={`${result.summary.expected_life_years.toFixed(2)}y`} />
                                    </div>
                                    <div className="results-meta">
                                        <span>Risk posture</span>
                                        <RatingBars
                                            value={result.summary.ki_probability * 5}
                                            color="orange"
                                            label="Risk rating"
                                        />
                                    </div>
                                </GraveCard>
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

                            {/* Stats */}
                            <Frame title="Statistics" subtitle="Simulation health">
                                <div className="results-meta">
                                    <span>Paths: {result.summary.num_paths.toLocaleString()}</span>
                                    <span>Std Error: ${formatNumber(result.summary.pv_std_error)}</span>
                                    <span>Time: {result.summary.computation_time_ms.toFixed(0)}ms</span>
                                </div>
                            </Frame>
                        </>
                    ) : (
                        <Frame title="Results" subtitle="Awaiting pricing run">
                            <GraveCard>
                                <div className="card-header">
                                    <div className="card-title">No results yet</div>
                                    <Badge>Waiting</Badge>
                                </div>
                                <p className="card-description">
                                    Click run pricing to calculate PV, risk metrics, and cashflow projections.
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
