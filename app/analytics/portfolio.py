import pandas as pd
import yfinance as yf
import time
from datetime import datetime, timedelta, date
from pycoingecko import CoinGeckoAPI
from typing import List, Optional, Dict
import uuid
import numpy as np

from app.services.price_service import PriceService
from app.db.base import Asset, PriceData, DataSource
from app.db.session import get_db

# Initialize price service
price_service = PriceService()

# Mapping of crypto symbols to CoinGecko IDs
CRYPTO_ASSET_IDS = {
    "AAVE": "aave",
    "ADA": "cardano",
    "ALGO": "algorand",
    "ATOM": "cosmos",
    "AVAX": "avalanche-2",
    "BAT": "basic-attention-token",
    "BCH": "bitcoin-cash",
    "BTC": "bitcoin",
    "COMP": "compound-governance-token",
    "CGLD": "celo",  # CGLD is an older name for CELO
    "DOT": "polkadot",
    "EOS": "eos",
    "ETC": "ethereum-classic",
    "ETH": "ethereum",
    "ETH2": "ethereum",  # ETH2 is a placeholder; no separate ID on CoinGecko
    "FIL": "filecoin",
    "FLR": "flare-networks",
    "GUSD": "gemini-dollar",
    "LINK": "chainlink",
    "LTC": "litecoin",
    "MANA": "decentraland",
    "MATIC": "matic-network",  # Updated from "polygon"
    "MKR": "maker",
    "REP": "augur",
    "SNX": "synthetix-network-token",
    "SOL": "solana",
    "STORJ": "storj",
    "SUSHI": "sushi",
    "UNI": "uniswap",
    "USDC": "usd-coin",
    "XLM": "stellar",
    "XRP": "ripple",
    "XTZ": "tezos",
    "YFI": "yearn-finance",
    "ZEC": "zcash",
    "ZRX": "0x"
}

#########################
# Price Fetching Helpers
#########################

def fetch_stock_prices(asset: str, start_date: datetime, end_date: datetime) -> Optional[pd.DataFrame]:
    """
    Fetch historical stock prices using yfinance.
    Uses local cache when available.
    """
    # Skip known non-tradeable assets
    NON_TRADEABLE = ["USD", "USDC", "GUSD"]
    if asset in NON_TRADEABLE:
        date_range = pd.date_range(start=start_date, end=end_date, freq="D")
        return pd.DataFrame({asset: 1.0}, index=date_range)
    
    # Check cache first
    cached_prices = price_service.get_price_range(asset, start_date, end_date)
    if not cached_prices.empty:
        return cached_prices
        
    try:
        ticker = asset  # Adjust if needed for ticker conversion
        data = yf.download(ticker, start=start_date, end=end_date, progress=False)
        if data.empty:
            print(f"⚠️ No price data for {asset} from yfinance.")
            return None
            
        # Use Adjusted Close as the price
        prices = data[['Adj Close']].rename(columns={'Adj Close': asset})
        
        # Save prices to database
        with next(get_db()) as db:
            for date, row in prices.iterrows():
                price_data = PriceData(
                    asset=Asset(symbol=asset),
                    source=DataSource(name='yfinance'),
                    date=date.date(),
                    close=row[asset]
                )
                db.add(price_data)
            db.commit()
        
        return prices
    except Exception as e:
        print(f"Error fetching price for {asset} using yfinance: {e}")
        return None

def fetch_crypto_prices(asset: str, start_date: datetime, end_date: datetime) -> Optional[pd.DataFrame]:
    """
    Fetch historical crypto prices using CoinGecko.
    Uses local cache when available.
    """
    asset = asset.upper().strip()
    
    # Handle stablecoins
    STABLECOINS = ["USDC", "GUSD", "USD", "USDT", "DAI", "BUSD"]
    if asset in STABLECOINS:
        date_range = pd.date_range(start=start_date, end=end_date, freq="D")
        return pd.DataFrame({asset: 1.0}, index=date_range)
    
    # Check cache first
    cached_prices = price_service.get_price_range(asset, start_date, end_date)
    if not cached_prices.empty:
        return cached_prices
    
    try:
        # For non-stablecoins, try CoinGecko API
        coin_id = CRYPTO_ASSET_IDS.get(asset)
        if not coin_id:
            print(f"⚠️ No CoinGecko mapping for asset: {asset}")
            return None
            
        # Calculate date ranges
        today = datetime.now().date()
        api_start = max(start_date, (today - timedelta(days=364)))  # CoinGecko's 365-day limit
        
        if end_date > today:
            api_end = today
        else:
            api_end = end_date
            
        # Only call API if we're within the last 365 days
        if api_start <= api_end:
            cg = CoinGeckoAPI()
            start_ts = int(time.mktime(datetime.combine(api_start, datetime.min.time()).timetuple()))
            end_ts = int(time.mktime(datetime.combine(api_end, datetime.min.time()).timetuple()))
            
            data = cg.get_coin_market_chart_range_by_id(
                id=coin_id,
                vs_currency="usd",
                from_timestamp=start_ts,
                to_timestamp=end_ts
            )
            
            prices_list = data.get("prices", [])
            if prices_list:
                df = pd.DataFrame(prices_list, columns=["timestamp", asset])
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
                df = df.set_index("timestamp")
                df = df.resample("D").last()  # Ensure daily frequency
                
                # Save prices to database
                with next(get_db()) as db:
                    for date, row in df.iterrows():
                        price_data = PriceData(
                            asset=Asset(symbol=asset),
                            source=DataSource(name='coingecko'),
                            date=date.date(),
                            close=row[asset]
                        )
                        db.add(price_data)
                    db.commit()
                
                return df
                
        return None
        
    except Exception as e:
        print(f"Error fetching crypto price for {asset}: {e}")
        return None

