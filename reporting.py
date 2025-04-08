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
        """Calculate portfolio value time series."""
        if holdings is None:
            holdings = self._calculate_daily_holdings(start_date, end_date)
        
        if holdings.empty:
            return pd.DataFrame(columns=['portfolio_value'])
        
        # Remove non-asset columns like 'Amount'
        asset_columns = [col for col in holdings.columns if col not in ['Amount']]
        holdings = holdings[asset_columns].copy()
        
        # Initialize portfolio values DataFrame
        portfolio_values = pd.DataFrame(index=holdings.index)
        
        # Get prices for all assets if not provided
        if prices is None:
            prices = price_service.get_multi_asset_prices(holdings.columns, start_date, end_date)
        
        print("Debug: Holdings shape:", holdings.shape)
        print("Debug: Holdings columns:", holdings.columns)
        print("Debug: Sample holdings:")
        print(holdings.head())
        print("Debug: Prices shape:", prices.shape)
        print("Debug: Prices columns:", prices.columns)
        print("Debug: Sample prices:")
        print(prices.head())
        
        # Calculate value for each asset
        for asset in holdings.columns:
            # Get prices for this asset
            asset_prices = prices[prices['symbol'] == asset].copy()
            if asset_prices.empty:
                print(f"Debug: No prices found for {asset}")
                continue
            
            # Print debug info
            print(f"\nDebug: {asset} holdings:")
            print(holdings[asset].head(10))
            print(f"\nDebug: {asset} holdings date range:")
            print("Start:", holdings.index[0])
            print("End:", holdings.index[-1])
            
            print(f"\nDebug: {asset} prices:")
            print(asset_prices.head(10))
            print(f"\nDebug: {asset} prices date range:")
            print("Start:", asset_prices['date'].min())
            print("End:", asset_prices['date'].max())
            
            # Convert price dates to datetime for matching
            asset_prices['date'] = pd.to_datetime(asset_prices['date'])
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
        if not portfolio_values.empty:
            initial_value = portfolio_values['portfolio_value'].iloc[0]
            final_value = portfolio_values['portfolio_value'].iloc[-1]
            print("Debug: Initial value:", initial_value)
            print("Debug: Final value:", final_value)
            
            if initial_value == 0:
                print("Debug: Initial value is zero")
        
        return portfolio_values
        
    def calculate_tax_lots(self) -> pd.DataFrame:
        """Calculate tax lots for all assets."""
        # Define stablecoins set
        stablecoins = {'USD', 'USDC', 'USDT', 'DAI', 'BUSD', 'TUSD', 'USDP', 'USDD', 'FRAX', 'LUSD', 'SUSD', 'GUSD', 'HUSD', 'USDK', 'USDN', 'USDX', 'USDJ', 'USDH', 'USDX', 'USDY', 'USDZ', 'USDW', 'USDV', 'USDU', 'USDT', 'USDT.e', 'USDT.b', 'USDT.c', 'USDT.d', 'USDT.e', 'USDT.f', 'USDT.g', 'USDT.h', 'USDT.i', 'USDT.j', 'USDT.k', 'USDT.l', 'USDT.m', 'USDT.n', 'USDT.o', 'USDT.p', 'USDT.q', 'USDT.r', 'USDT.s', 'USDT.t', 'USDT.u', 'USDT.v', 'USDT.w', 'USDT.x', 'USDT.y', 'USDT.z'}
        
        # Filter out stablecoins and Amount column, ensure numeric columns
        transactions = self.transactions[
            (~self.transactions["asset"].isin(stablecoins)) & 
            (self.transactions["asset"] != "Amount")
        ].copy()
        
        # Ensure numeric columns
        numeric_columns = ["quantity", "price", "fees"]
        for col in numeric_columns:
            if col in transactions.columns:
                transactions[col] = pd.to_numeric(transactions[col], errors='coerce')
        
        # Calculate subtotal if not present
        if 'subtotal' not in transactions.columns:
            transactions['subtotal'] = transactions['quantity'] * transactions['price']
        else:
            transactions['subtotal'] = pd.to_numeric(transactions['subtotal'], errors='coerce')
        
        # Create tax lots
        lots = []
        for asset in transactions["asset"].unique():
            asset_txs = transactions[transactions["asset"] == asset].copy()
            asset_txs = asset_txs.sort_values("timestamp")
            
            # Track acquisitions (buys, transfer_in, staking_rewards) and disposals (sells, transfer_out)
            acquisitions = asset_txs[
                asset_txs["type"].isin(["buy", "transfer_in", "staking_reward"])
            ].copy()
            
            disposals = asset_txs[
                asset_txs["type"].isin(["sell", "transfer_out"])
            ].copy()
            
            # Process each disposal transaction
            for _, disposal in disposals.iterrows():
                disposal_quantity = abs(float(disposal["quantity"]))
                disposal_price = abs(float(disposal["price"])) if pd.notna(disposal["price"]) else 0.0
                
                # Use source subtotal if available, otherwise calculate
                if "subtotal" in disposal and pd.notna(disposal["subtotal"]):
                    disposal_subtotal = abs(float(disposal["subtotal"]))
                else:
                    disposal_subtotal = disposal_quantity * disposal_price
                
                # Use source net proceeds if available, otherwise calculate
                if "net_proceeds" in disposal and pd.notna(disposal["net_proceeds"]):
                    disposal_proceeds = abs(float(disposal["net_proceeds"]))
                else:
                    disposal_fees = abs(float(disposal["fees"])) if pd.notna(disposal["fees"]) else 0.0
                    disposal_proceeds = disposal_subtotal - disposal_fees
                
                # Find matching acquisition lots
                remaining_quantity = disposal_quantity
                acquisition_lots = acquisitions[acquisitions["timestamp"] <= disposal["timestamp"]].copy()
                
                while remaining_quantity > 0 and not acquisition_lots.empty:
                    acquisition = acquisition_lots.iloc[0]
                    acquisition_quantity = abs(float(acquisition["quantity"]))
                    
                    # Handle cost basis based on transaction type
                    if acquisition["type"] == "staking_reward":
                        # Staking rewards have zero cost basis
                        acquisition_price = 0.0
                        acquisition_subtotal = 0.0
                        acquisition_fees = 0.0
                        acquisition_cost_basis = 0.0
                    else:
                        # Get acquisition price first
                        acquisition_price = abs(float(acquisition["price"])) if pd.notna(acquisition["price"]) else 0.0
                        
                        # Use source subtotal if available, otherwise calculate
                        if "subtotal" in acquisition and pd.notna(acquisition["subtotal"]):
                            acquisition_subtotal = abs(float(acquisition["subtotal"]))
                        else:
                            acquisition_subtotal = acquisition_quantity * acquisition_price
                        
                        acquisition_fees = abs(float(acquisition["fees"])) if pd.notna(acquisition["fees"]) else 0.0
                        acquisition_cost_basis = acquisition_subtotal + acquisition_fees
                    
                    # Calculate cost basis per unit
                    cost_basis_per_unit = acquisition_cost_basis / acquisition_quantity if acquisition_quantity > 0 else 0.0
                    
                    # Determine how much of this lot to use
                    lot_quantity = min(remaining_quantity, acquisition_quantity)
                    lot_cost_basis = lot_quantity * cost_basis_per_unit
                    
                    # Use the actual proceeds from the disposal transaction
                    if lot_quantity == disposal_quantity:
                        # If we're using the entire disposal quantity, use the actual proceeds
                        lot_proceeds = disposal_proceeds
                        lot_fees = disposal_fees
                    else:
                        # If we're using a partial lot, calculate proportionally
                        lot_proceeds = (lot_quantity / disposal_quantity) * disposal_proceeds
                        lot_fees = (lot_quantity / disposal_quantity) * disposal_fees
                    
                    # Calculate gain/loss matching the net profit calculation
                    # lot_proceeds already has fees subtracted, so we don't subtract them again
                    gain_loss = lot_proceeds - lot_cost_basis
                    
                    # Add lot to list
                    lots.append({
                        "asset": asset,
                        "quantity": lot_quantity,
                        "acquisition_date": acquisition["timestamp"].date(),
                        "disposal_date": disposal["timestamp"].date(),
                        "acquisition_type": acquisition["type"],
                        "disposal_type": disposal["type"],
                        "acquisition_exchange": acquisition["institution"] if "institution" in acquisition else "",
                        "disposal_exchange": disposal["institution"] if "institution" in disposal else "",
                        "cost_basis": lot_cost_basis,
                        "fees": lot_fees,
                        "proceeds": lot_proceeds,
                        "gain_loss": gain_loss,
                        "holding_period_days": (disposal["timestamp"] - acquisition["timestamp"]).days
                    })
                    
                    # Update remaining quantity and remove used acquisition lot
                    remaining_quantity -= lot_quantity
                    if lot_quantity == acquisition_quantity:
                        acquisition_lots = acquisition_lots.iloc[1:]
                    else:
                        # Update the first row's values
                        acquisition_lots.iloc[0, acquisition_lots.columns.get_loc("quantity")] = acquisition_quantity - lot_quantity
                        acquisition_lots.iloc[0, acquisition_lots.columns.get_loc("subtotal")] = (acquisition_quantity - lot_quantity) * acquisition_price
                        acquisition_lots.iloc[0, acquisition_lots.columns.get_loc("fees")] = ((acquisition_quantity - lot_quantity) / acquisition_quantity) * acquisition_fees
        
        # Convert to DataFrame and sort by disposal date
        if lots:
            df = pd.DataFrame(lots)
            # Convert dates to string format
            df["acquisition_date"] = df["acquisition_date"].astype(str)
            df["disposal_date"] = df["disposal_date"].astype(str)
            df = df.sort_values("disposal_date", ascending=False)
            return df
        else:
            return pd.DataFrame()
        
    def calculate_performance_metrics(self, initial_date: Optional[datetime] = None) -> Dict:
        """Calculate performance metrics from initial date to today"""
        # Get portfolio value time series
        end_date = datetime.now().replace(tzinfo=None)  # Make timezone-naive
        
        # Calculate holdings and get prices
        holdings = self._calculate_daily_holdings(initial_date, end_date)
        if holdings.empty:
            return {
                'initial_value': 0.0,
                'final_value': 0.0,
                'total_return': 0.0,
                'annualized_return': 0.0,
                'volatility': 0.0,
                'sharpe_ratio': 0.0,
                'max_drawdown': 0.0,
                'best_day': {'date': None, 'return': 0.0},
                'worst_day': {'date': None, 'return': 0.0}
            }
        
        # Get prices for all assets
        assets = [col for col in holdings.columns if col not in ['Amount']]
        prices = price_service.get_multi_asset_prices(assets, initial_date, end_date)
        
        # Calculate portfolio value
        portfolio_values = self.calculate_portfolio_value(holdings, prices)
        if portfolio_values.empty or 'portfolio_value' not in portfolio_values.columns:
            return {
                'initial_value': 0.0,
                'final_value': 0.0,
                'total_return': 0.0,
                'annualized_return': 0.0,
                'volatility': 0.0,
                'sharpe_ratio': 0.0,
                'max_drawdown': 0.0,
                'best_day': {'date': None, 'return': 0.0},
                'worst_day': {'date': None, 'return': 0.0}
            }
        
        # Get non-zero portfolio values
        non_zero_values = portfolio_values[portfolio_values['portfolio_value'] > 0].copy()
        if non_zero_values.empty:
            return {
                'initial_value': 0.0,
                'final_value': 0.0,
                'total_return': 0.0,
                'annualized_return': 0.0,
                'volatility': 0.0,
                'sharpe_ratio': 0.0,
                'max_drawdown': 0.0,
                'best_day': {'date': None, 'return': 0.0},
                'worst_day': {'date': None, 'return': 0.0}
            }
        
        # Calculate daily returns using non-zero values
        daily_returns = non_zero_values['portfolio_value'].pct_change().fillna(0)
        
        # Calculate metrics
        initial_value = non_zero_values['portfolio_value'].iloc[0]
        final_value = non_zero_values['portfolio_value'].iloc[-1]
        total_return = (final_value - initial_value) / initial_value if initial_value > 0 else 0.0
        
        # Calculate annualized return
        days = (non_zero_values.index[-1] - non_zero_values.index[0]).days
        annualized_return = ((1 + total_return) ** (365.25 / days) - 1) if days > 0 and initial_value > 0 else 0.0
        
        # Calculate volatility (annualized)
        volatility = daily_returns.std() * np.sqrt(252) if len(daily_returns) > 1 else 0.0
        
        # Calculate Sharpe ratio (assuming risk-free rate of 0.02)
        risk_free_rate = 0.02
        sharpe_ratio = (annualized_return - risk_free_rate) / volatility if volatility > 0 else 0.0
        
        # Calculate maximum drawdown
        rolling_max = non_zero_values['portfolio_value'].expanding().max()
        drawdowns = non_zero_values['portfolio_value'] / rolling_max - 1
        max_drawdown = abs(drawdowns.min()) if not drawdowns.empty else 0.0
        
        # Find best and worst days
        if len(daily_returns) > 1:
            best_day = daily_returns.nlargest(1)
            worst_day = daily_returns.nsmallest(1)
            best_day_info = {
                'date': best_day.index[0].strftime('%Y-%m-%d'),
                'return': float(best_day.iloc[0])
            }
            worst_day_info = {
                'date': worst_day.index[0].strftime('%Y-%m-%d'),
                'return': float(worst_day.iloc[0])
            }
        else:
            best_day_info = {'date': None, 'return': 0.0}
            worst_day_info = {'date': None, 'return': 0.0}
        
        return {
            'initial_value': float(initial_value),
            'final_value': float(final_value),
            'total_return': float(total_return * 100),  # Convert to percentage
            'annualized_return': float(annualized_return * 100),  # Convert to percentage
            'volatility': float(volatility * 100),  # Convert to percentage
            'sharpe_ratio': float(sharpe_ratio),
            'max_drawdown': float(max_drawdown * 100),  # Convert to percentage
            'best_day': best_day_info,
            'worst_day': worst_day_info
        }
        
    def generate_tax_report(self, year: int) -> Tuple[pd.DataFrame, Dict]:
        """Generate tax report for specified year"""
        # Define stablecoins set
        stablecoins = {'USD', 'USDC', 'USDT', 'DAI', 'BUSD', 'TUSD', 'USDP', 'USDD', 'FRAX', 'LUSD', 'SUSD', 'GUSD', 'HUSD', 'USDK', 'USDN', 'USDX', 'USDJ', 'USDH', 'USDX', 'USDY', 'USDZ', 'USDW', 'USDV', 'USDU', 'USDT', 'USDT.e', 'USDT.b', 'USDT.c', 'USDT.d', 'USDT.e', 'USDT.f', 'USDT.g', 'USDT.h', 'USDT.i', 'USDT.j', 'USDT.k', 'USDT.l', 'USDT.m', 'USDT.n', 'USDT.o', 'USDT.p', 'USDT.q', 'USDT.r', 'USDT.s', 'USDT.t', 'USDT.u', 'USDT.v', 'USDT.w', 'USDT.x', 'USDT.y', 'USDT.z'}
        
        # Calculate tax lots
        tax_lots = self.calculate_tax_lots()
        
        if tax_lots.empty:
            return pd.DataFrame(), {
                "net_proceeds": 0.0,
                "total_cost_basis": 0.0,
                "total_gain_loss": 0.0,
                "short_term_gain_loss": 0.0,
                "long_term_gain_loss": 0.0,
                "total_transactions": 0
            }
        
        # Filter out stablecoins from tax lots
        tax_lots = tax_lots[~tax_lots['asset'].isin(stablecoins)]
        
        # Ensure numeric columns
        numeric_columns = ["quantity", "cost_basis", "proceeds", "fees", "gain_loss"]
        for col in numeric_columns:
            if col in tax_lots.columns:
                tax_lots[col] = pd.to_numeric(tax_lots[col], errors='coerce')
        
        # Convert disposal_date to datetime for filtering
        tax_lots["disposal_date"] = pd.to_datetime(tax_lots["disposal_date"])
        
        # Filter for disposals in the specified year
        year_start = pd.Timestamp(f"{year}-01-01")
        year_end = pd.Timestamp(f"{year}-12-31")
        year_lots = tax_lots[
            (tax_lots["disposal_date"] >= year_start) & 
            (tax_lots["disposal_date"] <= year_end)
        ].copy()
        
        # Convert dates back to string format
        year_lots["acquisition_date"] = year_lots["acquisition_date"].astype(str)
        year_lots["disposal_date"] = year_lots["disposal_date"].dt.strftime("%Y-%m-%d")
        
        # Get sell transactions for the year to calculate net proceeds
        sell_transactions = self.transactions[
            (self.transactions['timestamp'].dt.year == year) &
            ((self.transactions['type'] == 'sell') | (self.transactions['type'] == 'transfer_out')) &
            (~self.transactions['asset'].isin(stablecoins))  # Exclude stablecoins
        ].copy()
        
        # Calculate net proceeds from source transactions
        net_proceeds = 0.0
        if not sell_transactions.empty:
            # Convert numeric columns and ensure all values are positive
            sell_transactions['quantity'] = pd.to_numeric(sell_transactions['quantity'], errors='coerce').abs()
            sell_transactions['price'] = pd.to_numeric(sell_transactions['price'], errors='coerce').abs()
            sell_transactions['fees'] = pd.to_numeric(sell_transactions['fees'], errors='coerce').abs()
            
            # Calculate subtotal if not present
            if 'subtotal' not in sell_transactions.columns:
                sell_transactions['subtotal'] = sell_transactions['quantity'] * sell_transactions['price']
            else:
                sell_transactions['subtotal'] = pd.to_numeric(sell_transactions['subtotal'], errors='coerce').abs()
            
            # Calculate net proceeds for each transaction and sum
            sell_transactions['net_proceeds'] = sell_transactions['subtotal'] - sell_transactions['fees']
            net_proceeds = sell_transactions['net_proceeds'].sum()
            
            # Debug print transactions
            print("\nDebug: Tax Report Sell Transactions:")
            for _, tx in sell_transactions.iterrows():
                print(f"{tx['asset']}: Type={tx['type']}, Date={tx['timestamp'].date()}, "  # Convert to date only
                      f"Quantity={tx['quantity']:.8f}, Price=${tx['price']:.4f}, "
                      f"Subtotal=${tx['subtotal']:.2f}, Fees=${tx['fees']:.2f}, "
                      f"Net=${tx['net_proceeds']:.2f}")
            print(f"Total Net Proceeds: ${net_proceeds:,.2f}")
        
        # Calculate summary statistics
        summary = {
            "net_proceeds": float(net_proceeds),
            "total_cost_basis": float(year_lots["cost_basis"].sum()) if not year_lots.empty else 0.0,
            "total_gain_loss": float(year_lots["gain_loss"].sum()) if not year_lots.empty else 0.0,
            "short_term_gain_loss": float(year_lots[year_lots["holding_period_days"] <= 365]["gain_loss"].sum()) if not year_lots.empty else 0.0,
            "long_term_gain_loss": float(year_lots[year_lots["holding_period_days"] > 365]["gain_loss"].sum()) if not year_lots.empty else 0.0,
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
        if holdings.empty:
            return {
                "period": period,
                "start_date": start_date,
                "end_date": today,
                "metrics": metrics,
                "current_allocation": {},
                "total_value": 0.0
            }
        
        prices = price_service.get_multi_asset_prices(holdings.columns, start_date, today)
        portfolio_value = self.calculate_portfolio_value(holdings, prices)
        
        if portfolio_value.empty or 'portfolio_value' not in portfolio_value.columns:
            return {
                "period": period,
                "start_date": start_date,
                "end_date": today,
                "metrics": metrics,
                "current_allocation": {},
                "total_value": 0.0
            }
        
        # Get the last row that has data
        last_valid_idx = portfolio_value.last_valid_index()
        if last_valid_idx is None:
            return {
                "period": period,
                "start_date": start_date,
                "end_date": today,
                "metrics": metrics,
                "current_allocation": {},
                "total_value": 0.0
            }
        
        latest_values = {col.replace("_value", ""): val 
                        for col, val in portfolio_value.loc[last_valid_idx].items()
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
        # Define stablecoins set
        stablecoins = {'USD', 'USDC', 'USDT', 'DAI', 'BUSD', 'TUSD', 'USDP', 'USDD', 'FRAX', 'LUSD', 'SUSD', 'GUSD', 'HUSD', 'USDK', 'USDN', 'USDX', 'USDJ', 'USDH', 'USDX', 'USDY', 'USDZ', 'USDW', 'USDV', 'USDU', 'USDT', 'USDT.e', 'USDT.b', 'USDT.c', 'USDT.d', 'USDT.e', 'USDT.f', 'USDT.g', 'USDT.h', 'USDT.i', 'USDT.j', 'USDT.k', 'USDT.l', 'USDT.m', 'USDT.n', 'USDT.o', 'USDT.p', 'USDT.q', 'USDT.r', 'USDT.s', 'USDT.t', 'USDT.u', 'USDT.v', 'USDT.w', 'USDT.x', 'USDT.y', 'USDT.z'}
        
        # Debug print initial transaction data
        print("\nDebug: Initial transaction data:")
        print(f"Total transactions: {len(self.transactions)}")
        print(f"Transaction types: {self.transactions['type'].unique()}")
        print(f"Assets: {self.transactions['asset'].unique()}")
        print(f"Columns: {self.transactions.columns.tolist()}")
        
        # Filter transactions for sells and transfer_outs, excluding stablecoins
        sells = self.transactions[
            ((self.transactions["type"] == "sell") | (self.transactions["type"] == "transfer_out")) & 
            (~self.transactions["asset"].isin(stablecoins))
        ].copy()
        
        # Debug print after filtering
        print("\nDebug: After filtering for sells/transfers and non-stablecoins:")
        print(f"Number of transactions: {len(sells)}")
        print(f"Transaction types: {sells['type'].unique()}")
        print(f"Assets: {sells['asset'].unique()}")
        
        if asset:
            sells = sells[sells["asset"] == asset]
            print(f"\nDebug: After filtering for specific asset '{asset}':")
            print(f"Number of transactions: {len(sells)}")
        
        # Create sell details using exact source data
        sell_details = []
        for _, sell in sells.iterrows():
            try:
                # Skip transactions with NaT dates
                if pd.isna(sell["timestamp"]):
                    print(f"\nDebug: Skipping transaction with NaT date: {sell.get('transaction_id', 'unknown')}")
                    continue
                
                # Convert date to string format (YYYY-MM-DD)
                date_str = sell["timestamp"].strftime("%Y-%m-%d")
                
                # Get quantity and price, defaulting to 0.0 if not available
                quantity = abs(float(sell["quantity"])) if pd.notna(sell["quantity"]) else 0.0
                price = abs(float(sell["price"])) if pd.notna(sell["price"]) else 0.0
                fees = abs(float(sell["fees"])) if pd.notna(sell["fees"]) else 0.0
                
                # Use source subtotal if available, otherwise calculate
                if "subtotal" in sell and pd.notna(sell["subtotal"]):
                    subtotal = abs(float(sell["subtotal"]))
                elif "amount" in sell and pd.notna(sell["amount"]):
                    subtotal = abs(float(sell["amount"]))
                else:
                    subtotal = quantity * price
                
                # Calculate net proceeds (subtotal - fees)
                net_proceeds = subtotal - fees
                
                # For transfer_out transactions, we need to get the price from the price service
                if sell["type"] == "transfer_out" and price == 0:
                    # Get price for the asset on the transaction date
                    asset_prices = price_service.get_multi_asset_prices([sell["asset"]], date_str, date_str)
                    if not asset_prices.empty:
                        price = float(asset_prices.iloc[0]["price"])
                        subtotal = quantity * price
                        net_proceeds = subtotal - fees
                
                # Calculate cost basis by finding matching acquisition lots
                remaining_quantity = quantity
                acquisition_lots = self.transactions[
                    (self.transactions["asset"] == sell["asset"]) &
                    (self.transactions["type"].isin(["buy", "transfer_in", "staking_reward"])) &
                    (self.transactions["timestamp"] <= sell["timestamp"])
                ].copy()
                
                total_cost_basis = 0.0
                
                while remaining_quantity > 0 and not acquisition_lots.empty:
                    acquisition = acquisition_lots.iloc[0]
                    acquisition_quantity = abs(float(acquisition["quantity"]))
                    
                    # Handle cost basis based on transaction type
                    if acquisition["type"] == "staking_reward":
                        # Staking rewards have zero cost basis
                        acquisition_price = 0.0
                        acquisition_subtotal = 0.0
                        acquisition_fees = 0.0
                        acquisition_cost_basis = 0.0
                    else:
                        # Get acquisition price first
                        acquisition_price = abs(float(acquisition["price"])) if pd.notna(acquisition["price"]) else 0.0
                        
                        # Use source subtotal if available, otherwise calculate
                        if "subtotal" in acquisition and pd.notna(acquisition["subtotal"]):
                            acquisition_subtotal = abs(float(acquisition["subtotal"]))
                        else:
                            acquisition_subtotal = acquisition_quantity * acquisition_price
                        
                        acquisition_fees = abs(float(acquisition["fees"])) if pd.notna(acquisition["fees"]) else 0.0
                        acquisition_cost_basis = acquisition_subtotal + acquisition_fees
                    
                    # Calculate cost basis per unit
                    cost_basis_per_unit = acquisition_cost_basis / acquisition_quantity if acquisition_quantity > 0 else 0.0
                    
                    # Determine how much of this lot to use
                    lot_quantity = min(remaining_quantity, acquisition_quantity)
                    lot_cost_basis = lot_quantity * cost_basis_per_unit
                    
                    # Add to total cost basis
                    total_cost_basis += lot_cost_basis
                    
                    # Update remaining quantity and remove used acquisition lot
                    remaining_quantity -= lot_quantity
                    if lot_quantity == acquisition_quantity:
                        acquisition_lots = acquisition_lots.iloc[1:]
                    else:
                        # Update the first row's values
                        acquisition_lots.iloc[0, acquisition_lots.columns.get_loc("quantity")] = acquisition_quantity - lot_quantity
                        acquisition_lots.iloc[0, acquisition_lots.columns.get_loc("subtotal")] = (acquisition_quantity - lot_quantity) * acquisition_price
                        acquisition_lots.iloc[0, acquisition_lots.columns.get_loc("fees")] = ((acquisition_quantity - lot_quantity) / acquisition_quantity) * acquisition_fees
                
                # Create transaction detail with all required fields
                detail = {
                    "date": date_str,
                    "type": sell["type"],
                    "asset": sell["asset"],
                    "quantity": quantity,
                    "price": price,
                    "subtotal": subtotal,
                    "fees": fees,
                    "net_proceeds": net_proceeds,
                    "cost_basis": total_cost_basis,
                    "net_profit": net_proceeds - total_cost_basis,
                    "transaction_id": sell.get("transaction_id", f"{sell['asset']}_{date_str}_{quantity}"),  # Generate a unique ID if not present
                    "institution": sell.get("institution", "Unknown")
                }
                
                sell_details.append(detail)
                
                # Debug print transaction details
                print(f"\nDebug: Transaction details for {sell['asset']} on {date_str}:")
                print(f"Type: {sell['type']}")
                print(f"Quantity: {quantity}")
                print(f"Price: {price}")
                print(f"Subtotal: {subtotal}")
                print(f"Fees: {fees}")
                print(f"Net Proceeds: {net_proceeds}")
                print(f"Cost Basis: {total_cost_basis}")
                print(f"Net Profit: {net_proceeds - total_cost_basis}")
                print(f"Transaction ID: {detail['transaction_id']}")
            
            except Exception as e:
                print(f"Error processing sell transaction:")
                print(f"Transaction: {sell}")
                print(f"Error: {str(e)}")
                continue
        
        # Debug print sell details
        print(f"\nDebug: Number of sell details processed: {len(sell_details)}")
        
        # Convert to DataFrame and sort by date
        if sell_details:
            df = pd.DataFrame(sell_details)
            
            # Ensure all required columns are present with correct types
            required_columns = {
                "date": str,
                "type": str,
                "asset": str,
                "quantity": float,
                "price": float,
                "subtotal": float,
                "fees": float,
                "net_proceeds": float,
                "cost_basis": float,
                "net_profit": float,
                "transaction_id": str,
                "institution": str
            }
            
            # Add any missing columns with default values
            for col, dtype in required_columns.items():
                if col not in df.columns:
                    df[col] = "" if dtype == str else 0.0
            
            # Ensure correct data types
            for col, dtype in required_columns.items():
                df[col] = df[col].astype(dtype)
            
            # Sort by date
            df = df.sort_values("date", ascending=False)
            
            # Debug print final DataFrame
            print("\nDebug: Final DataFrame:")
            print(df.head())
            print("\nColumns:", df.columns.tolist())
            print("\nData types:", df.dtypes)
            
            return df
        else:
            # Return empty DataFrame with all required columns
            return pd.DataFrame(columns=[
                "date", "type", "asset", "quantity", "price", 
                "subtotal", "fees", "net_proceeds", "cost_basis",
                "net_profit", "transaction_id", "institution"
            ]) 