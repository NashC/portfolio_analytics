from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Union, Tuple
import pandas as pd
import numpy as np
import yfinance as yf
import requests
import time
import logging
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, func

from app.db.base import Asset, DataSource, PriceData, PositionDaily
from app.db.session import get_db

# Set up logging
logger = logging.getLogger(__name__)

class PriceService:
    """Service for managing and retrieving price data."""
    
    def __init__(self):
        """Initialize the price service."""
        # Add mapping for CELO to CGLD (since price data is stored under CELO)
        self.asset_mapping = {
            "CGLD": "CELO",  # When querying database, map CGLD to CELO
            "ETH2": "ETH",   # ETH2 uses ETH price
        }
        self.stablecoins = {'USD', 'USDC', 'USDT', 'DAI'}
        
        # Stock symbol mappings for yfinance
        self.stock_symbols = {
            'AAPL': 'AAPL',
            'GOOGL': 'GOOGL',
            'MSFT': 'MSFT',
            'TSLA': 'TSLA',
            'AMZN': 'AMZN',
            'NVDA': 'NVDA',
            'META': 'META',
            'NFLX': 'NFLX',
            'SPY': 'SPY',
            'QQQ': 'QQQ',
            'VTI': 'VTI',
        }
        
        # CoinGecko API settings
        self.coingecko_base_url = "https://api.coingecko.com/api/v3"
        self.coingecko_rate_limit = 1.0  # seconds between requests
        self.last_coingecko_request = 0
        
        # Crypto symbol mappings for CoinGecko
        self.crypto_coingecko_ids = {
            'BTC': 'bitcoin',
            'ETH': 'ethereum',
            'ADA': 'cardano',
            'DOT': 'polkadot',
            'LINK': 'chainlink',
            'UNI': 'uniswap',
            'AAVE': 'aave',
            'SUSHI': 'sushi',
            'COMP': 'compound-governance-token',
            'MKR': 'maker',
            'SNX': 'havven',
            'YFI': 'yearn-finance',
            'CELO': 'celo',
            'ALGO': 'algorand',
            'ATOM': 'cosmos',
            'SOL': 'solana',
            'AVAX': 'avalanche-2',
            'MATIC': 'matic-network',
            'FTM': 'fantom',
            'NEAR': 'near',
            'ICP': 'internet-computer',
            'FLOW': 'flow',
            'EGLD': 'elrond-erd-2',
            'THETA': 'theta-token',
            'VET': 'vechain',
            'FIL': 'filecoin',
            'TRX': 'tron',
            'EOS': 'eos',
            'XTZ': 'tezos',
            'NEO': 'neo',
            'IOTA': 'iota',
            'DASH': 'dash',
            'ETC': 'ethereum-classic',
            'ZEC': 'zcash',
            'XMR': 'monero',
            'LTC': 'litecoin',
            'BCH': 'bitcoin-cash',
            'XRP': 'ripple',
            'BNB': 'binancecoin',
            'DOGE': 'dogecoin',
            'SHIB': 'shiba-inu',
        }
        
    def _normalize_asset(self, asset: str) -> str:
        """Normalize asset symbol to standard format."""
        # Remove any trailing slashes
        asset = asset.rstrip("/")
        # Convert to uppercase
        asset = asset.upper()
        # Apply asset mapping if exists
        return self.asset_mapping.get(asset, asset)
        
    def _rate_limit_coingecko(self):
        """Apply rate limiting for CoinGecko API."""
        current_time = time.time()
        time_since_last = current_time - self.last_coingecko_request
        if time_since_last < self.coingecko_rate_limit:
            time.sleep(self.coingecko_rate_limit - time_since_last)
        self.last_coingecko_request = time.time()
        
    def get_price(self, asset: str, date_: Union[date, datetime]) -> Optional[float]:
        """Get the closing price for an asset on a specific date."""
        if isinstance(date_, datetime):
            date_ = date_.date()
            
        with next(get_db()) as db:
            query = (
                select(PriceData.close)
                .join(Asset)
                .where(
                    and_(
                        Asset.symbol == self._normalize_asset(asset).replace("/", ""),
                        PriceData.date == date_
                    )
                )
                .order_by(PriceData.confidence_score.desc())
                .limit(1)
            )
            result = db.execute(query).scalar_one_or_none()
            return result
            
    def get_price_with_fallback(self, asset: str, date_: Union[date, datetime]) -> Optional[float]:
        """
        Get price with fallback to external APIs if not found in database (AP-3).
        
        This method guarantees a price is returned if the asset is supported.
        """
        if isinstance(date_, datetime):
            date_ = date_.date()
            
        # First try to get from database
        price = self.get_price(asset, date_)
        if price is not None:
            return price
            
        # Handle stablecoins
        normalized_asset = self._normalize_asset(asset)
        if normalized_asset in self.stablecoins:
            return 1.0
            
        # Try to fetch from external sources
        try:
            # Try stocks first (yfinance)
            if normalized_asset in self.stock_symbols:
                price = self._fetch_stock_price_yfinance(normalized_asset, date_)
                if price is not None:
                    return price
                    
            # Try crypto (CoinGecko)
            if normalized_asset in self.crypto_coingecko_ids:
                price = self._fetch_crypto_price_coingecko(normalized_asset, date_)
                if price is not None:
                    return price
                    
        except Exception as e:
            logger.error(f"Error fetching price for {asset} on {date_}: {e}")
            
        # If all else fails, raise clear error
        raise ValueError(f"Price not available for {asset} on {date_}. "
                        f"Asset may not be supported or date may be outside available range.")
        
    def _fetch_stock_price_yfinance(self, symbol: str, target_date: date) -> Optional[float]:
        """Fetch stock price from yfinance."""
        try:
            ticker = yf.Ticker(symbol)
            # Get data for a small range around the target date
            start_date = target_date - timedelta(days=5)
            end_date = target_date + timedelta(days=5)
            
            hist = ticker.history(start=start_date, end=end_date)
            if hist.empty:
                return None
                
            # Try to get exact date first
            target_str = target_date.strftime('%Y-%m-%d')
            if target_str in hist.index.strftime('%Y-%m-%d'):
                return float(hist.loc[hist.index.strftime('%Y-%m-%d') == target_str, 'Close'].iloc[0])
                
            # If exact date not found, get closest previous date
            hist_dates = hist.index.date
            valid_dates = [d for d in hist_dates if d <= target_date]
            if valid_dates:
                closest_date = max(valid_dates)
                return float(hist.loc[hist.index.date == closest_date, 'Close'].iloc[0])
                
        except Exception as e:
            logger.warning(f"Failed to fetch stock price for {symbol}: {e}")
            
        return None
        
    def _fetch_crypto_price_coingecko(self, symbol: str, target_date: date) -> Optional[float]:
        """Fetch crypto price from CoinGecko."""
        try:
            coingecko_id = self.crypto_coingecko_ids.get(symbol)
            if not coingecko_id:
                return None
                
            self._rate_limit_coingecko()
            
            # Format date for CoinGecko API (DD-MM-YYYY)
            date_str = target_date.strftime('%d-%m-%Y')
            
            url = f"{self.coingecko_base_url}/coins/{coingecko_id}/history"
            params = {
                'date': date_str,
                'localization': 'false'
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if 'market_data' in data and 'current_price' in data['market_data']:
                usd_price = data['market_data']['current_price'].get('usd')
                if usd_price:
                    return float(usd_price)
                    
        except Exception as e:
            logger.warning(f"Failed to fetch crypto price for {symbol}: {e}")
            
        return None
        
    def ensure_price_coverage(self, start_date: date, end_date: date, 
                            asset_ids: Optional[List[int]] = None) -> Dict[str, int]:
        """
        Ensure price coverage for all assets in position_daily table (AP-3).
        
        Args:
            start_date: Start date for coverage check
            end_date: End date for coverage check  
            asset_ids: Optional list of specific asset IDs to check
            
        Returns:
            Dict with coverage statistics
        """
        logger.info(f"Ensuring price coverage from {start_date} to {end_date}")
        
        with next(get_db()) as db:
            # Get all unique asset/date combinations from position_daily
            query = (
                select(PositionDaily.asset_id, PositionDaily.date, Asset.symbol)
                .join(Asset)
                .where(
                    and_(
                        PositionDaily.date >= start_date,
                        PositionDaily.date <= end_date
                    )
                )
            )
            
            if asset_ids:
                query = query.where(PositionDaily.asset_id.in_(asset_ids))
                
            query = query.distinct()
            
            required_prices = db.execute(query).all()
            
            stats = {
                'total_required': len(required_prices),
                'found_in_db': 0,
                'fetched_external': 0,
                'missing': 0,
                'errors': []
            }
            
            for asset_id, price_date, symbol in required_prices:
                try:
                    # Check if price exists in database
                    existing_price = db.execute(
                        select(PriceData.close)
                        .where(
                            and_(
                                PriceData.asset_id == asset_id,
                                PriceData.date == price_date
                            )
                        )
                    ).scalar_one_or_none()
                    
                    if existing_price is not None:
                        stats['found_in_db'] += 1
                        continue
                        
                    # Try to fetch from external sources
                    try:
                        price = self.get_price_with_fallback(symbol, price_date)
                        if price is not None:
                            # Store the fetched price in database
                            self._store_fetched_price(db, asset_id, price_date, price, symbol)
                            stats['fetched_external'] += 1
                        else:
                            stats['missing'] += 1
                            stats['errors'].append(f"No price found for {symbol} on {price_date}")
                    except Exception as e:
                        stats['missing'] += 1
                        stats['errors'].append(f"Error fetching {symbol} on {price_date}: {str(e)}")
                        
                except Exception as e:
                    stats['errors'].append(f"Database error for {symbol} on {price_date}: {str(e)}")
                    
            db.commit()
            
        logger.info(f"Price coverage complete: {stats}")
        return stats
        
    def _store_fetched_price(self, db: Session, asset_id: int, price_date: date, 
                           price: float, symbol: str):
        """Store a fetched price in the database."""
        try:
            # Get or create a data source for external fetches
            external_source = db.execute(
                select(DataSource).where(DataSource.name == "External_API")
            ).scalar_one_or_none()
            
            if not external_source:
                external_source = DataSource(
                    name="External_API",
                    type="aggregator",
                    priority=50  # Lower priority than primary sources
                )
                db.add(external_source)
                db.flush()  # Get the ID
                
            # Create price record
            price_record = PriceData(
                asset_id=asset_id,
                source_id=external_source.source_id,
                date=price_date,
                open=price,  # Use same price for all OHLC since we only have close
                high=price,
                low=price,
                close=price,
                confidence_score=75.0  # Medium confidence for external fetches
            )
            
            db.add(price_record)
            logger.debug(f"Stored external price for {symbol} on {price_date}: ${price}")
            
        except Exception as e:
            logger.error(f"Error storing fetched price for {symbol}: {e}")
            
    def validate_position_price_coverage(self, start_date: date, end_date: date) -> Dict:
        """
        Validate that all positions have corresponding price data (AP-3).
        
        Returns:
            Dict with validation results and missing price information
        """
        with next(get_db()) as db:
            # Get all position/date combinations that need prices
            positions_query = (
                select(
                    PositionDaily.asset_id,
                    PositionDaily.date,
                    Asset.symbol,
                    PositionDaily.quantity
                )
                .join(Asset)
                .where(
                    and_(
                        PositionDaily.date >= start_date,
                        PositionDaily.date <= end_date,
                        PositionDaily.quantity != 0  # Only check non-zero positions
                    )
                )
                .distinct()
            )
            
            positions = db.execute(positions_query).all()
            
            # Check which ones have price data
            missing_prices = []
            covered_count = 0
            
            for asset_id, pos_date, symbol, quantity in positions:
                price_exists = db.execute(
                    select(PriceData.price_id)
                    .where(
                        and_(
                            PriceData.asset_id == asset_id,
                            PriceData.date == pos_date
                        )
                    )
                ).scalar_one_or_none()
                
                if price_exists:
                    covered_count += 1
                else:
                    missing_prices.append({
                        'asset_id': asset_id,
                        'symbol': symbol,
                        'date': pos_date,
                        'quantity': float(quantity)
                    })
                    
            total_positions = len(positions)
            coverage_percentage = (covered_count / total_positions * 100) if total_positions > 0 else 100
            
            return {
                'total_positions': total_positions,
                'covered_positions': covered_count,
                'missing_positions': len(missing_prices),
                'coverage_percentage': coverage_percentage,
                'missing_prices': missing_prices,
                'is_complete': len(missing_prices) == 0
            }
            
    def get_price_range(self, asset: str, start_date: Union[date, datetime], 
                       end_date: Union[date, datetime]) -> pd.DataFrame:
        """Get daily closing prices for an asset over a date range."""
        if isinstance(start_date, datetime):
            start_date = start_date.date()
        if isinstance(end_date, datetime):
            end_date = end_date.date()
            
        with next(get_db()) as db:
            query = (
                select(PriceData.date, PriceData.close)
                .join(Asset)
                .where(
                    and_(
                        Asset.symbol == self._normalize_asset(asset).replace("/", ""),
                        PriceData.date.between(start_date, end_date)
                    )
                )
                .order_by(PriceData.date)
            )
            result = db.execute(query).all()
            
            if result:
                df = pd.DataFrame(result, columns=['date', self._normalize_asset(asset)])
                df['date'] = pd.to_datetime(df['date'])
                df = df.set_index('date')
                return df
            return pd.DataFrame()
            
    def get_multi_asset_prices(self, symbols: List[str], start_date: Optional[datetime] = None, 
                              end_date: Optional[datetime] = None) -> pd.DataFrame:
        """Get historical prices for multiple assets."""
        # Clean and normalize symbols
        cleaned_symbols = []
        symbol_mapping = {}  # Keep track of original to normalized mapping
        for symbol in symbols:
            # Remove any trailing /USD and clean the symbol
            clean_symbol = self._normalize_asset(symbol.split('/')[0])
            cleaned_symbols.append(clean_symbol)
            symbol_mapping[clean_symbol] = symbol  # Store mapping
        
        if not cleaned_symbols:
            return pd.DataFrame(columns=['date', 'symbol', 'price'])
        
        # Handle stablecoins
        prices_list = []
        for normalized_symbol in cleaned_symbols:
            if normalized_symbol in self.stablecoins:
                # Create a date range for the stablecoin
                if start_date and end_date:
                    date_range = pd.date_range(start=start_date, end=end_date, freq='D')
                else:
                    # Default to last 30 days if no dates specified
                    end_date = datetime.now()
                    start_date = end_date - timedelta(days=30)
                    date_range = pd.date_range(start=start_date, end=end_date, freq='D')
                
                # Create a DataFrame with price of 1 for all dates
                stablecoin_prices = pd.DataFrame({
                    'date': date_range,
                    'symbol': symbol_mapping.get(normalized_symbol, normalized_symbol),
                    'price': 1.0
                })
                prices_list.append(stablecoin_prices)
            else:
                with next(get_db()) as db:
                    query = (
                        select(
                            PriceData.date,
                            func.literal(symbol_mapping.get(normalized_symbol, normalized_symbol)).label('symbol'),
                            PriceData.close.label('price'),
                            PriceData.confidence_score
                        )
                        .join(Asset)
                        .where(Asset.symbol == normalized_symbol)
                    )
                    
                    if start_date:
                        query = query.where(PriceData.date >= start_date if isinstance(start_date, date) else start_date.date())
                    if end_date:
                        query = query.where(PriceData.date <= end_date if isinstance(end_date, date) else end_date.date())
                    
                    query = query.order_by(PriceData.date, PriceData.confidence_score.desc())
                    
                    result = db.execute(query).all()
                    if result:
                        df = pd.DataFrame(result)
                        df['date'] = pd.to_datetime(df['date'])
                        # Take the price with highest confidence score for each date
                        df = df.sort_values('confidence_score', ascending=False).groupby(['date', 'symbol']).first().reset_index()
                        df = df.drop('confidence_score', axis=1)
                        prices_list.append(df)
                    else:
                        # Check if the asset exists in the database
                        asset_exists = db.execute(
                            select(Asset).where(Asset.symbol == normalized_symbol)
                        ).first() is not None
                        
                        if not asset_exists:
                            print(f"Debug: Asset {normalized_symbol} not found in database")
                        else:
                            print(f"Debug: No price data found for {normalized_symbol} in the specified date range")
        
        if not prices_list:
            return pd.DataFrame(columns=['date', 'symbol', 'price'])
        
        # Combine all price data
        result = pd.concat(prices_list, ignore_index=True)
        
        # Drop duplicates, keeping the first occurrence (which has the highest confidence score)
        result = result.drop_duplicates(subset=['date', 'symbol'], keep='first')
        
        return result
    
    def get_source_priority(self, asset: str) -> List[str]:
        """Get the priority order of data sources for an asset."""
        with next(get_db()) as db:
            query = (
                select(DataSource.name)
                .join(PriceData)
                .join(Asset)
                .where(Asset.symbol == self._normalize_asset(asset))
                .distinct()
                .order_by(DataSource.priority.desc())
            )
            result = db.execute(query).scalars().all()
            return list(result)
            
    def get_asset_coverage(self) -> Dict[str, Dict]:
        """Get coverage information for all assets."""
        with next(get_db()) as db:
            query = (
                select(
                    Asset.symbol,
                    func.min(PriceData.date).label('first_date'),
                    func.max(PriceData.date).label('last_date'),
                    func.count(PriceData.price_id).label('data_points')
                )
                .join(PriceData)
                .group_by(Asset.symbol)
            )
            result = db.execute(query).all()
            
            coverage = {}
            for row in result:
                coverage[row.symbol] = {
                    'first_date': row.first_date,
                    'last_date': row.last_date,
                    'data_points': row.data_points
                }
            return coverage
            
    def validate_price_data(self, asset: str, start_date: Union[date, datetime],
                          end_date: Union[date, datetime]) -> Dict:
        """Validate price data coverage for an asset."""
        if isinstance(start_date, datetime):
            start_date = start_date.date()
        if isinstance(end_date, datetime):
            end_date = end_date.date()
            
        with next(get_db()) as db:
            # Get total days in range
            total_days = (end_date - start_date).days + 1
            
            # Get actual data points
            query = (
                select(func.count(PriceData.price_id))
                .join(Asset)
                .where(
                    and_(
                        Asset.symbol == self._normalize_asset(asset),
                        PriceData.date.between(start_date, end_date)
                    )
                )
            )
            data_points = db.execute(query).scalar_one()
            
            # Get missing dates
            query = (
                select(PriceData.date)
                .join(Asset)
                .where(
                    and_(
                        Asset.symbol == self._normalize_asset(asset),
                        PriceData.date.between(start_date, end_date)
                    )
                )
            )
            existing_dates = {row.date for row in db.execute(query)}
            all_dates = {start_date + timedelta(days=x) for x in range(total_days)}
            missing_dates = sorted(all_dates - existing_dates)
            
            return {
                'total_days': total_days,
                'data_points': data_points,
                'coverage_percentage': (data_points / total_days) * 100 if total_days > 0 else 0,
                'missing_dates': missing_dates
            } 