def fetch_historical_prices(assets: List[str], start_date: datetime, end_date: datetime) -> pd.DataFrame:
    """
    Fetch external daily closing prices for each asset.
    Uses a combination of:
    1. CoinGecko API for recent crypto prices
    2. yfinance for stock prices
    3. Fixed 1.0 price for stablecoins
    4. Transaction prices as fallback
    """
    price_dfs = []
    
    # Handle stablecoins first
    STABLECOINS = ["USDC", "GUSD", "USD", "USDT", "DAI", "BUSD"]
    date_range = pd.date_range(start=start_date, end=end_date, freq="D")
    
    for stable in STABLECOINS:
        if stable in assets:
            price_dfs.append(pd.DataFrame({stable: 1.0}, index=date_range))
            assets = [a for a in assets if a != stable]
    
    # Fetch prices for remaining assets
    for asset in assets:
        asset = asset.upper().strip()
        if asset in CRYPTO_ASSET_IDS:
            df_price = fetch_crypto_prices(asset, start_date, end_date)
        else:
            df_price = fetch_stock_prices(asset, start_date, end_date)
            
        if df_price is not None:
            price_dfs.append(df_price)
    
    if price_dfs:
        # Combine all price data
        prices_df = pd.concat(price_dfs, axis=1)
        prices_df.index = pd.DatetimeIndex(prices_df.index)
        
        # Forward fill missing values
        prices_df.ffill(inplace=True)
        
        return prices_df
    else:
        print("❌ No valid external price data retrieved.")
        return pd.DataFrame()


##########################################
# Portfolio Time Series Calculation
##########################################

def compute_portfolio_time_series_with_external_prices(transactions: pd.DataFrame) -> pd.DataFrame:
    """Compute portfolio value over time using external price data."""
    # Get unique assets and date range
    assets = transactions['asset'].unique()
    start_date = transactions['timestamp'].min()
    end_date = transactions['timestamp'].max()
    
    # Fetch historical prices
    prices_df = fetch_historical_prices(assets, start_date, end_date)
    if prices_df.empty:
        return pd.DataFrame()
    
    # Compute holdings over time
    holdings = pd.DataFrame(index=prices_df.index)
    for asset in assets:
        if asset in prices_df.columns:
            holdings[asset] = transactions[transactions['asset'] == asset]['amount'].cumsum()
    
    # Compute portfolio value
    portfolio_value = holdings * prices_df
    portfolio_value['total'] = portfolio_value.sum(axis=1)
    
    return portfolio_value

def compute_portfolio_time_series(transactions: pd.DataFrame) -> pd.DataFrame:
    """Compute portfolio value over time using transaction prices."""
    # Group by date and asset
    grouped = transactions.groupby(['timestamp', 'asset'])
    
    # Compute holdings and value
    holdings = grouped['amount'].sum().unstack(fill_value=0)
    values = grouped.apply(lambda x: (x['amount'] * x['price']).sum()).unstack(fill_value=0)
    
    # Compute total value
    portfolio_value = pd.DataFrame(index=holdings.index)
    for asset in holdings.columns:
        portfolio_value[asset] = values[asset]
    portfolio_value['total'] = portfolio_value.sum(axis=1)
    
    return portfolio_value

##########################################
# Cost Basis Calculations (Placeholders)
##########################################

