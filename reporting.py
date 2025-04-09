import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from price_service import price_service, PriceService

class PortfolioReporting:
    def __init__(self, transactions: pd.DataFrame):
        """Initialize with transaction data"""
        self.transactions = transactions.sort_values("timestamp").copy()
        self.transactions["date"] = self.transactions["timestamp"].dt.tz_localize(None).dt.floor("D")
        
        # Ensure essential columns always exist
        if 'cost_basis' not in self.transactions.columns:
            self.transactions['cost_basis'] = 0.0
            
        if 'cost_basis_per_unit' not in self.transactions.columns:
            self.transactions['cost_basis_per_unit'] = 0.0
            
        if 'net_proceeds' not in self.transactions.columns:
            self.transactions['net_proceeds'] = 0.0
        
        # Initialize a price service instance
        self.price_service = PriceService()
    
    def get_price_data(self, asset_symbol: str) -> pd.DataFrame:
        """Get historical price data for an asset.
        
        Args:
            asset_symbol: The symbol of the asset to get prices for
            
        Returns:
            DataFrame with price data, containing 'date', 'price', and possibly 'volume' columns
        """
        try:
            # Get the date range from transactions for this asset
            asset_txs = self.transactions[self.transactions['asset'] == asset_symbol]
            
            if asset_txs.empty:
                return pd.DataFrame(columns=['date', 'price', 'volume'])
                
            # Get the min and max dates with some padding
            min_date = pd.to_datetime(asset_txs['timestamp'].min()) - pd.Timedelta(days=30)
            max_date = pd.to_datetime(asset_txs['timestamp'].max()) + pd.Timedelta(days=30)
            
            # Fetch prices from the price service
            prices_df = self.price_service.get_multi_asset_prices(
                [asset_symbol], 
                min_date,
                max_date
            )
            
            # If prices were found, format them consistently
            if not prices_df.empty:
                # Select just the data for this asset
                prices_df = prices_df[prices_df['symbol'] == asset_symbol].copy()
                
                # Ensure date column is datetime
                prices_df['date'] = pd.to_datetime(prices_df['date'])
                
                # Add a volume column if it doesn't exist
                if 'volume' not in prices_df.columns:
                    prices_df['volume'] = 0
                
                # Sort by date
                prices_df = prices_df.sort_values('date')
                
                return prices_df
            else:
                # Return an empty DataFrame with expected columns
                return pd.DataFrame(columns=['date', 'price', 'volume'])
        except Exception as e:
            print(f"Error getting price data for {asset_symbol}: {str(e)}")
            return pd.DataFrame(columns=['date', 'price', 'volume'])
    
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
            # Skip stablecoins and USD
            if asset in ['USD', 'USDC', 'USDT']:
                continue
                
            # Get prices for this asset
            asset_prices = prices[prices['symbol'] == asset].copy()
            
            if asset_prices.empty:
                print(f"\nDebug: Asset {asset} not found in database")
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
        # Get transactions sorted by timestamp
        transactions = self.transactions.sort_values("timestamp").copy()
        
        # Initialize empty lots list
        lots = []
        
        # Track remaining quantities for each buy transaction
        remaining_quantities = {}
        
        # Process each transaction
        for _, tx in transactions.iterrows():
            if tx["type"] in ["buy", "transfer_in", "staking_reward"]:
                # For buys and transfers in, add to available quantities
                tx_id = tx.get("transaction_id", f"{tx['asset']}_{tx['timestamp']}_{tx['quantity']}")
                acquisition_date = tx["timestamp"].replace(tzinfo=None)
                
                # Get acquisition quantity and cost
                quantity = abs(float(tx["quantity"])) if not pd.isna(tx["quantity"]) else 0.0
                
                # Skip if zero quantity
                if quantity == 0:
                    continue
                    
                # Handle cost basis based on transaction type
                if tx["type"] == "staking_reward":
                    # For staking rewards, cost basis is market value at time of receipt
                    reward_date = tx["timestamp"].replace(tzinfo=None)
                    prices_df = price_service.get_multi_asset_prices(
                        [tx["asset"]], 
                        reward_date,
                        reward_date
                    )
                    
                    if not prices_df.empty:
                        market_price = float(prices_df.iloc[0]["price"])
                        acquisition_cost = quantity * market_price
                    else:
                        # If no price available, use 0
                        acquisition_cost = 0.0
                elif tx["type"] == "transfer_in" and 'cost_basis' in tx and pd.notna(tx['cost_basis']) and float(tx['cost_basis']) > 0:
                    # Use pre-calculated cost basis for transfer_in transactions
                    acquisition_cost = float(tx['cost_basis'])
                else:
                    # For buy transactions, get price and calculate cost
                    price = tx["price"] if pd.notna(tx["price"]) else 0.0
                    
                    # Use subtotal if available, otherwise calculate based on price
                    if "subtotal" in tx and pd.notna(tx["subtotal"]):
                        subtotal = abs(float(tx["subtotal"]))
                    else:
                        subtotal = quantity * price
                    
                    fees = abs(float(tx["fees"])) if pd.notna(tx["fees"]) else 0.0
                    acquisition_cost = subtotal + fees
                
                # Record this acquisition lot
                remaining_quantities[tx_id] = {
                    "asset": tx["asset"],
                    "quantity": quantity,
                    "acquisition_date": acquisition_date,
                    "acquisition_cost": acquisition_cost,
                    "acquisition_exchange": tx.get("institution", "Unknown"),
                    "acquisition_type": tx["type"]
                }
            
            elif tx["type"] in ["sell", "transfer_out"]:
                # For sells and transfers out, reduce available quantities using FIFO
                asset = tx["asset"]
                disposal_date = tx["timestamp"].replace(tzinfo=None)
                disposal_quantity = abs(float(tx["quantity"])) if not pd.isna(tx["quantity"]) else 0.0
                disposal_exchange = tx.get("institution", "Unknown")
                
                # Skip if zero quantity
                if disposal_quantity == 0:
                    continue
                
                # Initialize disposal_fees to 0.0 if not provided
                disposal_fees = abs(float(tx["fees"])) if pd.notna(tx["fees"]) else 0.0
                
                # Calculate disposal proceeds
                disposal_price = tx["price"] if pd.notna(tx["price"]) else 0.0
                
                if "subtotal" in tx and pd.notna(tx["subtotal"]):
                    disposal_subtotal = abs(float(tx["subtotal"]))
                else:
                    disposal_subtotal = disposal_quantity * disposal_price
                
                disposal_proceeds = disposal_subtotal
                
                # Use pre-calculated cost basis if available
                if 'cost_basis' in tx and pd.notna(tx['cost_basis']) and float(tx['cost_basis']) > 0:
                    # Just use the pre-calculated cost basis
                    total_cost_basis = float(tx['cost_basis'])
                    
                    # Create a single lot for this disposal
                    lots.append({
                        "asset": asset,
                        "quantity": disposal_quantity,
                        "acquisition_date": disposal_date - timedelta(days=1),  # Assume acquired just before disposal
                        "disposal_date": disposal_date,
                        "acquisition_exchange": tx.get("matching_institution", "Unknown"),
                        "disposal_exchange": disposal_exchange,
                        "proceeds": disposal_proceeds,
                        "fees": disposal_fees,
                        "cost_basis": total_cost_basis,
                        "gain_loss": disposal_proceeds - total_cost_basis,
                        "holding_period_days": 1,  # Assume 1 day for pre-calculated cost basis
                        "disposal_transaction_id": tx.get("transaction_id", "Unknown")
                    })
                    
                    continue  # Skip FIFO processing for transactions with pre-calculated cost basis
                
                # Find lots for this asset using FIFO method
                remaining_disposal_quantity = disposal_quantity
                
                for tx_id, lot in list(remaining_quantities.items()):
                    if lot["asset"] == asset and lot["quantity"] > 0:
                        # Calculate how much of this lot to use
                        lot_quantity = min(remaining_disposal_quantity, lot["quantity"])
                        
                        # Calculate cost basis for this portion
                        lot_cost_basis = (lot_quantity / lot["quantity"]) * lot["acquisition_cost"]
                        
                        # Calculate fees for this portion (proportional)
                        lot_fees = (lot_quantity / disposal_quantity) * disposal_fees
                        
                        # Calculate proceeds for this portion (proportional)
                        lot_proceeds = (lot_quantity / disposal_quantity) * disposal_proceeds
                        
                        # Calculate holding period
                        holding_period = disposal_date - lot["acquisition_date"]
                        holding_period_days = holding_period.days
                        
                        # Add tax lot
                        lots.append({
                            "asset": asset,
                            "quantity": lot_quantity,
                            "acquisition_date": lot["acquisition_date"],
                            "disposal_date": disposal_date,
                            "acquisition_exchange": lot["acquisition_exchange"],
                            "disposal_exchange": disposal_exchange,
                            "proceeds": lot_proceeds,
                            "fees": lot_fees,
                            "cost_basis": lot_cost_basis,
                            "gain_loss": lot_proceeds - lot_cost_basis,
                            "holding_period_days": holding_period_days,
                            "disposal_transaction_id": tx.get("transaction_id", "Unknown"),
                            "acquisition_type": lot.get("acquisition_type", "buy")
                        })
                        
                        # Update remaining quantities
                        remaining_disposal_quantity -= lot_quantity
                        lot["quantity"] -= lot_quantity
                        
                        # If lot is fully used, remove it
                        if lot["quantity"] <= 0:
                            remaining_quantities.pop(tx_id)
                        
                        # If all disposal quantity is accounted for, break
                        if remaining_disposal_quantity <= 0:
                            break
                
                # If there's remaining disposal quantity with no matching buy lots, create a zero cost basis lot
                if remaining_disposal_quantity > 0:
                    # Calculate holding period (assume same day for zero basis)
                    holding_period_days = 0
                    
                    # Calculate proportional fees and proceeds
                    lot_fees = (remaining_disposal_quantity / disposal_quantity) * disposal_fees
                    lot_proceeds = (remaining_disposal_quantity / disposal_quantity) * disposal_proceeds
                    
                    # Add tax lot with zero cost basis
                    lots.append({
                        "asset": asset,
                        "quantity": remaining_disposal_quantity,
                        "acquisition_date": disposal_date,  # Same day as disposal
                        "disposal_date": disposal_date,
                        "acquisition_exchange": "Unknown",
                        "disposal_exchange": disposal_exchange,
                        "proceeds": lot_proceeds,
                        "fees": lot_fees,
                        "cost_basis": 0,
                        "gain_loss": lot_proceeds,
                        "holding_period_days": holding_period_days,
                        "disposal_transaction_id": tx.get("transaction_id", "Unknown"),
                        "acquisition_type": "unknown"
                    })
        
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
        # Calculate tax lots for all transactions
        tax_lots = self.calculate_tax_lots()
        
        if tax_lots.empty:
            return pd.DataFrame(), {
                "net_proceeds": 0.0,
                "total_cost_basis": 0.0,
                "total_gain_loss": 0.0,
                "short_term_gain_loss": 0.0,
                "long_term_gain_loss": 0.0
            }
        
        # Add disposal_type column based on acquisition_type if doesn't exist
        if 'disposal_type' not in tax_lots.columns:
            # If we have disposal_transaction_id, lookup the type from original transactions
            if 'disposal_transaction_id' in tax_lots.columns:
                # Create a lookup dictionary of transaction_id to type
                tx_types = self.transactions.set_index('transaction_id')['type'].to_dict()
                tax_lots['disposal_type'] = tax_lots['disposal_transaction_id'].map(
                    lambda x: tx_types.get(x, 'unknown')
                )
            else:
                # Default to 'sell' if we can't determine the type
                tax_lots['disposal_type'] = 'sell'
        
        # Convert disposal_date to datetime for filtering
        tax_lots["disposal_date"] = pd.to_datetime(tax_lots["disposal_date"])
        
        # Filter for disposals in the specified year
        year_lots = tax_lots[tax_lots["disposal_date"].dt.year == year].copy()
        
        if year_lots.empty:
            return pd.DataFrame(), {
                "net_proceeds": 0.0,
                "total_cost_basis": 0.0,
                "total_gain_loss": 0.0,
                "short_term_gain_loss": 0.0,
                "long_term_gain_loss": 0.0
            }
        
        # Add term classification (short or long)
        year_lots["term"] = year_lots["holding_period_days"].apply(
            lambda days: "Short Term" if days <= 365 else "Long Term"
        )
        
        # Calculate year summary
        net_proceeds = year_lots["proceeds"].sum()
        total_cost_basis = year_lots["cost_basis"].sum()
        total_gain_loss = year_lots["gain_loss"].sum()
        year_start = pd.Timestamp(f"{year}-01-01")
        year_end = pd.Timestamp(f"{year}-12-31")
        year_lots = tax_lots[
            (tax_lots["disposal_date"] >= year_start) & 
            (tax_lots["disposal_date"] <= year_end)
        ].copy()
        
        # Convert dates back to string format
        year_lots["acquisition_date"] = year_lots["acquisition_date"].astype(str)
        year_lots["disposal_date"] = year_lots["disposal_date"].dt.strftime("%Y-%m-%d")
        
        # Get sell transactions for the year to calculate net proceeds and gains/losses
        # IMPORTANT: For the summary section, always exclude transfer_out transactions
        sales_df = self.show_sell_transactions_with_lots(include_transfers=False)
        
        if not sales_df.empty:
            sales_df['date'] = pd.to_datetime(sales_df['date'])
            year_sales = sales_df[sales_df['date'].dt.year == year].copy()
            
            # Calculate summary statistics from sales history (transfers excluded)
            if not year_sales.empty:
                net_proceeds = year_sales['net_proceeds'].sum()
                total_cost_basis = year_sales['cost_basis'].sum()
                total_gain_loss = year_sales['net_profit'].sum()
                
                # Calculate short-term and long-term gains based on holding period
                # Filter tax lots for the current year's disposals AND exclude transfer_out disposals
                year_tax_lots = tax_lots[
                    (tax_lots["disposal_date"].dt.year == year) &
                    (tax_lots["disposal_type"] != "transfer_out")
                ].copy()
                
                # Calculate short-term and long-term gains from tax lots
                short_term_gain_loss = year_tax_lots[year_tax_lots["holding_period_days"] <= 365]["gain_loss"].sum()
                long_term_gain_loss = year_tax_lots[year_tax_lots["holding_period_days"] > 365]["gain_loss"].sum()
                
                # Debug print
                print(f"\nDebug: Short/Long Term Calculation")
                print(f"Total gain/loss from sales (excluding transfers): ${total_gain_loss:,.2f}")
                print(f"Short-term gain/loss: ${short_term_gain_loss:,.2f}")
                print(f"Long-term gain/loss: ${long_term_gain_loss:,.2f}")
                print(f"Sum of short + long: ${short_term_gain_loss + long_term_gain_loss:,.2f}")
                
                # Verify the split adds up to total gain/loss
                gain_loss_diff = abs(total_gain_loss - (short_term_gain_loss + long_term_gain_loss))
                if gain_loss_diff > 0.01:  # Allow for small rounding differences
                    print(f"Warning: Gain/loss split does not match total by ${gain_loss_diff:,.2f}")
                    # If there's a significant difference, proportionally adjust the split
                    if abs(short_term_gain_loss + long_term_gain_loss) > 0:
                        adjustment_factor = total_gain_loss / (short_term_gain_loss + long_term_gain_loss)
                        short_term_gain_loss *= adjustment_factor
                        long_term_gain_loss *= adjustment_factor
                        print(f"Adjusted values:")
                        print(f"Short-term gain/loss: ${short_term_gain_loss:,.2f}")
                        print(f"Long-term gain/loss: ${long_term_gain_loss:,.2f}")
                
                summary = {
                    "net_proceeds": float(net_proceeds),
                    "total_cost_basis": float(total_cost_basis),
                    "total_gain_loss": float(total_gain_loss),
                    "short_term_gain_loss": float(short_term_gain_loss),
                    "long_term_gain_loss": float(long_term_gain_loss),
                    "total_transactions": len(year_sales)
                }
            else:
                summary = {
                    "net_proceeds": 0.0,
                    "total_cost_basis": 0.0,
                    "total_gain_loss": 0.0,
                    "short_term_gain_loss": 0.0,
                    "long_term_gain_loss": 0.0,
                    "total_transactions": 0
                }
        else:
            summary = {
                "net_proceeds": 0.0,
                "total_cost_basis": 0.0,
                "total_gain_loss": 0.0,
                "short_term_gain_loss": 0.0,
                "long_term_gain_loss": 0.0,
                "total_transactions": 0
            }
        
        # Debug print
        print(f"\nDebug: Tax Report for {year}")
        print(f"Total lots: {len(year_lots)}")
        print(f"Net proceeds (excluding stablecoins and transfers): ${summary['net_proceeds']:,.2f}")
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

    def show_sell_transactions_with_lots(self, asset: str = None, include_transfers: bool = True) -> pd.DataFrame:
        """Show sell transactions and their associated buy lots.
        
        Args:
            asset: Optional filter for a specific asset
            include_transfers: Whether to include transfer_out transactions (default: True)
        """
        # Define stablecoins set
        stablecoins = {'USD', 'USDC', 'USDT', 'DAI', 'BUSD', 'TUSD', 'USDP', 'USDD', 'FRAX', 'LUSD', 'SUSD', 'GUSD', 'HUSD', 'USDK', 'USDN', 'USDX', 'USDJ', 'USDH', 'USDX', 'USDY', 'USDZ', 'USDW', 'USDV', 'USDU', 'USDT', 'USDT.e', 'USDT.b', 'USDT.c', 'USDT.d', 'USDT.e', 'USDT.f', 'USDT.g', 'USDT.h', 'USDT.i', 'USDT.j', 'USDT.k', 'USDT.l', 'USDT.m', 'USDT.n', 'USDT.o', 'USDT.p', 'USDT.q', 'USDT.r', 'USDT.s', 'USDT.t', 'USDT.u', 'USDT.v', 'USDT.w', 'USDT.x', 'USDT.y', 'USDT.z'}
        
        # Debug print initial transaction data
        print("\nDebug: Initial transaction data:")
        print(f"Total transactions: {len(self.transactions)}")
        print(f"Transaction types: {self.transactions['type'].unique()}")
        print(f"Assets: {self.transactions['asset'].unique()}")
        print(f"Columns: {self.transactions.columns.tolist()}")
        
        # Determine transaction types to include
        types_to_include = ["sell"]
        if include_transfers:
            types_to_include.append("transfer_out")
            
        # Filter transactions for selected types, excluding stablecoins
        sells = self.transactions[
            (self.transactions["type"].isin(types_to_include)) & 
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
                
                # For Gemini transfer_out transactions, prioritize getting price from the price database
                if sell["type"] == "transfer_out" and sell["institution"] == "gemini":
                    # Try to get price from the price database first
                    transfer_date = sell["timestamp"].replace(tzinfo=None)
                    prices_df = price_service.get_multi_asset_prices(
                        [sell["asset"]], 
                        transfer_date,
                        transfer_date
                    )
                    
                    if not prices_df.empty:
                        db_price = float(prices_df.iloc[0]["price"])
                        print(f"\nUsing database price for Gemini transfer_out:")
                        print(f"  Asset: {sell['asset']}")
                        print(f"  Date: {sell['timestamp']}")
                        print(f"  Original price: ${price:.4f}")
                        print(f"  Database price: ${db_price:.4f}")
                        print(f"  Data source: {prices_df.iloc[0].get('source', 'unknown')}")
                        
                        # Use database price
                        price = db_price
                
                # Use source subtotal if available, otherwise calculate
                if "subtotal" in sell and pd.notna(sell["subtotal"]):
                    subtotal = abs(float(sell["subtotal"]))
                elif "amount" in sell and pd.notna(sell["amount"]):
                    subtotal = abs(float(sell["amount"]))
                else:
                    subtotal = quantity * price
                
                # Calculate net proceeds (subtotal - fees)
                net_proceeds = subtotal - fees
                
                # For other transfer_out transactions (non-Gemini), we need to get the price from the price service if not present
                if sell["type"] == "transfer_out" and not (sell["institution"] == "gemini") and price == 0:
                    # Get price for the asset on the transaction date
                    asset_prices = price_service.get_multi_asset_prices([sell["asset"]], date_str, date_str)
                    if not asset_prices.empty:
                        price = float(asset_prices.iloc[0]["price"])
                        subtotal = quantity * price
                        net_proceeds = subtotal - fees
                
                # For transfers, first check if there's a pre-calculated cost basis from transfer reconciliation
                total_cost_basis = 0.0
                if sell["type"] == "transfer_out" and 'cost_basis' in sell and pd.notna(sell['cost_basis']) and float(sell['cost_basis']) > 0:
                    total_cost_basis = float(sell['cost_basis'])
                    print(f"\nUsing pre-calculated cost basis for {sell['institution']} transfer_out:")
                    print(f"  Asset: {sell['asset']}")
                    print(f"  Date: {sell['timestamp']}")
                    print(f"  Pre-calculated cost basis: ${total_cost_basis:.2f}")
                else:
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
                            # Get market price at time of staking reward
                            reward_date = acquisition["timestamp"].replace(tzinfo=None)
                            prices_df = price_service.get_multi_asset_prices(
                                [acquisition["asset"]], 
                                reward_date,
                                reward_date
                            )
                            
                            if not prices_df.empty:
                                acquisition_price = float(prices_df.iloc[0]["price"])
                                acquisition_subtotal = acquisition_quantity * acquisition_price
                                acquisition_fees = 0.0  # Staking rewards typically have no fees
                                acquisition_cost_basis = acquisition_subtotal
                                
                                if acquisition["asset"] == 'DOT':
                                    print(f"\nStaking reward cost basis calculation:")
                                    print(f"- Date: {reward_date}")
                                    print(f"- Market price: ${acquisition_price:.4f}")
                                    print(f"- Quantity: {acquisition_quantity:.8f}")
                                    print(f"- Cost basis: ${acquisition_cost_basis:.2f}")
                            else:
                                # Fallback to zero if no price data available
                                acquisition_price = 0.0
                                acquisition_subtotal = 0.0
                                acquisition_fees = 0.0
                                acquisition_cost_basis = 0.0
                        elif acquisition["type"] == "transfer_in" and 'cost_basis' in acquisition and pd.notna(acquisition['cost_basis']) and float(acquisition['cost_basis']) > 0:
                            # Use pre-calculated cost basis from transfer reconciliation for transfer_in transactions
                            acquisition_cost_basis = float(acquisition['cost_basis'])
                            if acquisition["asset"] == 'DOT':
                                print(f"\nUsing pre-calculated cost basis for transfer_in acquisition:")
                                print(f"- Date: {acquisition['timestamp']}")
                                print(f"- Exchange: {acquisition['institution']}")
                                print(f"- Pre-calculated cost basis: ${acquisition_cost_basis:.2f}")
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
                        acquisition_lots = acquisition_lots.iloc[1:]
                
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
                print(f"Error processing transaction: {str(e)}")
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

    def get_transfer_transactions(self, year=None, asset=None):
        """Get transfer transactions for the specified year and asset."""
        # Filter for transfer transactions
        transfers = self.transactions[
            (self.transactions['type'].isin(['transfer_in', 'transfer_out']))
        ].copy()
        
        # Add debug logging for DOT transfers
        dot_transfers = transfers[transfers['asset'] == 'DOT'].copy()
        if not dot_transfers.empty:
            print("\nDebug: DOT Transfers:")
            for _, row in dot_transfers.iterrows():
                print(f"\nTransfer Details:")
                print(f"  Date: {row['date']}")
                print(f"  Exchange: {row['institution']}")
                print(f"  Type: {row['type']}")
                print(f"  Quantity: {row['quantity']}")
                print(f"  Price: {row['price']}")
                print(f"  Subtotal: {row['subtotal']}")
                print(f"  Fees: {row['fees']}")
        
        # Continue with existing code
        if year is not None:
            transfers = transfers[transfers['date'].dt.year == year]
        
        if asset is not None and asset != "All Assets":
            transfers = transfers[transfers['asset'] == asset]
            
        # Initialize critical columns to ensure they exist
        if 'cost_basis' not in transfers.columns:
            transfers['cost_basis'] = 0.0
        
        if 'cost_basis_per_unit' not in transfers.columns:
            transfers['cost_basis_per_unit'] = 0.0
            
        if 'net_proceeds' not in transfers.columns:
            transfers['net_proceeds'] = 0.0
        
        # Store original price before any modifications
        transfers['original_price'] = transfers['price']
        
        # For Gemini transactions, prioritize database prices
        for idx, transfer in transfers.iterrows():
            if transfer['institution'] == 'gemini':
                transfer_date = transfer["timestamp"].replace(tzinfo=None)
                asset = transfer['asset']
                prices_df = price_service.get_multi_asset_prices(
                    [asset], 
                    transfer_date,
                    transfer_date
                )
                
                if not prices_df.empty:
                    db_price = float(prices_df.iloc[0]["price"])
                    print(f"\nUpdating price for Gemini transfer:")
                    print(f"  Asset: {asset}")
                    print(f"  Date: {transfer['timestamp']}")
                    print(f"  Original price: ${transfer['price'] if pd.notna(transfer['price']) else 0.0:.4f}")
                    print(f"  Database price: ${db_price:.4f}")
                    print(f"  Data source: {prices_df.iloc[0].get('source', 'unknown')}")
                    
                    # Update the price in the DataFrame
                    transfers.at[idx, 'price'] = db_price
                    
                    # Also recalculate subtotal using this price
                    quantity = abs(float(transfer['quantity']))
                    transfers.at[idx, 'subtotal'] = quantity * db_price
        
        # For Binance US transfer-out transactions, use the total value directly
        # For other transactions, calculate subtotal using price * quantity
        transfers['subtotal'] = transfers.apply(
            lambda row: row['price'] if (  # Use total value directly for Binance transfer-out
                row['type'] == 'transfer_out' and 
                row['institution'] == 'binanceus' and 
                pd.notna(row['price'])
            ) else (  # Calculate subtotal normally for other cases
                abs(row['quantity']) * row['price'] if pd.notna(row['price']) and pd.notna(row['quantity']) else 0
            ),
            axis=1
        )
        
        # For Binance transfer-out transactions, calculate the correct per-unit price
        transfers['price'] = transfers.apply(
            lambda row: (row['price'] / abs(row['quantity'])) if (  # Calculate per-unit price for Binance transfer-out
                row['type'] == 'transfer_out' and 
                row['institution'] == 'binanceus' and 
                pd.notna(row['price']) and 
                pd.notna(row['quantity']) and 
                abs(row['quantity']) > 0
            ) else row['price'],  # Keep original price for other cases
            axis=1
        )
        
        # First calculate cost basis for all transfer_out transactions
        # This needs to be done before matching to ensure cost basis is accurate
        for idx, transfer in transfers.iterrows():
            if transfer['type'] == 'transfer_out':
                # For Coinbase transfers out, prioritize using their cost basis calculation
                # This preserves the original cost basis information when transferring to other exchanges
                if transfer['institution'] == 'coinbase' and not pd.notna(transfer.get('cost_basis')):
                    # Calculate cost basis using the _calculate_sell_cost_basis method
                    cost_basis = self._calculate_sell_cost_basis(transfer)
                    transfers.at[idx, 'cost_basis'] = cost_basis
                    
                    # Also calculate cost_basis_per_unit for later reference
                    quantity = abs(float(transfer['quantity']))
                    if quantity > 0:
                        transfers.at[idx, 'cost_basis_per_unit'] = cost_basis / quantity
                    else:
                        transfers.at[idx, 'cost_basis_per_unit'] = 0.0
                        
                    print(f"\nCalculated cost basis for Coinbase transfer out of {transfer['asset']}:")
                    print(f"  Date: {transfer['timestamp']}")
                    print(f"  Quantity: {quantity}")
                    print(f"  Cost basis: ${cost_basis:.2f}")
                    print(f"  Cost basis per unit: ${transfers.at[idx, 'cost_basis_per_unit']:.4f}")
                
                # For other exchanges, calculate cost basis normally
                elif not pd.notna(transfer.get('cost_basis')):
                    cost_basis = self._calculate_sell_cost_basis(transfer)
                    transfers.at[idx, 'cost_basis'] = cost_basis
                    
                    # Also calculate cost_basis_per_unit
                    quantity = abs(float(transfer['quantity']))
                    if quantity > 0:
                        transfers.at[idx, 'cost_basis_per_unit'] = cost_basis / quantity
                    else:
                        transfers.at[idx, 'cost_basis_per_unit'] = 0.0
        
        # Handle matched transfers - copy cost basis from transfer_out to corresponding transfer_in
        for _, transfer in transfers.iterrows():
            if transfer['type'] == 'transfer_out' and pd.notna(transfer.get('transfer_id')):
                # Find the matching transfer_in
                matching_idx = transfers[
                    (transfers['transfer_id'] == transfer['transfer_id']) & 
                    (transfers['type'] == 'transfer_in')
                ].index
                
                if not matching_idx.empty:
                    # Get the pre-calculated cost basis for the transfer_out
                    if pd.notna(transfer.get('cost_basis')) and float(transfer.get('cost_basis', 0)) > 0:
                        sending_cost_basis = float(transfer['cost_basis'])
                    else:
                        # Calculate it if not already present
                        sending_cost_basis = self._calculate_sell_cost_basis(transfer)
                        
                    # Copy the cost basis to the matched transfer_in (adding any additional fees)
                    receiving_fees = abs(float(transfers.at[matching_idx[0], 'fees'])) if pd.notna(transfers.at[matching_idx[0], 'fees']) else 0.0
                    total_cost_basis = sending_cost_basis + receiving_fees
                    
                    # Update cost basis in the transfers DataFrame
                    transfers.at[matching_idx[0], 'cost_basis'] = total_cost_basis
                    qty = abs(float(transfers.at[matching_idx[0], 'quantity']))
                    if qty > 0:
                        transfers.at[matching_idx[0], 'cost_basis_per_unit'] = total_cost_basis / qty
                    else:
                        transfers.at[matching_idx[0], 'cost_basis_per_unit'] = 0.0
                    
                    # Also store the source cost basis info for traceability
                    transfers.at[matching_idx[0], 'source_cost_basis'] = sending_cost_basis
                    transfers.at[matching_idx[0], 'source_exchange'] = transfer['institution']
                    
                    print(f"\nMatched transfer cost basis calculation:")
                    print(f"  Asset: {transfer['asset']}")
                    print(f"  From: {transfer['institution']} to {transfers.at[matching_idx[0], 'institution']}")
                    print(f"  Transfer ID: {transfer['transfer_id']}")
                    print(f"  Original cost basis: ${sending_cost_basis:.2f}")
                    print(f"  Additional receiving fees: ${receiving_fees:.2f}")
                    print(f"  Total cost basis: ${total_cost_basis:.2f}")
                    print(f"  Cost basis per unit: ${transfers.at[matching_idx[0], 'cost_basis_per_unit']:.4f}")
        
        # Calculate cost basis for remaining transfers
        for idx, transfer in transfers.iterrows():
            # Skip transfers that already have cost basis calculated from the matching process
            if pd.notna(transfers.at[idx, 'cost_basis']) and transfers.at[idx, 'cost_basis'] > 0:
                continue
                
            # Calculate cost basis for this transfer
            cost_basis = self._calculate_transfer_cost_basis(transfer)
            transfers.at[idx, 'cost_basis'] = cost_basis
            
            # Calculate cost basis per unit
            quantity = abs(float(transfer['quantity']))
            if quantity > 0:
                transfers.at[idx, 'cost_basis_per_unit'] = cost_basis / quantity
            else:
                transfers.at[idx, 'cost_basis_per_unit'] = 0.0
        
        # Special handling for transfers back to Coinbase that may include staking rewards
        # This is critical for maintaining correct cost basis when funds move between exchanges
        for idx, transfer in transfers.iterrows():
            if transfer['type'] == 'transfer_in' and transfer['institution'] == 'coinbase' and pd.notna(transfer.get('matching_institution')):
                # Get the original transfer that went from Coinbase to the other exchange
                original_transfer = self.transactions[
                    (self.transactions['type'] == 'transfer_out') &
                    (self.transactions['institution'] == 'coinbase') &
                    (self.transactions['asset'] == transfer['asset']) &
                    (self.transactions['timestamp'] < transfer['timestamp'])
                ].sort_values('timestamp', ascending=False)
                
                if not original_transfer.empty:
                    # Check if the quantity transferred back is greater than what was sent
                    # This would indicate staking rewards were included
                    original_qty = abs(float(original_transfer.iloc[0]['quantity']))
                    current_qty = abs(float(transfer['quantity']))
                    
                    if current_qty > original_qty * 1.01:  # Add 1% buffer for minor differences
                        # Calculate the additional quantity from staking
                        staking_qty = current_qty - original_qty
                        
                        print(f"\nDetected potential staking rewards in transfer back to Coinbase:")
                        print(f"  Asset: {transfer['asset']}")
                        print(f"  Original transfer quantity: {original_qty}")
                        print(f"  Current transfer quantity: {current_qty}")
                        print(f"  Estimated staking rewards: {staking_qty}")
                        
                        # Get market price at time of transfer for the staking portion
                        transfer_date = transfer["timestamp"].replace(tzinfo=None)
                        prices_df = price_service.get_multi_asset_prices(
                            [transfer['asset']], 
                            transfer_date,
                            transfer_date
                        )
                        
                        if not prices_df.empty:
                            market_price = float(prices_df.iloc[0]["price"])
                            
                            # Adjust the cost basis calculation:
                            # 1. Original amount keeps its cost basis
                            # 2. Staking rewards are valued at market price
                            original_cost_basis = transfers.at[idx, 'cost_basis'] 
                            staking_cost_basis = staking_qty * market_price
                            
                            # Update the total cost basis
                            total_cost_basis = original_cost_basis + staking_cost_basis
                            transfers.at[idx, 'cost_basis'] = total_cost_basis
                            transfers.at[idx, 'cost_basis_per_unit'] = total_cost_basis / current_qty
                            
                            print(f"  Market price at transfer: ${market_price:.4f}")
                            print(f"  Original cost basis: ${original_cost_basis:.2f}")
                            print(f"  Staking portion cost basis: ${staking_cost_basis:.2f}")
                            print(f"  New total cost basis: ${total_cost_basis:.2f}")
                            print(f"  New cost basis per unit: ${transfers.at[idx, 'cost_basis_per_unit']:.4f}")
        
        # Calculate net proceeds for send transfers (similar to sells)
        transfers['net_proceeds'] = transfers.apply(
            lambda row: row['subtotal'] - row['fees'] if row['type'] == 'transfer_out' else 0,
            axis=1
        )
        
        # Add source and destination exchange information
        transfers['source_exchange'] = transfers.apply(
            lambda row: row['institution'] if row['type'] == 'transfer_out' else '',
            axis=1
        )
        transfers['destination_exchange'] = transfers.apply(
            lambda row: row['institution'] if row['type'] == 'transfer_in' else '',
            axis=1
        )
        
        # Ensure all required columns exist
        required_columns = [
            'date', 'type', 'asset', 'quantity', 'price', 
            'subtotal', 'fees',
            'source_exchange', 'destination_exchange', 'transfer_id', 'matching_institution',
            'cost_basis', 'cost_basis_per_unit', 'net_proceeds'
        ]
        
        for col in required_columns:
            if col not in transfers.columns:
                if col == 'date':
                    transfers['date'] = transfers['timestamp'].dt.strftime('%Y-%m-%d')
                elif col in ['source_exchange', 'destination_exchange', 'matching_institution']:
                    transfers[col] = ''
                elif col == 'transfer_id':
                    transfers[col] = None
                elif col in ['cost_basis', 'cost_basis_per_unit', 'net_proceeds']:
                    transfers[col] = 0.0
                else:
                    transfers[col] = 0.0
        
        # Format numeric columns
        numeric_columns = ['quantity', 'price', 'subtotal', 'fees', 'cost_basis', 'cost_basis_per_unit', 'net_proceeds']
        for col in numeric_columns:
            transfers[col] = pd.to_numeric(transfers[col], errors='coerce').fillna(0.0)
            
        # Debug print final calculations
        print("\nDebug: Final transfer calculations:")
        for _, row in transfers.iterrows():
            print(f"{row['asset']} {row['type']} on {row['date']}:")
            print(f"  Exchange: {row['institution']}")
            print(f"  Quantity: {abs(row['quantity']):.8f}")
            print(f"  Price per unit: ${row['price']:.4f}")
            print(f"  Subtotal: ${row['subtotal']:.2f}")
            print(f"  Fees: ${row['fees']:.2f}")
            print(f"  Cost Basis: ${row['cost_basis']:.2f}")
            print(f"  Cost Basis per unit: ${row['cost_basis_per_unit']:.4f}")
            print(f"  Net Proceeds: ${row['net_proceeds']:.2f}")
            if pd.notna(row.get('transfer_id')):
                print(f"  Transfer ID: {row['transfer_id']}")
                print(f"  Matching Institution: {row.get('matching_institution', 'Unknown')}")
        
        return transfers.sort_values('date', ascending=False)
    
    def _calculate_transfer_cost_basis(self, transaction: pd.Series) -> float:
        """Calculate cost basis for a transfer transaction."""
        if transaction['asset'] == 'DOT':
            print(f"\nDebug: Processing DOT transfer:")
            print(f"  Date: {transaction['date']}")
            print(f"  Exchange: {transaction['institution']}")
            print(f"  Type: {transaction['type']}")
            print(f"  Quantity: {transaction['quantity']}")
            print(f"  Transfer ID: {transaction.get('transfer_id', 'None')}")

        quantity = abs(float(transaction["quantity"]))
        asset = transaction["asset"]
        
        # If this is a matched transfer_in, get the cost basis from the matching transfer_out
        if (transaction['type'] == 'transfer_in' and pd.notna(transaction.get('transfer_id'))):
            matching_transfer = self.transactions[
                (self.transactions['transfer_id'] == transaction['transfer_id']) &
                (self.transactions['type'] == 'transfer_out')
            ]
            if not matching_transfer.empty:
                # First check if the transfer_out already has a calculated cost_basis
                if 'cost_basis' in matching_transfer.columns and pd.notna(matching_transfer.iloc[0]['cost_basis']) and float(matching_transfer.iloc[0]['cost_basis']) > 0:
                    # Use the pre-calculated cost basis from the transfer reconciliation
                    sending_cost_basis = float(matching_transfer.iloc[0]['cost_basis'])
                    fees = abs(float(transaction["fees"])) if pd.notna(transaction["fees"]) else 0.0
                    total_cost_basis = sending_cost_basis + fees
                    
                    print(f"\nUsing pre-calculated cost basis from matched transfer_out:")
                    print(f"  Asset: {asset}")
                    print(f"  Source Exchange: {matching_transfer.iloc[0]['institution']}")
                    print(f"  Matched cost basis: ${sending_cost_basis:.2f}")
                    print(f"  Additional receive fees: ${fees:.2f}")
                    print(f"  Total cost basis: ${total_cost_basis:.2f}")
                    
                    return total_cost_basis
                else:
                    # Calculate cost basis from the sending side
                    sending_cost_basis = self._calculate_sell_cost_basis(matching_transfer.iloc[0])
                    # Add any additional fees from receiving side
                    fees = abs(float(transaction["fees"])) if pd.notna(transaction["fees"]) else 0.0
                    total_cost_basis = sending_cost_basis + fees
                    
                    if asset == 'DOT':
                        print(f"\nMatched transfer cost basis calculation:")
                        print(f"- Found matching transfer out from {matching_transfer.iloc[0]['institution']}")
                        print(f"- Original cost basis: ${sending_cost_basis:.2f}")
                        print(f"- Additional receive fees: ${fees:.2f}")
                        print(f"- Total cost basis: ${total_cost_basis:.2f}")
                    
                    return total_cost_basis
        
        # For Coinbase transactions, prioritize using source price data
        if transaction['institution'] == 'coinbase' and pd.notna(transaction['price']):
            # Calculate cost basis using price per unit
            price_per_unit = float(transaction['price'])
            subtotal = quantity * price_per_unit
            fees = abs(float(transaction["fees"])) if pd.notna(transaction["fees"]) else 0.0
            cost_basis = subtotal + fees
            
            print(f"\nUsing source price data for {transaction['institution']} {transaction['type']}:")
            print(f"  Asset: {asset}")
            print(f"  Date: {transaction['timestamp']}")
            print(f"  Source price per unit: ${price_per_unit:.4f}")
            print(f"  Quantity: {quantity:.8f}")
            print(f"  Subtotal: ${subtotal:.2f}")
            print(f"  Fees: ${fees:.2f}")
            print(f"  Total cost basis: ${cost_basis:.2f}")
            
            return cost_basis
        
        # For Binance US transfer-out transactions, calculate cost basis from previous acquisitions
        if transaction['type'] == 'transfer_out':
            # Try to get price from database first for Gemini transactions
            if transaction['institution'] == 'gemini':
                # Try to get market price from price service
                transfer_date = transaction["timestamp"].replace(tzinfo=None)
                prices_df = price_service.get_multi_asset_prices(
                    [asset], 
                    transfer_date,
                    transfer_date
                )
                
                if not prices_df.empty:
                    market_price_per_unit = float(prices_df.iloc[0]["price"])
                    subtotal = quantity * market_price_per_unit
                    fees = abs(float(transaction["fees"])) if pd.notna(transaction["fees"]) else 0.0
                    cost_basis = subtotal + fees
                    
                    print(f"\nUsing database price for Gemini {transaction['type']}:")
                    print(f"  Asset: {asset}")
                    print(f"  Date: {transaction['timestamp']}")
                    print(f"  Database price per unit: ${market_price_per_unit:.4f}")
                    print(f"  Quantity: {quantity:.8f}")
                    print(f"  Subtotal: ${subtotal:.2f}")
                    print(f"  Fees: ${fees:.2f}")
                    print(f"  Total cost basis: ${cost_basis:.2f}")
                    print(f"  Data source: {prices_df.iloc[0].get('source', 'unknown')}")
                    
                    return cost_basis
                
                # If price database lookup failed, only then fall back to the hard-coded price
                if pd.notna(transaction['price']):
                    price_per_unit = float(transaction['price'])
                    subtotal = quantity * price_per_unit
                    fees = abs(float(transaction["fees"])) if pd.notna(transaction["fees"]) else 0.0
                    cost_basis = subtotal + fees
                    
                    print(f"\nFalling back to hardcoded price for Gemini {transaction['type']}:")
                    print(f"  Asset: {asset}")
                    print(f"  Date: {transaction['timestamp']}")
                    print(f"  Fallback price per unit: ${price_per_unit:.4f}")
                    print(f"  Quantity: {quantity:.8f}")
                    print(f"  Subtotal: ${subtotal:.2f}")
                    print(f"  Fees: ${fees:.2f}")
                    print(f"  Total cost basis: ${cost_basis:.2f}")
                    
                    return cost_basis
            
            # For other institutions or if Gemini price lookup failed, calculate from previous acquisitions
            cost_basis = self._calculate_sell_cost_basis(transaction)
            if asset == 'DOT':
                print(f"\nTransfer out cost basis calculation:")
                print(f"- Calculated from previous acquisitions: ${cost_basis:.2f}")
            return cost_basis
        
        # For unmatched transfer-in transactions, use price data
        if transaction['type'] == 'transfer_in':
            # First check if the transfer has a pre-calculated cost basis from transfer reconciliation
            if 'cost_basis' in transaction and pd.notna(transaction['cost_basis']) and float(transaction['cost_basis']) > 0:
                cost_basis = float(transaction['cost_basis'])
                print(f"\nUsing pre-calculated cost basis for {transaction['institution']} transfer_in:")
                print(f"  Asset: {asset}")
                print(f"  Date: {transaction['timestamp']}")
                print(f"  Cost basis: ${cost_basis:.2f}")
                return cost_basis
            
            # Get market price from price service
            transfer_date = transaction["timestamp"].replace(tzinfo=None)
            prices_df = price_service.get_multi_asset_prices(
                [asset], 
                transfer_date,
                transfer_date
            )
            
            market_price_per_unit = 0.0
            if not prices_df.empty:
                market_price_per_unit = float(prices_df.iloc[0]["price"])
                if asset == 'DOT':
                    print(f"\nUnmatched transfer market price calculation:")
                    print(f"- Date used for price lookup: {transfer_date}")
                    print(f"- Market price from price service: ${market_price_per_unit:.4f}")
            
            # Calculate cost basis using market price
            cost_basis = quantity * market_price_per_unit
            
            # Add fees
            fees = abs(float(transaction["fees"])) if pd.notna(transaction["fees"]) else 0.0
            cost_basis += fees
            
            if asset == 'DOT':
                print(f"- Final cost basis: ${cost_basis:.2f}")
                print(f"- Cost basis per unit: ${cost_basis/quantity if quantity > 0 else 0:.4f}")
        
            return cost_basis
        
        return 0.0

    def _calculate_sell_cost_basis(self, sell: pd.Series) -> float:
        """Calculate cost basis for a sell/transfer_out transaction by finding matching buy lots"""
        # Get quantity that needs to be matched with buys
        sell_quantity = abs(float(sell["quantity"]))
        asset = sell["asset"]
        
        if asset == 'DOT':
            print(f"\nDebug: Calculating cost basis for DOT {sell['type']}:")
            print(f"  Date: {sell['timestamp']}")
            print(f"  Exchange: {sell['institution']}")
            print(f"  Quantity: {sell_quantity}")
            print(f"  Price: {sell.get('price', 'N/A')}")
            print(f"  Transfer ID: {sell.get('transfer_id', 'None')}")
        
        # For transfer_out transactions with matched transfer_in, try to use the original cost basis
        if sell['type'] == 'transfer_out' and pd.notna(sell.get('transfer_id')) and 'cost_basis_per_unit' in sell and pd.notna(sell.get('cost_basis_per_unit')):
            cost_basis = float(sell['cost_basis_per_unit']) * sell_quantity
            print(f"\nUsing pre-calculated cost basis per unit for {sell['institution']} transfer:")
            print(f"  Asset: {asset}")
            print(f"  Cost basis per unit: ${float(sell['cost_basis_per_unit']):.4f}")
            print(f"  Quantity: {sell_quantity}")
            print(f"  Total cost basis: ${cost_basis:.2f}")
            return cost_basis
        
        # Find all acquisition transactions (buys, transfers in, staking rewards) before this sell
        acquisitions = self.transactions[
            (self.transactions["asset"] == sell["asset"]) &
            (self.transactions["type"].isin(["buy", "transfer_in", "staking_reward"])) &
            (self.transactions["timestamp"] <= sell["timestamp"])
        ].copy()
        
        # Sort acquisitions by timestamp (FIFO method)
        acquisitions = acquisitions.sort_values("timestamp")
        
        if asset == 'DOT':
            print("\nMatching acquisitions found:")
            for _, acq in acquisitions.iterrows():
                print(f"  - {acq['type']} on {acq['timestamp']}: {abs(float(acq['quantity']))} @ ${float(acq['price']) if pd.notna(acq['price']) else 0.0:.2f}")
                if 'cost_basis' in acq and pd.notna(acq['cost_basis']) and float(acq['cost_basis']) > 0:
                    cost_per_unit = float(acq['cost_basis']) / abs(float(acq['quantity'])) if abs(float(acq['quantity'])) > 0 else 0
                    print(f"    Cost basis: ${float(acq['cost_basis']):.2f}, Cost per unit: ${cost_per_unit:.4f}")
        
        total_cost_basis = 0.0
        remaining_quantity = sell_quantity
        
        # First prioritize using transfer_in transactions with pre-calculated cost basis
        # This ensures cost basis is carried over from previous exchanges
        priority_acquisitions = acquisitions[
            (acquisitions["type"] == "transfer_in") & 
            acquisitions['cost_basis'].notna() & 
            (acquisitions['cost_basis'] > 0)
        ].copy()
        
        if not priority_acquisitions.empty and asset != "USDC":
            print(f"\nUsing prioritized transfer_in transactions with pre-calculated cost basis for {asset}")
            for _, acquisition in priority_acquisitions.iterrows():
                if remaining_quantity <= 0:
                    break
                    
                acquisition_quantity = abs(float(acquisition["quantity"]))
                acquisition_cost_basis = float(acquisition["cost_basis"])
                
                # Calculate cost basis per unit
                cost_basis_per_unit = acquisition_cost_basis / acquisition_quantity if acquisition_quantity > 0 else 0.0
                
                # Determine how much of this lot to use
                lot_quantity = min(remaining_quantity, acquisition_quantity)
                lot_cost_basis = lot_quantity * cost_basis_per_unit
                
                if asset == 'DOT':
                    print(f"\nUsing lot from transfer_in on {acquisition['timestamp']} from {acquisition['institution']}:")
                    print(f"  Quantity used: {lot_quantity} of {acquisition_quantity}")
                    print(f"  Cost basis per unit: ${cost_basis_per_unit:.4f}")
                    print(f"  Lot cost basis: ${lot_cost_basis:.2f}")
                
                # Add to total cost basis
                total_cost_basis += lot_cost_basis
                
                # Update remaining quantity and remove the used acquisition from all acquisitions
                remaining_quantity -= lot_quantity
                acquisitions = acquisitions[acquisitions.index != acquisition.name]
        
        # Process remaining acquisitions if needed (buys, staking rewards, and transfers without pre-calculated cost basis)
        while remaining_quantity > 0 and not acquisitions.empty:
            acquisition = acquisitions.iloc[0]
            acquisition_quantity = abs(float(acquisition["quantity"]))
            
            # Handle cost basis based on transaction type
            if acquisition["type"] == "staking_reward":
                # Get market price at time of staking reward
                reward_date = acquisition["timestamp"].replace(tzinfo=None)
                prices_df = price_service.get_multi_asset_prices(
                    [acquisition["asset"]], 
                    reward_date,
                    reward_date
                )
                
                if not prices_df.empty:
                    acquisition_price = float(prices_df.iloc[0]["price"])
                    acquisition_subtotal = acquisition_quantity * acquisition_price
                    acquisition_fees = 0.0  # Staking rewards typically have no fees
                    acquisition_cost_basis = acquisition_subtotal
                    
                    if acquisition["asset"] == 'DOT':
                        print(f"\nStaking reward cost basis calculation:")
                        print(f"- Date: {reward_date}")
                        print(f"- Market price: ${acquisition_price:.4f}")
                        print(f"- Quantity: {acquisition_quantity:.8f}")
                        print(f"- Cost basis: ${acquisition_cost_basis:.2f}")
                else:
                    # Fallback to zero if no price data available
                    acquisition_price = 0.0
                    acquisition_subtotal = 0.0
                    acquisition_fees = 0.0
                    acquisition_cost_basis = 0.0
            elif acquisition["type"] == "transfer_in" and 'cost_basis' in acquisition and pd.notna(acquisition['cost_basis']) and float(acquisition['cost_basis']) > 0:
                # Use pre-calculated cost basis for transfer_in transactions (already handled above, but this is a safeguard)
                acquisition_cost_basis = float(acquisition['cost_basis'])
                if acquisition["asset"] == 'DOT':
                    print(f"\nUsing pre-calculated cost basis for transfer_in acquisition:")
                    print(f"- Date: {acquisition['timestamp']}")
                    print(f"- Exchange: {acquisition['institution']}")
                    print(f"- Pre-calculated cost basis: ${acquisition_cost_basis:.2f}")
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
            
            if asset == 'DOT':
                print(f"\nUsing lot from {acquisition['type']} on {acquisition['timestamp']}:")
                print(f"  Quantity used: {lot_quantity}")
                print(f"  Cost basis per unit: ${cost_basis_per_unit:.2f}")
                print(f"  Lot cost basis: ${lot_cost_basis:.2f}")
            
            # Add to total cost basis
            total_cost_basis += lot_cost_basis
            
            # Update remaining quantity and remove used acquisition lot
            remaining_quantity -= lot_quantity
            acquisitions = acquisitions.iloc[1:]
        
        if asset == 'DOT':
            print(f"\nFinal cost basis calculation:")
            print(f"  Total cost basis: ${total_cost_basis:.2f}")
            print(f"  Cost basis per unit: ${total_cost_basis/sell_quantity if sell_quantity > 0 else 0:.2f}")
        
        return total_cost_basis

    def get_all_transactions(self) -> pd.DataFrame:
        """Get all transactions"""
        return self.transactions.copy()
        
    def get_portfolio_summary(self) -> Dict:
        """Get portfolio summary metrics"""
        return {
            "total_value": 0.0,
            "total_cost_basis": 0.0,
            "total_unrealized_pl": 0.0
        }
        
    def get_asset_allocation(self) -> pd.DataFrame:
        """Get current asset allocation"""
        return pd.DataFrame(columns=["asset", "value", "percentage"])
        
    def get_recent_transactions(self) -> pd.DataFrame:
        """Get recent transactions"""
        return self.transactions.tail(5).copy() 