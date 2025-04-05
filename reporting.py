import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from price_service import price_service

class PortfolioReporting:
    def __init__(self, transactions: pd.DataFrame):
        """Initialize with transaction data"""
        self.transactions = transactions.sort_values("timestamp").copy()
        self.transactions["date"] = self.transactions["timestamp"].dt.tz_localize(None).dt.floor("D")
        
    def _calculate_daily_holdings(self, start_date: Optional[datetime] = None,
                                end_date: Optional[datetime] = None) -> pd.DataFrame:
        """Calculate daily holdings for each asset"""
        if start_date is None:
            start_date = self.transactions["timestamp"].min()
        if end_date is None:
            end_date = self.transactions["timestamp"].max()
            
        # Ensure dates are timezone-naive
        if pd.api.types.is_datetime64tz_dtype(pd.Series([start_date])):
            start_date = start_date.replace(tzinfo=None)
        if pd.api.types.is_datetime64tz_dtype(pd.Series([end_date])):
            end_date = end_date.replace(tzinfo=None)
            
        # Create date range
        date_range = pd.date_range(start=start_date, end=end_date, freq="D")
        
        # Ensure transaction timestamps are timezone-naive
        transactions = self.transactions.copy()
        transactions["timestamp"] = transactions["timestamp"].dt.tz_localize(None)
            
        # Calculate daily holdings
        transactions["date"] = transactions["timestamp"].dt.floor("D")
        daily_holdings = transactions.groupby(["date", "asset"])["quantity"].sum().unstack(fill_value=0)
        return daily_holdings.reindex(date_range, method="ffill").fillna(0)
        
    def calculate_portfolio_value(self, holdings=None, prices=None, start_date=None, end_date=None):
        """Calculate portfolio value time series.
        
        Args:
            holdings: Optional pre-calculated holdings DataFrame. If not provided, will be calculated from start_date/end_date
            prices: Optional pre-fetched prices DataFrame. If not provided, will be fetched from start_date/end_date
            start_date: Optional start date for calculating holdings and fetching prices
            end_date: Optional end date for calculating holdings and fetching prices
        """
        # If holdings not provided, calculate from dates
        if holdings is None:
            holdings = self._calculate_daily_holdings(start_date, end_date)
        
        # If prices not provided, fetch them
        if prices is None:
            assets = [col for col in holdings.columns if col != "portfolio_value"]
            # Ensure we're using timezone-naive dates for price lookup
            price_start = holdings.index[0].tz_localize(None) if holdings.index[0].tzinfo else holdings.index[0]
            price_end = holdings.index[-1].tz_localize(None) if holdings.index[-1].tzinfo else holdings.index[-1]
            prices = price_service.get_multi_asset_prices(assets, price_start, price_end)
            
        print(f"Debug: Holdings shape: {holdings.shape}")
        print(f"Debug: Holdings columns: {holdings.columns}")
        print(f"Debug: Sample holdings:\n{holdings.head()}")
        
        print(f"Debug: Prices shape: {prices.shape}")
        print(f"Debug: Prices columns: {prices.columns}")
        print(f"Debug: Sample prices:\n{prices.head()}")
        
        # Debug print for BTC holdings
        if 'BTC' in holdings.columns:
            print("\nDebug: BTC holdings:")
            btc_holdings = holdings['BTC'][holdings['BTC'] != 0]
            print(btc_holdings.head(10))
            print("\nDebug: BTC holdings date range:")
            print("Start:", holdings.index[0])
            print("End:", holdings.index[-1])

        # Convert holdings index to date only (no time component)
        holdings.index = pd.to_datetime(holdings.index).date
        holdings.index.name = 'date'
        
        # Calculate value for each asset
        portfolio_values = pd.DataFrame(index=holdings.index)
        
        for asset in holdings.columns:
            # Skip portfolio_value column if it exists
            if asset == 'portfolio_value':
                continue
                
            # Handle stablecoins
            if asset in {'USD', 'USDC', 'USDT', 'DAI'}:
                portfolio_values[f"{asset}_value"] = holdings[asset]
                continue
                
            # Get asset prices
            asset_prices = prices[prices['symbol'] == asset]
            if asset_prices.empty:
                print(f"Debug: No prices found for {asset}")
                if holdings[asset].any():  # If there are any non-zero holdings
                    print("  Non-zero holdings:", holdings[asset][holdings[asset] != 0])
                continue
            
            # Debug print for BTC prices
            if asset == 'BTC':
                print("\nDebug: BTC prices:")
                print(asset_prices.head(10))
                print("\nDebug: BTC prices date range:")
                print("Start:", asset_prices['date'].min())
                print("End:", asset_prices['date'].max())
            
            # Convert price dates to date type for matching
            asset_prices['date'] = pd.to_datetime(asset_prices['date']).dt.date
            asset_prices = asset_prices.set_index('date')['price']
            
            # Get holdings and prices for this asset
            asset_holdings = holdings[asset]
            
            # Align dates between holdings and prices
            common_dates = asset_holdings.index.intersection(asset_prices.index)
            if len(common_dates) == 0:
                print(f"Debug: No overlapping dates for {asset}")
                continue
                
            # Calculate value only for overlapping dates
            asset_value = pd.Series(0.0, index=holdings.index)
            asset_value[common_dates] = asset_holdings[common_dates] * asset_prices[common_dates]
            portfolio_values[f"{asset}_value"] = asset_value
            
            print(f"Debug: {asset} value calculation:")
            print("  Holdings:", asset_holdings[common_dates].head())
            print("  Prices:", asset_prices[common_dates].head())
            print("  Values:", asset_value[common_dates].head())
        
        # Calculate total portfolio value
        print("Debug: Portfolio value calculation:")
        print("  Value columns:", list(portfolio_values.columns))
        portfolio_values['portfolio_value'] = portfolio_values.sum(axis=1)
        print("  Sample portfolio values:")
        print(portfolio_values['portfolio_value'].head())
        
        print("Debug: Portfolio value shape:", portfolio_values.shape)
        print("Debug: Portfolio value columns:", portfolio_values.columns)
        
        # Print initial and final values
        initial_value = portfolio_values['portfolio_value'].iloc[0]
        final_value = portfolio_values['portfolio_value'].iloc[-1]
        print("Debug: Initial value:", initial_value)
        print("Debug: Final value:", final_value)
        
        if initial_value == 0:
            print("Debug: Initial value is zero")
        
        return portfolio_values
        
    def calculate_tax_lots(self, method: str = "fifo") -> pd.DataFrame:
        """Calculate tax lots using specified method (fifo, lifo, or avg)"""
        lots = []
        open_lots = {}
        
        for _, tx in self.transactions.iterrows():
            asset = tx["asset"]
            if asset not in open_lots:
                open_lots[asset] = []
                
            if tx["type"] == "buy":
                # Add new lot
                lot = {
                    "asset": asset,
                    "quantity": tx["quantity"],
                    "price": tx["price"],
                    "date_acquired": tx["timestamp"],
                    "fees": tx["fees"] if "fees" in tx else 0,
                    "source": tx["source_account"] if "source_account" in tx else None,
                    "transaction_id": tx["transaction_id"]
                }
                if method == "lifo":
                    open_lots[asset].insert(0, lot)
                else:  # fifo or avg
                    open_lots[asset].append(lot)
                    
            elif tx["type"] == "sell":
                remaining_quantity = tx["quantity"]
                realized_gains = []
                
                while remaining_quantity > 0 and open_lots[asset]:
                    lot = open_lots[asset][0]
                    used_quantity = min(remaining_quantity, lot["quantity"])
                    
                    # Calculate gain/loss
                    proceeds = used_quantity * tx["price"]
                    cost_basis = used_quantity * lot["price"]
                    gain_loss = proceeds - cost_basis
                    
                    # Record realized gain/loss
                    realized_gains.append({
                        "asset": asset,
                        "quantity": used_quantity,
                        "acquisition_date": lot["date_acquired"],
                        "disposal_date": tx["timestamp"],
                        "acquisition_price": lot["price"],
                        "disposal_price": tx["price"],
                        "cost_basis": cost_basis,
                        "proceeds": proceeds,
                        "gain_loss": gain_loss,
                        "holding_period_days": (tx["timestamp"] - lot["date_acquired"]).days,
                        "transaction_id": tx["transaction_id"],
                        "lot_transaction_id": lot["transaction_id"]
                    })
                    
                    # Update or remove lot
                    if used_quantity == lot["quantity"]:
                        open_lots[asset].pop(0)
                    else:
                        lot["quantity"] -= used_quantity
                        
                    remaining_quantity -= used_quantity
                    
                lots.extend(realized_gains)
                
        return pd.DataFrame(lots)
        
    def calculate_performance_metrics(self, initial_date: Optional[datetime] = None) -> Dict:
        """Calculate performance metrics from initial date to today"""
        # Get portfolio value time series
        end_date = datetime.now().replace(tzinfo=None)  # Make timezone-naive
        if initial_date is None:
            initial_date = self.transactions["date"].min()
        
        # Convert dates to Timestamps for consistent comparison
        initial_date = pd.Timestamp(initial_date)
        end_date = pd.Timestamp(end_date)
        
        # Calculate portfolio value
        portfolio_value = self.calculate_portfolio_value(
            self._calculate_daily_holdings(initial_date),
            price_service.get_multi_asset_prices(self._calculate_daily_holdings(initial_date).columns, initial_date, end_date)
        )
        
        # Get initial and final values
        initial_value = portfolio_value["portfolio_value"].iloc[0]
        final_value = portfolio_value["portfolio_value"].iloc[-1]
        
        print(f"Debug: Initial value: {initial_value}")
        print(f"Debug: Final value: {final_value}")
        
        # Calculate metrics
        if initial_value == 0:
            print("Debug: Initial value is zero")
            total_return = 0
            annualized_return = 0
            volatility = 0
            sharpe_ratio = 0
            max_drawdown = 0
        else:
            total_return = (final_value - initial_value) / initial_value
            # Calculate years between initial investment and end
            years = (end_date - initial_date).days / 365.25
            annualized_return = (1 + total_return) ** (1/years) - 1 if years > 0 else 0
            
            # Calculate daily returns only for the period with non-zero values
            daily_values = portfolio_value["portfolio_value"]
            daily_returns = daily_values.pct_change().fillna(0)
            
            # Calculate volatility (annualized)
            volatility = daily_returns.std() * np.sqrt(252)
            
            # Calculate Sharpe ratio (assuming risk-free rate of 0.02)
            risk_free_rate = 0.02
            excess_returns = daily_returns - risk_free_rate/252
            sharpe_ratio = np.sqrt(252) * excess_returns.mean() / daily_returns.std() if daily_returns.std() != 0 else 0
            
            # Calculate maximum drawdown
            cumulative_returns = (1 + daily_returns).cumprod()
            rolling_max = cumulative_returns.expanding().max()
            drawdowns = cumulative_returns/rolling_max - 1
            max_drawdown = drawdowns.min()
            print(f"Debug: Max drawdown: {max_drawdown*100:.2f}%")
        
        return {
            "total_return": total_return,
            "annualized_return": annualized_return,
            "volatility": volatility,
            "sharpe_ratio": sharpe_ratio,
            "max_drawdown": max_drawdown
        }
        
    def generate_tax_report(self, year: int) -> Tuple[pd.DataFrame, Dict]:
        """Generate tax report for specified year"""
        # Calculate tax lots
        tax_lots = self.calculate_tax_lots()
        
        # Filter for disposals in the specified year
        year_start = pd.Timestamp(f"{year}-01-01")
        year_end = pd.Timestamp(f"{year}-12-31")
        year_lots = tax_lots[
            (tax_lots["disposal_date"].dt.tz_localize(None) >= year_start) & 
            (tax_lots["disposal_date"].dt.tz_localize(None) <= year_end)
        ]
        
        # Calculate summary statistics
        summary = {
            "total_proceeds": year_lots["proceeds"].sum(),
            "total_cost_basis": year_lots["cost_basis"].sum(),
            "total_gain_loss": year_lots["gain_loss"].sum(),
            "short_term_gain_loss": year_lots[year_lots["holding_period_days"] <= 365]["gain_loss"].sum(),
            "long_term_gain_loss": year_lots[year_lots["holding_period_days"] > 365]["gain_loss"].sum(),
            "total_transactions": len(year_lots)
        }
        
        return year_lots, summary
        
    def generate_performance_report(self, period: str = "YTD") -> Dict:
        """Generate performance report for specified period"""
        today = pd.Timestamp.now().normalize()  # Make timezone-naive and normalize to midnight
        
        if period == "YTD":
            start_date = pd.Timestamp(f"{today.year}-01-01")
        elif period == "1Y":
            start_date = today - pd.Timedelta(days=365)
        elif period == "3Y":
            start_date = today - pd.Timedelta(days=365 * 3)
        elif period == "5Y":
            start_date = today - pd.Timedelta(days=365 * 5)
        else:
            start_date = None
            
        # Calculate performance metrics
        metrics = self.calculate_performance_metrics(start_date)
        
        # Get asset allocation
        holdings = self._calculate_daily_holdings(start_date)
        prices = price_service.get_multi_asset_prices(holdings.columns, start_date, today)
        portfolio_value = self.calculate_portfolio_value(holdings, prices)
        
        latest_values = {col.replace("_value", ""): val 
                        for col, val in portfolio_value.iloc[-1].items()
                        if col != "portfolio_value" and not pd.isna(val)}
        total_value = sum(latest_values.values())
        
        # Handle empty or zero portfolio value
        if total_value == 0:
            allocation = {asset: 0.0 for asset in latest_values.keys()}
        else:
            allocation = {asset: (value / total_value * 100) 
                         for asset, value in latest_values.items()}
        
        report = {
            "period": period,
            "start_date": start_date,
            "end_date": today,
            "metrics": metrics,
            "current_allocation": allocation,
            "total_value": total_value
        }
        
        return report 