def calculate_cost_basis_fifo(transactions: pd.DataFrame) -> pd.DataFrame:
    """Calculate FIFO cost basis for each asset."""
    # Sort transactions by timestamp
    transactions = transactions.sort_values('timestamp')
    
    # Group by asset
    cost_basis = {}
    for asset, group in transactions.groupby('asset'):
        # Initialize FIFO queue
        fifo_queue = []
        cost_basis[asset] = []
        
        for _, tx in group.iterrows():
            # Use quantity column and handle buy/sell based on transaction type
            if tx['type'] == 'buy' or tx['quantity'] > 0:  # Buy
                fifo_queue.append((abs(tx['quantity']), tx['price']))
            elif tx['type'] == 'sell' or tx['quantity'] < 0:  # Sell
                remaining = abs(tx['quantity'])
                while remaining > 0 and fifo_queue:
                    lot_amount, lot_price = fifo_queue[0]
                    if lot_amount <= remaining:
                        # Use entire lot
                        cost_basis[asset].append({
                            'date': tx['timestamp'],
                            'amount': lot_amount,
                            'price': tx['price'],
                            'cost_basis': lot_price,
                            'gain_loss': (tx['price'] - lot_price) * lot_amount
                        })
                        remaining -= lot_amount
                        fifo_queue.pop(0)
                    else:
                        # Use part of lot
                        cost_basis[asset].append({
                            'date': tx['timestamp'],
                            'amount': remaining,
                            'price': tx['price'],
                            'cost_basis': lot_price,
                            'gain_loss': (tx['price'] - lot_price) * remaining
                        })
                        fifo_queue[0] = (lot_amount - remaining, lot_price)
                        remaining = 0
    
    # Convert to DataFrame
    result = pd.DataFrame()
    for asset, basis in cost_basis.items():
        if basis:
            df = pd.DataFrame(basis)
            df['asset'] = asset
            result = pd.concat([result, df])
    
    return result

def calculate_cost_basis_avg(transactions: pd.DataFrame) -> pd.DataFrame:
    """Calculate average cost basis for each asset."""
    # Group by asset
    cost_basis = {}
    for asset, group in transactions.groupby('asset'):
        # Filter for buy transactions only
        buy_transactions = group[group['type'] == 'buy']
        if not buy_transactions.empty:
            # Calculate weighted average cost
            total_quantity = buy_transactions['quantity'].sum()
            if total_quantity > 0:
                avg_cost = (buy_transactions['quantity'] * buy_transactions['price']).sum() / total_quantity
                cost_basis[asset] = avg_cost
    
    return pd.DataFrame.from_dict(cost_basis, orient='index', columns=['avg_cost_basis'])

##########################################
# Portfolio Analysis Functions
##########################################

def calculate_portfolio_value(holdings: pd.DataFrame, price_service: PriceService, 
                            start_date: date, end_date: date) -> pd.DataFrame:
    """
    Calculate portfolio value over time.
    
    Args:
        holdings: DataFrame with date index and asset columns containing quantities
        price_service: PriceService instance for fetching prices
        start_date: Start date for calculation
        end_date: End date for calculation
        
    Returns:
        DataFrame with portfolio values by asset and total
    """
    # Create date range
    date_range = pd.date_range(start=start_date, end=end_date, freq='D')
    
    # Initialize result DataFrame
    result = pd.DataFrame(index=date_range)
    
    # Calculate value for each asset
    for asset in holdings.columns:
        if asset == 'date':
            continue
            
        # Get prices for this asset
        prices = price_service.get_price_range(asset, start_date, end_date)
        
        if prices.empty:
            # Use constant price of 1.0 for stablecoins
            if asset.upper() in ['USDC', 'USDT', 'DAI', 'BUSD', 'GUSD']:
                prices = pd.Series(1.0, index=date_range, name=asset)
            else:
                # Skip assets without price data
                continue
        else:
            # Reindex to match our date range
            prices = prices.reindex(date_range, method='ffill')
        
        # Get holdings for this asset (forward fill)
        asset_holdings = holdings[asset].reindex(date_range, method='ffill').fillna(0)
        
        # Calculate value
        result[f'{asset}_value'] = asset_holdings * prices
    
    # Calculate total value
    value_columns = [col for col in result.columns if col.endswith('_value')]
    result['total_value'] = result[value_columns].sum(axis=1)
    
    return result

