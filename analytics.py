import pandas as pd
import yfinance as yf
import time
from datetime import datetime, timedelta
from pycoingecko import CoinGeckoAPI
from typing import List
import uuid

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
    "MATIC": "polygon",
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
    """
    try:
        ticker = asset  # Adjust if needed for ticker conversion.
        data = yf.download(ticker, start=start_date, end=end_date, progress=False)
        if data.empty:
            print(f"⚠️ No price data for {asset} from yfinance.")
            return None
        # Use Adjusted Close as the price.
        prices = data[['Adj Close']].rename(columns={'Adj Close': asset})
        return prices
    except Exception as e:
        print(f"Error fetching price for {asset} using yfinance: {e}")
        return None

def fetch_crypto_prices(asset: str, start_date: datetime, end_date: datetime) -> pd.DataFrame:
    """
    Fetch historical crypto prices using CoinGecko.
    Returns a DataFrame with dates as index and one column for the asset price.
    """
    try:
        asset = asset.upper().strip()
        coin_id = CRYPTO_ASSET_IDS.get(asset)
        if not coin_id:
            print(f"⚠️ No CoinGecko mapping for asset: {asset}")
            return None
        cg = CoinGeckoAPI()
        # Convert start_date and end_date to Unix timestamps.
        start_ts = int(time.mktime(datetime.combine(start_date, datetime.min.time()).timetuple()))
        end_ts = int(time.mktime(datetime.combine(end_date, datetime.min.time()).timetuple()))
        data = cg.get_coin_market_chart_range_by_id(
            id=coin_id,
            vs_currency="usd",
            from_timestamp=start_ts,
            to_timestamp=end_ts
        )

        prices_list = data.get("prices", [])
        if not prices_list:
            print(f"⚠️ No price data returned for crypto {asset} from CoinGecko.")
            return None
        # Create a DataFrame from the list: timestamps in ms and prices.
        df = pd.DataFrame(prices_list, columns=["timestamp", asset])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms").dt.date
        df = df.groupby("timestamp").last()  # Use last available price of the day.
        df.index = pd.to_datetime(df.index)
        return df
    except Exception as e:
        print(f"Error fetching crypto price for {asset}: {e}")
        return None

def fetch_historical_prices(assets: List[str], start_date: datetime, end_date: datetime) -> pd.DataFrame:
    """
    Fetch external daily closing prices for each asset.
    For crypto assets (as defined in CRYPTO_ASSET_IDS), uses CoinGecko.
    For other assets, uses yfinance.
    Returns a DataFrame with dates as index and assets as columns.
    """
    price_dfs = []
    for asset in assets:
        asset = asset.upper().strip()
        if asset in CRYPTO_ASSET_IDS:
            df_price = fetch_crypto_prices(asset, start_date, end_date)
        else:
            df_price = fetch_stock_prices(asset, start_date, end_date)
        if df_price is not None:
            price_dfs.append(df_price)
            
    STABLECOINS = ["USDC", "GUSD", "USD"]

    if price_dfs:
        prices_df = pd.concat(price_dfs, axis=1)
        prices_df.ffill(inplace=True)

        # Inject flat 1.0 prices for known stablecoins
        for stable in STABLECOINS:
            if stable in assets:
                prices_df[stable] = 1.0

        return prices_df

    else:
        print("❌ No valid external price data retrieved.")
        return pd.DataFrame()


##########################################
# Portfolio Time Series Calculation
##########################################

def compute_portfolio_time_series_with_external_prices(transactions: pd.DataFrame) -> pd.DataFrame:
    """
    Computes a daily time series of the portfolio value using external prices.
    
    - Calculates cumulative holdings for each asset over time from transactions.
    - Fetches external historical prices (stocks via yfinance, crypto via CoinGecko).
    - For every day in the date range, multiplies cumulative holdings by the external price.
    
    Args:
        transactions: DataFrame of normalized transactions.
        
    Returns:
        A DataFrame indexed by date with a 'portfolio_value' column.
    """
    # Sort transactions by timestamp.
    transactions = transactions.sort_values("timestamp")
    start_date = transactions["timestamp"].min().date()
    end_date = transactions["timestamp"].max().date()
    date_range = pd.date_range(start=start_date, end=end_date, freq="D", tz="UTC")
    
    # Get unique assets.
    assets = transactions["asset"].dropna().unique()
    
    # Calculate daily cumulative holdings.
    transactions["date"] = transactions["timestamp"].dt.floor("D")
    daily_holdings = transactions.groupby(["date", "asset"])["quantity"].sum().unstack(fill_value=0)
    daily_holdings = daily_holdings.reindex(date_range, method="ffill").fillna(0)
    
    # Fetch external prices for the assets.
    external_prices = fetch_historical_prices(assets, start_date, end_date)
    if external_prices.empty:
        print("🚫 Skipping portfolio valuation — no external prices found.")
        return pd.DataFrame()

    external_prices = external_prices.reindex(date_range, method="ffill").fillna(0)
    
    # Multiply holdings by external prices and sum across assets to get portfolio value.
    portfolio_values = (daily_holdings * external_prices).sum(axis=1)
    
    portfolio_ts = pd.DataFrame({"portfolio_value": portfolio_values})
    portfolio_ts.index.name = "timestamp"
    return portfolio_ts

def compute_portfolio_time_series(transactions: pd.DataFrame) -> pd.DataFrame:
    """
    Computes a daily time series of portfolio value using the last transaction price
    as a proxy. This method does not use external price data.
    
    Args:
        transactions: DataFrame of normalized transactions.
        
    Returns:
        A DataFrame indexed by date with a 'portfolio_value' column.
    """
    transactions = transactions.sort_values("timestamp")
    # Group by day and asset, summing quantity.
    holdings = transactions.groupby([pd.Grouper(key="timestamp", freq="D"), "asset"]).agg({
        "quantity": "sum"
    }).unstack(fill_value=0)
    
    # Use the last transaction price for each asset as valuation.
    prices = transactions.groupby("asset")["price"].last()
    
    daily_value = holdings.multiply(prices, axis=1).sum(axis=1)
    portfolio_ts = pd.DataFrame({"portfolio_value": daily_value})
    return portfolio_ts

##########################################
# Cost Basis Calculations (Placeholders)
##########################################

def calculate_cost_basis_fifo(transactions: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate cost basis and realized gains using the FIFO method.
    Placeholder implementation.
    """
    # TODO: Implement FIFO logic.
    return pd.DataFrame(columns=["asset", "timestamp", "proceeds", "cost_basis", "gain_loss", "holding_period"])

def calculate_cost_basis_avg(transactions: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate cost basis and realized gains using the Average Cost method.
    Placeholder implementation.
    """
    # TODO: Implement Average Cost logic.
    return pd.DataFrame(columns=["asset", "timestamp", "proceeds", "cost_basis", "gain_loss", "holding_period"])
