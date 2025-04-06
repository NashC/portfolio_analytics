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
        
        # Ensure quantity is numeric
        transactions["quantity"] = pd.to_numeric(transactions["quantity"], errors='coerce')
            
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
        """Calculate tax lots for each asset using specified method (fifo, lifo, or average)."""
        # Ensure quantity is numeric
        self.transactions["quantity"] = pd.to_numeric(self.transactions["quantity"], errors='coerce')
        self.transactions["price"] = pd.to_numeric(self.transactions["price"], errors='coerce')
        self.transactions["subtotal"] = pd.to_numeric(self.transactions["subtotal"], errors='coerce')
        self.transactions["total"] = pd.to_numeric(self.transactions["total"], errors='coerce')
        self.transactions["fees"] = pd.to_numeric(self.transactions["fees"], errors='coerce')
        
        # Initialize lists to store tax lots
        tax_lots = []
        open_lots = {}  # Dictionary to track open lots for each asset
        realized_gains = []  # List to store realized gains/losses
        
        # Sort transactions by timestamp
        transactions = self.transactions.sort_values("timestamp")
        
        for _, tx in transactions.iterrows():
            try:
                if tx["type"] == "buy":
                    # Add new lot
                    if tx["asset"] not in open_lots:
                        open_lots[tx["asset"]] = []
                    
                    # Calculate total cost including fees
                    quantity = float(abs(tx["quantity"]))
                    fees = float(tx["fees"]) if pd.notna(tx["fees"]) else 0.0
                    # Total cost is (price * quantity) + fees
                    total_cost = (float(tx["price"]) * quantity) + fees
                    # Cost basis per unit includes the fees
                    cost_basis_per_unit = total_cost / quantity if quantity > 0 else 0
                    
                    open_lots[tx["asset"]].append({
                        "acquisition_date": tx["timestamp"],
                        "quantity": quantity,
                        "cost_basis_per_unit": cost_basis_per_unit,
                        "fees": fees,
                        "acquisition_type": "buy"
                    })
                
                elif tx["type"] == "staking_reward":
                    # Handle staking rewards like a buy transaction
                    if tx["asset"] not in open_lots:
                        open_lots[tx["asset"]] = []
                    
                    # For staking rewards:
                    # - quantity is the amount received
                    # - cost basis is the fair market value at time of receipt
                    # - no fees typically associated with rewards
                    quantity = float(abs(tx["quantity"]))
                    price = float(tx["price"]) if pd.notna(tx["price"]) else 0.0
                    cost_basis_per_unit = price  # FMV at time of receipt
                    
                    open_lots[tx["asset"]].append({
                        "acquisition_date": tx["timestamp"],
                        "quantity": quantity,
                        "cost_basis_per_unit": cost_basis_per_unit,
                        "fees": 0.0,  # No fees for staking rewards
                        "acquisition_type": "staking_reward"
                    })
                
                elif tx["type"] == "sell":
                    # Get open lots for this asset
                    if tx["asset"] not in open_lots or not open_lots[tx["asset"]]:
                        print(f"Warning: No open lots found for {tx['asset']} at {tx['timestamp']}")
                        continue
                        
                    # Calculate proceeds and net proceeds
                    sell_quantity = float(abs(tx["quantity"]))
                    sell_fees = float(tx["fees"]) if pd.notna(tx["fees"]) else 0.0
                    sell_fees = abs(sell_fees)  # Ensure fees are positive
                    # Calculate net proceeds as subtotal minus fees
                    subtotal = float(tx["subtotal"])
                    net_proceeds = subtotal - sell_fees
                    proceeds_per_unit = subtotal / sell_quantity if sell_quantity > 0 else 0
                    
                    remaining_quantity = sell_quantity
                    
                    # Process lots based on method
                    while remaining_quantity > 0 and open_lots[tx["asset"]]:
                        if method == "fifo":
                            lot = open_lots[tx["asset"]].pop(0)  # First in, first out
                        elif method == "lifo":
                            lot = open_lots[tx["asset"]].pop()  # Last in, first out
                        else:  # average
                            # For average cost basis, we'll use the weighted average of all lots
                            total_quantity = sum(float(lot["quantity"]) for lot in open_lots[tx["asset"]])
                            total_cost = sum(float(lot["quantity"]) * float(lot["cost_basis_per_unit"]) for lot in open_lots[tx["asset"]])
                            avg_cost = total_cost / total_quantity if total_quantity > 0 else 0
                            lot = {
                                "acquisition_date": open_lots[tx["asset"]][0]["acquisition_date"],
                                "quantity": total_quantity,
                                "cost_basis_per_unit": avg_cost,
                                "fees": sum(float(lot["fees"]) for lot in open_lots[tx["asset"]]),
                                "acquisition_type": "average"
                            }
                            open_lots[tx["asset"]] = []  # Clear all lots
                        
                        # Calculate how much of this lot to use
                        lot_quantity = min(float(lot["quantity"]), remaining_quantity)
                        remaining_quantity -= lot_quantity
                        
                        # Calculate portion of proceeds to attribute to this lot
                        lot_proceeds = (lot_quantity / sell_quantity) * subtotal
                        lot_fees = (lot_quantity / sell_quantity) * sell_fees
                        lot_net_proceeds = lot_proceeds - lot_fees
                        
                        # Calculate gain/loss for this portion
                        lot_cost_basis = lot_quantity * float(lot["cost_basis_per_unit"])
                        gain_loss = lot_net_proceeds - lot_cost_basis
                        
                        # Calculate holding period in days
                        holding_period_days = (tx["timestamp"] - lot["acquisition_date"]).days
                        
                        # Record the realized gain/loss
                        realized_gains.append({
                            "asset": tx["asset"],
                            "quantity": lot_quantity,
                            "acquisition_date": lot["acquisition_date"],
                            "disposal_date": tx["timestamp"],
                            "cost_basis": lot_cost_basis,
                            "proceeds": lot_proceeds,
                            "fees": lot_fees,
                            "gain_loss": gain_loss,
                            "holding_period_days": holding_period_days,
                            "acquisition_type": lot["acquisition_type"]  # Track whether this came from a buy or staking reward
                        })
                        
                        # If we didn't use the entire lot, put the remainder back
                        if lot_quantity < float(lot["quantity"]):
                            lot["quantity"] -= lot_quantity
                            if method == "fifo":
                                open_lots[tx["asset"]].insert(0, lot)
                            elif method == "lifo":
                                open_lots[tx["asset"]].append(lot)
                            else:  # average
                                open_lots[tx["asset"]].append(lot)
            
            except Exception as e:
                print(f"Error processing transaction:")
                print(f"Transaction: {tx}")
                print(f"Error: {str(e)}")
                continue
        
        # Convert realized gains to DataFrame
        if realized_gains:
            tax_lots_df = pd.DataFrame(realized_gains)
            tax_lots_df = tax_lots_df.sort_values("disposal_date")
            return tax_lots_df
        else:
            return pd.DataFrame()  # Return empty DataFrame if no realized gains
        
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
        holdings = self._calculate_daily_holdings(initial_date)
        prices = price_service.get_multi_asset_prices(holdings.columns, initial_date, end_date)
        portfolio_value = self.calculate_portfolio_value(holdings, prices)
        
        # Get initial and final values
        initial_value = portfolio_value["portfolio_value"].iloc[0]
        final_value = portfolio_value["portfolio_value"].iloc[-1]
        
        print(f"Debug: Initial value: {initial_value}")
        print(f"Debug: Final value: {final_value}")
        
        # Calculate metrics
        if initial_value == 0 or final_value == 0:
            print("Debug: Initial or final value is zero")
            total_return = 0
            annualized_return = 0
            volatility = 0
            sharpe_ratio = 0
            max_drawdown = 0
        else:
            # Calculate total return
            total_return = (final_value - initial_value) / initial_value
            
            # Calculate years between initial investment and end
            years = (end_date - initial_date).days / 365.25
            if years <= 0:
                annualized_return = total_return
            else:
                annualized_return = (1 + total_return) ** (1/years) - 1
            
            # Cap unrealistic returns
            if annualized_return > 10:  # Cap at 1000% annualized return
                annualized_return = 10
                print("Debug: Capped unrealistic annualized return")
            
            # Calculate daily returns
            daily_values = portfolio_value["portfolio_value"]
            daily_returns = daily_values.pct_change().fillna(0)
            
            # Remove any extreme outliers that might skew calculations
            daily_returns = daily_returns.clip(-0.5, 0.5)  # Cap at 50% daily return
            
            # Calculate volatility (annualized)
            if len(daily_returns) > 1:
                # Use log returns for more stable volatility calculation
                log_returns = np.log1p(daily_returns)
                volatility = log_returns.std() * np.sqrt(252)
            else:
                volatility = 0
            
            # Calculate Sharpe ratio (assuming risk-free rate of 0.02)
            risk_free_rate = 0.02
            if volatility > 0:
                excess_returns = daily_returns - risk_free_rate/252
                sharpe_ratio = np.sqrt(252) * excess_returns.mean() / volatility
            else:
                sharpe_ratio = 0
            
            # Calculate maximum drawdown
            if len(daily_values) > 1:
                # Calculate cumulative returns using log returns for more stability
                log_returns = np.log1p(daily_returns)
                cumulative_returns = np.exp(log_returns.cumsum())
                # Calculate rolling maximum
                rolling_max = cumulative_returns.expanding().max()
                # Calculate drawdowns
                drawdowns = cumulative_returns/rolling_max - 1
                # Get maximum drawdown
                max_drawdown = drawdowns.min()
            else:
                max_drawdown = 0
            
            print(f"Debug: Max drawdown: {max_drawdown*100:.2f}%")
            print(f"Debug: Daily returns mean: {daily_returns.mean()*100:.2f}%")
            print(f"Debug: Daily returns std: {daily_returns.std()*100:.2f}%")
            print(f"Debug: Log returns std: {log_returns.std()*100:.2f}%")
        
        return {
            "total_return": total_return,
            "annualized_return": annualized_return,
            "volatility": volatility,
            "sharpe_ratio": sharpe_ratio,
            "max_drawdown": max_drawdown
        }
        
    def generate_tax_report(self, year: int) -> Tuple[pd.DataFrame, Dict]:
        """Generate tax report for specified year"""
        # Define stablecoins set
        stablecoins = {'USD', 'USDC', 'USDT', 'DAI'}
        
        # Calculate tax lots
        tax_lots = self.calculate_tax_lots()
        
        # Ensure numeric columns
        numeric_columns = ["quantity", "cost_basis", "proceeds", "fees", "gain_loss"]
        for col in numeric_columns:
            if col in tax_lots.columns:
                tax_lots[col] = pd.to_numeric(tax_lots[col], errors='coerce')
        
        # Filter for disposals in the specified year
        year_start = pd.Timestamp(f"{year}-01-01")
        year_end = pd.Timestamp(f"{year}-12-31")
        year_lots = tax_lots[
            (tax_lots["disposal_date"].dt.tz_localize(None) >= year_start) & 
            (tax_lots["disposal_date"].dt.tz_localize(None) <= year_end)
        ]
        
        # Get sell transactions for the year to calculate net proceeds
        sell_transactions = self.transactions[
            (self.transactions['timestamp'].dt.year == year) &
            (self.transactions['type'] == 'sell') &
            (~self.transactions['asset'].isin(stablecoins))  # Exclude stablecoins
        ].copy()
        
        # Calculate net proceeds from source transactions
        net_proceeds = 0.0
        if not sell_transactions.empty:
            # Convert numeric columns and ensure fees are positive
            sell_transactions['subtotal'] = pd.to_numeric(sell_transactions['subtotal'], errors='coerce').fillna(0)
            sell_transactions['fees'] = pd.to_numeric(sell_transactions['fees'], errors='coerce').fillna(0).abs()  # Make fees positive
            
            # Calculate net proceeds for each transaction and sum
            sell_transactions['net_proceeds'] = sell_transactions['subtotal'] - sell_transactions['fees']
            net_proceeds = sell_transactions['net_proceeds'].sum()
            
            # Debug print transactions
            print("\nDebug: Tax Report Sell Transactions:")
            for _, tx in sell_transactions.iterrows():
                print(f"{tx['asset']}: Date={tx['timestamp'].strftime('%Y-%m-%d')}, Subtotal=${tx['subtotal']:.2f}, Fees=${tx['fees']:.2f}, Net=${tx['net_proceeds']:.2f}")
            print(f"Total Net Proceeds: ${net_proceeds:.2f}")
        
        # Filter tax lots to exclude stablecoins
        year_lots = year_lots[~year_lots['asset'].isin(stablecoins)]
        
        # Calculate summary statistics
        summary = {
            "net_proceeds": float(net_proceeds),
            "total_cost_basis": float(year_lots["cost_basis"].sum()),
            "total_gain_loss": float(year_lots["gain_loss"].sum()),
            "short_term_gain_loss": float(year_lots[year_lots["holding_period_days"] <= 365]["gain_loss"].sum()),
            "long_term_gain_loss": float(year_lots[year_lots["holding_period_days"] > 365]["gain_loss"].sum()),
            "total_transactions": len(year_lots)
        }
        
        # Debug print
        print(f"\nDebug: Tax Report for {year}")
        print(f"Total lots: {len(year_lots)}")
        print(f"Net proceeds (excluding stablecoins): ${summary['net_proceeds']:,.2f}")
        print(f"Total cost basis: ${summary['total_cost_basis']:,.2f}")
        print(f"Total gain/loss: ${summary['total_gain_loss']:,.2f}")
        print(f"Short-term G/L: ${summary['short_term_gain_loss']:,.2f}")
        print(f"Long-term G/L: ${summary['long_term_gain_loss']:,.2f}")
        
        # Print sample of lots
        if not year_lots.empty:
            print("\nSample lots:")
            print(year_lots[["asset", "quantity", "acquisition_date", "disposal_date", "proceeds", "fees", "cost_basis", "gain_loss"]].head())
        
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

    def show_sell_transactions_with_lots(self, asset: str = None) -> pd.DataFrame:
        """Show sell transactions and their associated buy lots."""
        # Filter transactions for sells
        sells = self.transactions[self.transactions["type"] == "sell"].copy()
        if asset:
            sells = sells[sells["asset"] == asset]
            
        # Ensure numeric columns
        numeric_columns = ["quantity", "price", "subtotal", "total", "fees"]
        for col in numeric_columns:
            if col in sells.columns:
                sells[col] = pd.to_numeric(sells[col], errors='coerce')
        
        # Create sell details using direct source data
        sell_details = []
        for _, sell in sells.iterrows():
            try:
                # Use values directly from source data
                quantity = abs(float(sell["quantity"]))
                price = float(sell["price"])
                subtotal = float(sell["subtotal"])  # Use subtotal directly from source
                fees = float(sell["fees"]) if pd.notna(sell["fees"]) else 0.0
                fees = abs(fees)  # Ensure fees are positive
                net_proceeds = subtotal - fees  # Calculate net proceeds as subtotal minus fees
                
                sell_details.append({
                    "date": sell["timestamp"],
                    "type": sell["type"],
                    "asset": sell["asset"],
                    "quantity": quantity,
                    "price": price,
                    "subtotal": subtotal,
                    "fees": fees,
                    "net_proceeds": net_proceeds
                })
            
            except Exception as e:
                print(f"Error processing sell transaction:")
                print(f"Transaction: {sell}")
                print(f"Error: {str(e)}")
                continue
        
        # Convert to DataFrame
        if sell_details:
            sell_details_df = pd.DataFrame(sell_details)
            
            # Format numeric columns
            if not sell_details_df.empty:
                sell_details_df["quantity"] = sell_details_df["quantity"].round(8)  # Crypto quantities often need 8 decimals
                sell_details_df["price"] = sell_details_df["price"].round(4)  # Format price to 4 decimal places
                sell_details_df["subtotal"] = sell_details_df["subtotal"].round(2)
                sell_details_df["fees"] = sell_details_df["fees"].round(2)
                sell_details_df["net_proceeds"] = sell_details_df["net_proceeds"].round(2)
            
            return sell_details_df
        else:
            return pd.DataFrame()  # Return empty DataFrame if no sell details 