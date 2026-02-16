"""
Market data fetcher using Yahoo Finance.

Provides functions to fetch:
- Spot prices
- Historical volatility
- Dividends
- Correlations
- Risk-free rates
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple
import numpy as np

try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False


@dataclass
class DividendInfo:
    """Dividend information for a stock."""
    ex_date: date
    amount: float


@dataclass
class VolInfo:
    """Volatility term structure entry."""
    date: date
    vol: float


@dataclass
class UnderlyingMarketData:
    """Market data for a single underlying."""
    ticker: str
    spot: float
    currency: str = "USD"
    historical_vol: float = 0.25
    vol_term_structure: List[VolInfo] = field(default_factory=list)
    dividends: List[DividendInfo] = field(default_factory=list)
    dividend_yield: float = 0.0


@dataclass
class MarketDataSnapshot:
    """Complete market data snapshot for multiple underlyings."""
    as_of_date: date
    underlyings: Dict[str, UnderlyingMarketData] = field(default_factory=dict)
    correlations: Dict[str, float] = field(default_factory=dict)
    risk_free_rate: float = 0.05


# Alias for backwards compatibility with existing engine interfaces
MarketData = MarketDataSnapshot


def _check_yfinance():
    """Check if yfinance is available."""
    if not HAS_YFINANCE:
        raise ImportError(
            "yfinance is required for market data. Install with: pip install yfinance"
        )


def fetch_spot_prices(tickers: List[str]) -> Dict[str, float]:
    """
    Fetch current spot prices for given tickers.
    
    Args:
        tickers: List of stock tickers (e.g., ["AAPL", "GOOG", "MSFT"])
        
    Returns:
        Dictionary mapping ticker to current price
    """
    _check_yfinance()
    
    prices = {}
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            # Try fast_info first, fall back to info
            try:
                price = stock.fast_info.last_price
            except:
                info = stock.info
                price = info.get("regularMarketPrice") or info.get("currentPrice")
            
            if price:
                prices[ticker] = float(price)
        except Exception as e:
            print(f"Warning: Could not fetch price for {ticker}: {e}")
    
    return prices


def fetch_historical_vol(
    ticker: str, 
    window_days: int = 30,
    annualization_factor: float = 252.0
) -> float:
    """
    Calculate annualized historical volatility from daily returns.
    
    Args:
        ticker: Stock ticker
        window_days: Number of trading days for calculation
        annualization_factor: Trading days per year (default 252)
        
    Returns:
        Annualized volatility as decimal (e.g., 0.25 for 25%)
    """
    _check_yfinance()
    
    stock = yf.Ticker(ticker)
    # Fetch enough data for the window
    end_date = datetime.now()
    start_date = end_date - timedelta(days=int(window_days * 1.5) + 10)
    
    hist = stock.history(start=start_date, end=end_date)
    
    if len(hist) < window_days:
        raise ValueError(f"Not enough history for {ticker}: got {len(hist)} days")
    
    # Use the most recent window_days
    close_prices = hist["Close"].tail(window_days + 1)
    
    # Calculate log returns
    log_returns = np.log(close_prices / close_prices.shift(1)).dropna()
    
    # Annualized volatility
    daily_vol = log_returns.std()
    annualized_vol = daily_vol * np.sqrt(annualization_factor)
    
    return float(annualized_vol)


def fetch_dividends(
    ticker: str, 
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
) -> List[DividendInfo]:
    """
    Fetch dividend information for a stock.
    
    Args:
        ticker: Stock ticker
        start_date: Optional start date filter
        end_date: Optional end date filter
        
    Returns:
        List of DividendInfo with ex-dates and amounts
    """
    _check_yfinance()
    
    stock = yf.Ticker(ticker)
    
    # Get dividend history
    try:
        divs = stock.dividends
    except:
        return []
    
    if divs.empty:
        return []
    
    result = []
    for idx, amount in divs.items():
        ex_date = idx.date() if hasattr(idx, 'date') else idx
        
        # Filter by date range
        if start_date and ex_date < start_date:
            continue
        if end_date and ex_date > end_date:
            continue
            
        result.append(DividendInfo(ex_date=ex_date, amount=float(amount)))
    
    return result


def fetch_correlations(
    tickers: List[str], 
    window_days: int = 60
) -> Dict[str, float]:
    """
    Calculate pairwise correlations from historical returns.
    
    Args:
        tickers: List of stock tickers
        window_days: Number of trading days for calculation
        
    Returns:
        Dictionary with keys like "AAPL_GOOG" and correlation values
    """
    _check_yfinance()
    
    if len(tickers) < 2:
        return {}
    
    # Fetch historical data
    end_date = datetime.now()
    start_date = end_date - timedelta(days=int(window_days * 1.5) + 10)
    
    # Collect returns for each ticker
    returns_data = {}
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(start=start_date, end=end_date)
            if len(hist) > window_days:
                close = hist["Close"].tail(window_days + 1)
                returns = np.log(close / close.shift(1)).dropna()
                returns_data[ticker] = returns
        except Exception as e:
            print(f"Warning: Could not fetch history for {ticker}: {e}")
    
    # Calculate pairwise correlations
    correlations = {}
    ticker_list = list(returns_data.keys())
    
    for i in range(len(ticker_list)):
        for j in range(i + 1, len(ticker_list)):
            t1, t2 = ticker_list[i], ticker_list[j]
            
            # Align dates
            returns1 = returns_data[t1]
            returns2 = returns_data[t2]
            
            # Get common dates
            common_idx = returns1.index.intersection(returns2.index)
            if len(common_idx) < 20:
                continue
                
            r1 = returns1.loc[common_idx]
            r2 = returns2.loc[common_idx]
            
            corr = np.corrcoef(r1, r2)[0, 1]
            key = f"{t1}_{t2}"
            correlations[key] = float(corr)
    
    return correlations


def fetch_risk_free_rate() -> float:
    """
    Fetch current risk-free rate (3-month Treasury).
    
    Returns:
        Risk-free rate as decimal (e.g., 0.05 for 5%)
    """
    _check_yfinance()
    
    try:
        # Use 3-month Treasury Bill rate
        irx = yf.Ticker("^IRX")
        info = irx.fast_info
        rate = info.last_price / 100  # Convert from percentage
        return float(rate)
    except:
        # Fallback to 10-year Treasury
        try:
            tnx = yf.Ticker("^TNX")
            info = tnx.fast_info
            rate = info.last_price / 100
            return float(rate)
        except:
            # Default fallback
            return 0.05


def _project_future_dividends(
    ticker: str,
    from_date: date,
    to_date: date,
    lookback_years: int = 2
) -> List[DividendInfo]:
    """
    Project future dividends from historical payment pattern.

    Looks at trailing history to detect payment frequency and amount,
    then projects forward from the last known ex-date through to_date.

    Args:
        ticker: Stock ticker
        from_date: Start date for projections
        to_date: End date for projections
        lookback_years: Years of history to analyze

    Returns:
        List of projected DividendInfo
    """
    _check_yfinance()

    stock = yf.Ticker(ticker)
    try:
        divs = stock.dividends
    except Exception:
        return []

    if divs.empty or len(divs) < 2:
        return []

    # Filter to trailing lookback_years
    cutoff = from_date - timedelta(days=lookback_years * 365)
    recent = []
    for idx, amount in divs.items():
        ex = idx.date() if hasattr(idx, 'date') else idx
        if ex >= cutoff:
            recent.append((ex, float(amount)))

    if len(recent) < 2:
        return []

    # Detect frequency from median gap between consecutive payments
    gaps = [(recent[i + 1][0] - recent[i][0]).days for i in range(len(recent) - 1)]
    median_gap = sorted(gaps)[len(gaps) // 2]

    # Classify: quarterly (~90d), semi-annual (~180d), annual (~365d)
    if median_gap < 135:
        freq_days = 91  # quarterly
    elif median_gap < 270:
        freq_days = 182  # semi-annual
    else:
        freq_days = 365  # annual

    # Use most recent payment amount
    last_date, last_amount = recent[-1]

    # Project forward from last known ex-date
    projected = []
    next_date = last_date + timedelta(days=freq_days)
    while next_date <= to_date:
        if next_date >= from_date:
            projected.append(DividendInfo(ex_date=next_date, amount=last_amount))
        next_date += timedelta(days=freq_days)

    return projected


def fetch_market_data_snapshot(
    tickers: List[str],
    valuation_date: Optional[date] = None,
    maturity_date: Optional[date] = None,
    vol_window: int = 90,
    corr_window: int = 60
) -> MarketDataSnapshot:
    """
    Fetch complete market data snapshot for multiple underlyings.
    
    Args:
        tickers: List of stock tickers
        valuation_date: Valuation date (default: today)
        maturity_date: Product maturity date (for vol term structure)
        vol_window: Days for historical vol calculation
        corr_window: Days for correlation calculation
        
    Returns:
        MarketDataSnapshot with all market data
    """
    _check_yfinance()
    
    if valuation_date is None:
        valuation_date = date.today()
    
    if maturity_date is None:
        maturity_date = valuation_date + timedelta(days=365 * 3)  # 3 years default
    
    # Fetch spot prices
    spots = fetch_spot_prices(tickers)
    
    # Fetch risk-free rate
    rf_rate = fetch_risk_free_rate()
    
    # Fetch correlations
    correlations = fetch_correlations(tickers, corr_window)
    
    # Build underlying data
    underlyings = {}
    for ticker in tickers:
        spot = spots.get(ticker)
        if spot is None:
            continue
        
        # Fetch historical vol
        try:
            hist_vol = fetch_historical_vol(ticker, vol_window)
        except:
            hist_vol = 0.25  # Default
        
        # Build simple vol term structure (flat for now)
        vol_ts = []
        current = valuation_date
        while current <= maturity_date:
            current += timedelta(days=182)  # ~6 months
            if current <= maturity_date:
                vol_ts.append(VolInfo(date=current, vol=hist_vol))
        vol_ts.append(VolInfo(date=maturity_date, vol=hist_vol))
        
        # Fetch dividends (historical in future range, or project from history)
        divs = fetch_dividends(ticker, valuation_date, maturity_date)
        if not divs:
            divs = _project_future_dividends(ticker, valuation_date, maturity_date)
        
        # Calculate dividend yield using multi-strategy approach
        try:
            stock = yf.Ticker(ticker)
            info = stock.info

            # Strategy 1 (primary): dividendRate / spot
            # dividendRate is annual dividend per share in currency (e.g. $1.00)
            dividend_rate = info.get("dividendRate", 0) or 0
            computed_yield = dividend_rate / spot if (dividend_rate > 0 and spot > 0) else 0

            # Strategy 2 (fallback): trailingAnnualDividendYield (already decimal)
            trailing_yield = info.get("trailingAnnualDividendYield", 0) or 0

            # Strategy 3 (last resort): dividendYield with minimal normalization
            raw_div_yield = info.get("dividendYield", 0) or 0
            if raw_div_yield > 1.0:
                raw_div_yield = raw_div_yield / 100

            # Pick best estimate
            if computed_yield > 0:
                div_yield = computed_yield
            elif trailing_yield > 0:
                div_yield = trailing_yield
            else:
                div_yield = raw_div_yield

            # Cross-validate: if we used a fallback but dividendRate is available,
            # trust the computed value when they disagree by > 2%
            if computed_yield > 0 and div_yield != computed_yield and abs(div_yield - computed_yield) > 0.02:
                div_yield = computed_yield

            # Safety cap at 10%
            div_yield = min(div_yield, 0.10)
        except:
            div_yield = 0
        
        underlyings[ticker] = UnderlyingMarketData(
            ticker=ticker,
            spot=spot,
            historical_vol=hist_vol,
            vol_term_structure=vol_ts,
            dividends=divs,
            dividend_yield=float(div_yield),
        )
    
    return MarketDataSnapshot(
        as_of_date=valuation_date,
        underlyings=underlyings,
        correlations=correlations,
        risk_free_rate=rf_rate,
    )
