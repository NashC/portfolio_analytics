import pandas as pd
import yfinance as yf
import time
from datetime import datetime, timedelta
from pycoingecko import CoinGeckoAPI
from typing import List
import uuid
from db import PriceDatabase
from price_service import price_service

# Initialize price database
price_db = PriceDatabase()

# Mapping of crypto symbols to CoinGecko IDs.
# Mapping from asset symbol to CoinGecko asset ID
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

def fetch_stock_prices(asset: str, start_date: datetime, end_date: datetime) -> pd.DataFrame:
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
    cached_prices = price_db.get_prices(asset, start_date.date(), end_date.date())
    if cached_prices is not None and not price_db.needs_update(asset):
        return cached_prices
        
    try:
        ticker = asset  # Adjust if needed for ticker conversion
        data = yf.download(ticker, start=start_date, end=end_date, progress=False)
        if data.empty:
            print(f"⚠️ No price data for {asset} from yfinance.")
            return None
            
        # Use Adjusted Close as the price
        prices = data[['Adj Close']].rename(columns={'Adj Close': asset})
        
        # Cache the prices
        price_db.save_prices(asset, prices, 'yfinance')
        
        return prices
    except Exception as e:
        print(f"Error fetching price for {asset} using yfinance: {e}")
        return None

def fetch_crypto_prices(asset: str, start_date: datetime, end_date: datetime) -> pd.DataFrame:
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
    cached_prices = price_db.get_prices(asset, start_date.date(), end_date.date())
    if cached_prices is not None and not price_db.needs_update(asset):
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
                
                # Cache the prices
                price_db.save_prices(asset, df, 'coingecko')
                
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
    """
    Computes a daily time series of the portfolio value using historical prices.
    
    Args:
        transactions: DataFrame of normalized transactions.
        
    Returns:
        A DataFrame indexed by date with a 'portfolio_value' column.
    """
    # Sort transactions by timestamp
    transactions = transactions.sort_values("timestamp")
    start_date = transactions["timestamp"].min()
    end_date = transactions["timestamp"].max()
    date_range = pd.date_range(start=start_date, end=end_date, freq="D", tz="UTC")
    
    # Get unique assets
    assets = transactions["asset"].dropna().unique()
    
    # Calculate daily cumulative holdings
    transactions["date"] = transactions["timestamp"].dt.floor("D")
    daily_holdings = transactions.groupby(["date", "asset"])["quantity"].sum().unstack(fill_value=0)
    daily_holdings = daily_holdings.reindex(date_range, method="ffill").fillna(0)
    
    # Get historical prices
    prices_df = price_service.get_multi_asset_prices(assets, start_date, end_date)
    
    if prices_df.empty:
        print("❌ No price data available for portfolio valuation.")
        return pd.DataFrame()
    
    # Calculate portfolio value
    portfolio_values = pd.DataFrame(index=date_range)
    portfolio_values["portfolio_value"] = 0
    
    for asset in assets:
        if asset in prices_df.columns:
            portfolio_values[f"{asset}_value"] = daily_holdings[asset] * prices_df[asset]
            portfolio_values["portfolio_value"] += portfolio_values[f"{asset}_value"]
    
    return portfolio_values

def compute_portfolio_time_series(transactions: pd.DataFrame) -> pd.DataFrame:
    """
    Legacy method - now redirects to compute_portfolio_time_series_with_external_prices
    """
    return compute_portfolio_time_series_with_external_prices(transactions)

##########################################
# Cost Basis Calculations (Placeholders)
##########################################

def calculate_cost_basis_fifo(transactions: pd.DataFrame) -> pd.DataFrame:
    """Calculate cost basis using FIFO method"""
    from reporting import PortfolioReporting
    reporter = PortfolioReporting(transactions)
    return reporter.calculate_tax_lots(method="fifo")

def calculate_cost_basis_avg(transactions: pd.DataFrame) -> pd.DataFrame:
    """Calculate cost basis using average cost method"""
    from reporting import PortfolioReporting
    reporter = PortfolioReporting(transactions)
    return reporter.calculate_tax_lots(method="avg")