def calculate_returns(holdings: pd.DataFrame, price_service: PriceService,
                     start_date: date, end_date: date) -> pd.DataFrame:
    """
    Calculate daily returns for the portfolio.
    
    Args:
        holdings: DataFrame with date index and asset columns containing quantities
        price_service: PriceService instance for fetching prices
        start_date: Start date for calculation
        end_date: End date for calculation
        
    Returns:
        DataFrame with daily returns by asset and total
    """
    # Get portfolio values
    portfolio_value = calculate_portfolio_value(holdings, price_service, start_date, end_date)
    
    # Calculate returns
    returns = portfolio_value.pct_change().dropna()
    
    # Rename columns to indicate returns
    returns.columns = [col.replace('_value', '_return') for col in returns.columns]
    
    return returns

def calculate_volatility(holdings: pd.DataFrame, price_service: PriceService,
                        start_date: date, end_date: date, annualized: bool = True) -> float:
    """
    Calculate portfolio volatility.
    
    Args:
        holdings: DataFrame with date index and asset columns containing quantities
        price_service: PriceService instance for fetching prices
        start_date: Start date for calculation
        end_date: End date for calculation
        annualized: Whether to annualize the volatility
        
    Returns:
        Portfolio volatility as a float
    """
    # Get returns
    returns = calculate_returns(holdings, price_service, start_date, end_date)
    
    # Calculate volatility of total returns
    volatility = returns['total_return'].std()
    
    if annualized:
        volatility *= np.sqrt(252)  # Annualize assuming 252 trading days
    
    return volatility

def calculate_sharpe_ratio(holdings: pd.DataFrame, price_service: PriceService,
                          start_date: date, end_date: date, risk_free_rate: float = 0.02) -> float:
    """
    Calculate Sharpe ratio for the portfolio.
    
    Args:
        holdings: DataFrame with date index and asset columns containing quantities
        price_service: PriceService instance for fetching prices
        start_date: Start date for calculation
        end_date: End date for calculation
        risk_free_rate: Annual risk-free rate (default 2%)
        
    Returns:
        Sharpe ratio as a float
    """
    # Get returns
    returns = calculate_returns(holdings, price_service, start_date, end_date)
    
    # Calculate excess returns
    daily_risk_free = risk_free_rate / 252  # Convert to daily
    excess_returns = returns['total_return'] - daily_risk_free
    
    # Calculate Sharpe ratio
    if excess_returns.std() == 0:
        return 0.0
    
    sharpe = excess_returns.mean() / excess_returns.std() * np.sqrt(252)  # Annualized
    
    return sharpe

def calculate_drawdown(holdings: pd.DataFrame, price_service: PriceService,
                      start_date: date, end_date: date) -> pd.DataFrame:
    """
    Calculate drawdown for the portfolio.
    
    Args:
        holdings: DataFrame with date index and asset columns containing quantities
        price_service: PriceService instance for fetching prices
        start_date: Start date for calculation
        end_date: End date for calculation
        
    Returns:
        DataFrame with drawdown information
    """
    # Get portfolio values
    portfolio_value = calculate_portfolio_value(holdings, price_service, start_date, end_date)
    
    # Calculate running maximum (peak)
    peak_value = portfolio_value['total_value'].expanding().max()
    
    # Calculate drawdown
    drawdown = (portfolio_value['total_value'] - peak_value) / peak_value
    
    # Create result DataFrame
    result = pd.DataFrame({
        'peak_value': peak_value,
        'current_value': portfolio_value['total_value'],
        'drawdown': drawdown
    })
    
    return result

def calculate_correlation_matrix(holdings: pd.DataFrame, price_service: PriceService,
                               start_date: date, end_date: date) -> pd.DataFrame:
    """
    Calculate correlation matrix for portfolio assets.
    
    Args:
        holdings: DataFrame with date index and asset columns containing quantities
        price_service: PriceService instance for fetching prices
        start_date: Start date for calculation
        end_date: End date for calculation
        
    Returns:
        Correlation matrix as DataFrame
    """
    # Get returns for each asset
    returns = calculate_returns(holdings, price_service, start_date, end_date)
    
    # Get only asset return columns (exclude total_return)
    asset_returns = returns[[col for col in returns.columns if col.endswith('_return') and col != 'total_return']]
    
    # Remove '_return' suffix from column names
    asset_returns.columns = [col.replace('_return', '') for col in asset_returns.columns]
    
    # Calculate correlation matrix
    correlation_matrix = asset_returns.corr()
    
    # Handle NaN values (which occur when an asset has zero variance, like stablecoins)
    # Fill diagonal NaN values with 1.0 (perfect correlation with itself)
    np.fill_diagonal(correlation_matrix.values, 1.0)
    
    # Fill off-diagonal NaN values with 0.0 (no correlation when one asset has zero variance)
    correlation_matrix = correlation_matrix.fillna(0.0)
    
    return correlation_matrix
