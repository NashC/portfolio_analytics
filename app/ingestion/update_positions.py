"""
Trade-to-Position engine for updating daily positions from transaction data (AP-2).

This module provides functionality to:
1. Read new transactions from the transaction table
2. Calculate daily positions by forward-filling each day
3. Handle buys, sells (negative qty), and same-day multiple trades
4. Update the position_daily table incrementally
"""

import argparse
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
import logging

from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import Session

from app.db.base import Transaction, PositionDaily, Account, Asset
from app.db.session import SessionLocal

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PositionEngine:
    """Engine for calculating and updating daily positions from transactions."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def get_transactions_since(self, start_date: date, account_ids: Optional[List[int]] = None) -> List[Transaction]:
        """Get all transactions since the given date."""
        query = select(Transaction).where(
            func.date(Transaction.timestamp) >= start_date
        ).order_by(Transaction.timestamp)
        
        if account_ids:
            query = query.where(Transaction.account_id.in_(account_ids))
        
        return self.session.execute(query).scalars().all()
    
    def get_last_position_date(self, account_id: int, asset_id: int) -> Optional[date]:
        """Get the last date for which we have position data for an account/asset."""
        result = self.session.execute(
            select(func.max(PositionDaily.date)).where(
                and_(
                    PositionDaily.account_id == account_id,
                    PositionDaily.asset_id == asset_id
                )
            )
        ).scalar()
        return result
    
    def get_position_on_date(self, account_id: int, asset_id: int, target_date: date) -> Decimal:
        """Get the position quantity for an account/asset on a specific date."""
        result = self.session.execute(
            select(PositionDaily.quantity).where(
                and_(
                    PositionDaily.account_id == account_id,
                    PositionDaily.asset_id == asset_id,
                    PositionDaily.date == target_date
                )
            )
        ).scalar()
        return result or Decimal('0')
    
    def calculate_position_changes(self, transactions: List[Transaction]) -> Dict[Tuple[int, int, date], Decimal]:
        """
        Calculate position changes by account/asset/date from transactions.
        
        Returns:
            Dict mapping (account_id, asset_id, date) -> net_quantity_change
        """
        position_changes = {}
        
        for txn in transactions:
            txn_date = txn.timestamp.date()
            key = (txn.account_id, txn.asset_id, txn_date)
            
            # Calculate quantity change based on transaction type
            if txn.type in ['buy', 'transfer_in', 'staking_reward']:
                quantity_change = txn.quantity
            elif txn.type in ['sell', 'transfer_out']:
                quantity_change = -txn.quantity
            else:
                logger.warning(f"Unknown transaction type: {txn.type} for transaction {txn.transaction_id}")
                continue
            
            # Accumulate changes for the same account/asset/date
            if key in position_changes:
                position_changes[key] += quantity_change
            else:
                position_changes[key] = quantity_change
        
        return position_changes
    
    def forward_fill_positions(self, account_id: int, asset_id: int, start_date: date, end_date: date):
        """Forward fill positions for an account/asset between start and end dates."""
        current_date = start_date
        last_quantity = self.get_position_on_date(account_id, asset_id, start_date - timedelta(days=1))
        
        while current_date <= end_date:
            # Check if we already have a position for this date
            existing_position = self.session.execute(
                select(PositionDaily).where(
                    and_(
                        PositionDaily.account_id == account_id,
                        PositionDaily.asset_id == asset_id,
                        PositionDaily.date == current_date
                    )
                )
            ).scalar_one_or_none()
            
            if not existing_position:
                # Create new position entry with forward-filled quantity
                new_position = PositionDaily(
                    date=current_date,
                    account_id=account_id,
                    asset_id=asset_id,
                    quantity=last_quantity
                )
                self.session.add(new_position)
            else:
                # Update last_quantity for next iteration
                last_quantity = existing_position.quantity
            
            current_date += timedelta(days=1)
    
    def update_positions_from_transactions(self, start_date: date, end_date: Optional[date] = None) -> int:
        """
        Update position_daily table from transactions starting from start_date.
        
        Args:
            start_date: Date to start processing from
            end_date: Date to end processing (defaults to today)
        
        Returns:
            Number of position records updated/created
        """
        if end_date is None:
            end_date = date.today()
        
        logger.info(f"Updating positions from {start_date} to {end_date}")
        
        # Get all transactions in the date range
        transactions = self.get_transactions_since(start_date)
        logger.info(f"Found {len(transactions)} transactions to process")
        
        if not transactions:
            logger.info("No transactions found, nothing to update")
            return 0
        
        # Calculate position changes by account/asset/date
        position_changes = self.calculate_position_changes(transactions)
        logger.info(f"Calculated changes for {len(position_changes)} account/asset/date combinations")
        
        records_updated = 0
        
        # Group by account/asset to process each combination
        account_asset_pairs = set((account_id, asset_id) for account_id, asset_id, _ in position_changes.keys())
        
        for account_id, asset_id in account_asset_pairs:
            logger.info(f"Processing positions for account {account_id}, asset {asset_id}")
            
            # Get all dates with changes for this account/asset
            dates_with_changes = [
                txn_date for acc_id, ast_id, txn_date in position_changes.keys()
                if acc_id == account_id and ast_id == asset_id
            ]
            dates_with_changes.sort()
            
            # Get the starting position (from the day before the first change)
            first_change_date = min(dates_with_changes)
            last_position_date = self.get_last_position_date(account_id, asset_id)
            
            # Determine starting quantity
            if last_position_date and last_position_date < first_change_date:
                current_quantity = self.get_position_on_date(account_id, asset_id, last_position_date)
                # Forward fill from last position date to first change date
                fill_start = last_position_date + timedelta(days=1)
                if fill_start < first_change_date:
                    self.forward_fill_positions(account_id, asset_id, fill_start, first_change_date - timedelta(days=1))
            else:
                current_quantity = Decimal('0')
            
            # Process each date with changes
            for change_date in dates_with_changes:
                key = (account_id, asset_id, change_date)
                quantity_change = position_changes[key]
                current_quantity += quantity_change
                
                # Update or create position record
                existing_position = self.session.execute(
                    select(PositionDaily).where(
                        and_(
                            PositionDaily.account_id == account_id,
                            PositionDaily.asset_id == asset_id,
                            PositionDaily.date == change_date
                        )
                    )
                ).scalar_one_or_none()
                
                if existing_position:
                    existing_position.quantity = current_quantity
                    existing_position.updated_at = datetime.now()
                else:
                    new_position = PositionDaily(
                        date=change_date,
                        account_id=account_id,
                        asset_id=asset_id,
                        quantity=current_quantity
                    )
                    self.session.add(new_position)
                
                records_updated += 1
            
            # Forward fill from last change date to end_date
            last_change_date = max(dates_with_changes)
            if last_change_date < end_date:
                self.forward_fill_positions(
                    account_id, asset_id, 
                    last_change_date + timedelta(days=1), 
                    end_date
                )
                # Count the forward-filled days
                records_updated += (end_date - last_change_date).days
        
        # Commit all changes
        self.session.commit()
        logger.info(f"Successfully updated {records_updated} position records")
        
        return records_updated


def update_positions_cli():
    """Command-line interface for updating positions."""
    parser = argparse.ArgumentParser(description='Update daily positions from transactions')
    parser.add_argument('--start', type=str, required=True, 
                       help='Start date in YYYY-MM-DD format')
    parser.add_argument('--end', type=str, 
                       help='End date in YYYY-MM-DD format (defaults to today)')
    parser.add_argument('--account-ids', type=str, 
                       help='Comma-separated list of account IDs to process')
    
    args = parser.parse_args()
    
    # Parse dates
    start_date = datetime.strptime(args.start, '%Y-%m-%d').date()
    end_date = datetime.strptime(args.end, '%Y-%m-%d').date() if args.end else date.today()
    
    # Parse account IDs if provided
    account_ids = None
    if args.account_ids:
        account_ids = [int(x.strip()) for x in args.account_ids.split(',')]
    
    # Create session and engine
    session = SessionLocal()
    try:
        engine = PositionEngine(session)
        records_updated = engine.update_positions_from_transactions(start_date, end_date)
        print(f"Successfully updated {records_updated} position records")
    except Exception as e:
        logger.error(f"Error updating positions: {e}")
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    update_positions_cli() 