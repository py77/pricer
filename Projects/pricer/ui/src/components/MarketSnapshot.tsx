'use client';

import { Tooltip } from './ui/Tooltip';

interface UnderlyingData {
    id: string;
    spot: number;
    currency: string;
    vol_model?: {
        type: string;
        flat_vol?: number;
        lsv_params?: { v0: number };
        term_structure?: Array<{ vol: number }>;
    };
}

interface MarketSnapshotProps {
    underlyings: UnderlyingData[];
    correlations?: Record<string, number>;
    asOfDate?: string;
}

export function MarketSnapshot({ underlyings, correlations, asOfDate }: MarketSnapshotProps) {
    const formatNumber = (num: number, decimals: number = 2) => {
        return num.toLocaleString('en-US', {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals,
        });
    };

    const formatPercent = (num: number) => {
        return `${(num * 100).toFixed(1)}%`;
    };

    const getVol = (underlying: UnderlyingData): number => {
        if (underlying.vol_model?.type === 'local_stochastic' && underlying.vol_model?.lsv_params?.v0) {
            return Math.sqrt(underlying.vol_model.lsv_params.v0);
        } else if (underlying.vol_model?.type === 'flat' && underlying.vol_model?.flat_vol) {
            return underlying.vol_model.flat_vol;
        } else if (underlying.vol_model?.term_structure?.length) {
            return underlying.vol_model.term_structure[0]?.vol || 0;
        }
        return 0;
    };

    if (!underlyings || underlyings.length === 0) {
        return (
            <div className="market-snapshot-empty">
                <div className="empty-icon">📊</div>
                <div className="empty-title">No Market Data</div>
                <div className="empty-description">
                    Load a term sheet to display live underlying prices
                </div>
            </div>
        );
    }

    return (
        <div className="market-snapshot">
            {/* Table */}
            <div className="market-snapshot-table">
                <div className="market-snapshot-header">
                    <div className="market-snapshot-cell">Ticker</div>
                    <div className="market-snapshot-cell align-right">Spot</div>
                    <div className="market-snapshot-cell align-right">
                        <Tooltip content="Annualized volatility used in pricing">
                            <span>Vol</span>
                        </Tooltip>
                    </div>
                    <div className="market-snapshot-cell">Currency</div>
                </div>
                {underlyings.map((underlying, index) => {
                    const vol = getVol(underlying);
                    return (
                        <div key={`${underlying.id}-${index}`} className="market-snapshot-row">
                            <div className="market-snapshot-cell ticker-cell">
                                {underlying.id}
                            </div>
                            <div className="market-snapshot-cell align-right spot-cell">
                                ${formatNumber(underlying.spot, 2)}
                            </div>
                            <div className="market-snapshot-cell align-right vol-cell">
                                {formatPercent(vol)}
                            </div>
                            <div className="market-snapshot-cell currency-cell">
                                {underlying.currency}
                            </div>
                        </div>
                    );
                })}
            </div>

            {/* Correlations */}
            {correlations && Object.keys(correlations).length > 0 && (
                <div className="market-snapshot-correlations">
                    <div className="correlations-title">
                        <Tooltip content="Pairwise correlation coefficients between underlyings">
                            <span>Correlations</span>
                        </Tooltip>
                    </div>
                    <div className="correlations-grid">
                        {Object.entries(correlations).map(([pair, corr]) => (
                            <div key={pair} className="correlation-chip">
                                <span className="correlation-pair">{pair.replace('_', '/')}</span>
                                <span className="correlation-value">{formatNumber(corr, 2)}</span>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
