"""
Tests for the position engine (AP-2).
"""
import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base, Transaction, PositionDaily, Account, Asset, User, Institution
from app.ingestion.update_positions import PositionEngine


@pytest.fixture
def test_db():
    """Create a test database with SQLite in-memory."""
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session(), engine


@pytest.fixture
def sample_data(test_db):
    """Create sample data for testing."""
    session, engine = test_db
    
    # Create user
    user = User(username="testuser", email="test@example.com")
    session.add(user)
    session.commit()
    
    # Create institution
    institution = Institution(name="Test Exchange", type="exchange")
    session.add(institution)
    session.commit()
    
    # Create account
    account = Account(
        user_id=user.user_id,
        institution_id=institution.institution_id,
        account_name="Test Account"
    )
    session.add(account)
    session.commit()
    
    # Create assets
    btc = Asset(symbol="BTC", name="Bitcoin", type="crypto")
    eth = Asset(symbol="ETH", name="Ethereum", type="crypto")
    session.add_all([btc, eth])
    session.commit()
    
    return {
        'session': session,
        'user': user,
        'account': account,
        'btc': btc,
        'eth': eth
    }


def test_position_engine_basic_buy_sell(sample_data):
    """Test basic buy and sell transactions."""
    session = sample_data['session']
    account = sample_data['account']
    btc = sample_data['btc']
    
    # Create transactions
    transactions = [
        Transaction(
            transaction_id="buy1",
            user_id=account.user_id,
            account_id=account.account_id,
            asset_id=btc.asset_id,
            type="buy",
            quantity=Decimal('1.0'),
            price=Decimal('50000'),
            timestamp=datetime(2024, 1, 1, 10, 0, 0)
        ),
        Transaction(
            transaction_id="buy2",
            user_id=account.user_id,
            account_id=account.account_id,
            asset_id=btc.asset_id,
            type="buy",
            quantity=Decimal('0.5'),
            price=Decimal('51000'),
            timestamp=datetime(2024, 1, 2, 10, 0, 0)
        ),
        Transaction(
            transaction_id="sell1",
            user_id=account.user_id,
            account_id=account.account_id,
            asset_id=btc.asset_id,
            type="sell",
            quantity=Decimal('0.3'),
            price=Decimal('52000'),
            timestamp=datetime(2024, 1, 3, 10, 0, 0)
        )
    ]
    
    session.add_all(transactions)
    session.commit()
    
    # Run position engine
    engine = PositionEngine(session)
    records_updated = engine.update_positions_from_transactions(
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 5)
    )
    
    # Verify positions
    positions = session.query(PositionDaily).filter_by(
        account_id=account.account_id,
        asset_id=btc.asset_id
    ).order_by(PositionDaily.date).all()
    
    assert len(positions) == 5  # 5 days
    assert positions[0].quantity == Decimal('1.0')  # Jan 1: +1.0
    assert positions[1].quantity == Decimal('1.5')  # Jan 2: +0.5
    assert positions[2].quantity == Decimal('1.2')  # Jan 3: -0.3
    assert positions[3].quantity == Decimal('1.2')  # Jan 4: forward fill
    assert positions[4].quantity == Decimal('1.2')  # Jan 5: forward fill
    
    assert records_updated > 0


def test_position_engine_same_day_multiple_trades(sample_data):
    """Test multiple trades on the same day."""
    session = sample_data['session']
    account = sample_data['account']
    eth = sample_data['eth']
    
    # Create multiple transactions on the same day
    transactions = [
        Transaction(
            transaction_id="buy1",
            user_id=account.user_id,
            account_id=account.account_id,
            asset_id=eth.asset_id,
            type="buy",
            quantity=Decimal('10.0'),
            timestamp=datetime(2024, 1, 1, 9, 0, 0)
        ),
        Transaction(
            transaction_id="buy2",
            user_id=account.user_id,
            account_id=account.account_id,
            asset_id=eth.asset_id,
            type="buy",
            quantity=Decimal('5.0'),
            timestamp=datetime(2024, 1, 1, 14, 0, 0)
        ),
        Transaction(
            transaction_id="sell1",
            user_id=account.user_id,
            account_id=account.account_id,
            asset_id=eth.asset_id,
            type="sell",
            quantity=Decimal('3.0'),
            timestamp=datetime(2024, 1, 1, 16, 0, 0)
        )
    ]
    
    session.add_all(transactions)
    session.commit()
    
    # Run position engine
    engine = PositionEngine(session)
    records_updated = engine.update_positions_from_transactions(
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 1)
    )
    
    # Verify position (should be net of all trades: 10 + 5 - 3 = 12)
    position = session.query(PositionDaily).filter_by(
        account_id=account.account_id,
        asset_id=eth.asset_id,
        date=date(2024, 1, 1)
    ).first()
    
    assert position is not None
    assert position.quantity == Decimal('12.0')


def test_position_engine_transfers(sample_data):
    """Test transfer transactions."""
    session = sample_data['session']
    account = sample_data['account']
    btc = sample_data['btc']
    
    # Create transfer transactions
    transactions = [
        Transaction(
            transaction_id="transfer_in1",
            user_id=account.user_id,
            account_id=account.account_id,
            asset_id=btc.asset_id,
            type="transfer_in",
            quantity=Decimal('2.0'),
            timestamp=datetime(2024, 1, 1, 10, 0, 0)
        ),
        Transaction(
            transaction_id="transfer_out1",
            user_id=account.user_id,
            account_id=account.account_id,
            asset_id=btc.asset_id,
            type="transfer_out",
            quantity=Decimal('0.5'),
            timestamp=datetime(2024, 1, 2, 10, 0, 0)
        )
    ]
    
    session.add_all(transactions)
    session.commit()
    
    # Run position engine
    engine = PositionEngine(session)
    engine.update_positions_from_transactions(
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 2)
    )
    
    # Verify positions
    positions = session.query(PositionDaily).filter_by(
        account_id=account.account_id,
        asset_id=btc.asset_id
    ).order_by(PositionDaily.date).all()
    
    assert len(positions) == 2
    assert positions[0].quantity == Decimal('2.0')  # Jan 1: +2.0 transfer in
    assert positions[1].quantity == Decimal('1.5')  # Jan 2: -0.5 transfer out


def test_position_engine_staking_rewards(sample_data):
    """Test staking reward transactions."""
    session = sample_data['session']
    account = sample_data['account']
    eth = sample_data['eth']
    
    # Create initial position and staking reward
    transactions = [
        Transaction(
            transaction_id="buy1",
            user_id=account.user_id,
            account_id=account.account_id,
            asset_id=eth.asset_id,
            type="buy",
            quantity=Decimal('32.0'),
            timestamp=datetime(2024, 1, 1, 10, 0, 0)
        ),
        Transaction(
            transaction_id="stake1",
            user_id=account.user_id,
            account_id=account.account_id,
            asset_id=eth.asset_id,
            type="staking_reward",
            quantity=Decimal('0.1'),
            timestamp=datetime(2024, 1, 2, 10, 0, 0)
        )
    ]
    
    session.add_all(transactions)
    session.commit()
    
    # Run position engine
    engine = PositionEngine(session)
    engine.update_positions_from_transactions(
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 2)
    )
    
    # Verify positions
    positions = session.query(PositionDaily).filter_by(
        account_id=account.account_id,
        asset_id=eth.asset_id
    ).order_by(PositionDaily.date).all()
    
    assert len(positions) == 2
    assert positions[0].quantity == Decimal('32.0')  # Jan 1: initial buy
    assert positions[1].quantity == Decimal('32.1')  # Jan 2: +0.1 staking reward


def test_position_engine_incremental_update(sample_data):
    """Test incremental updates (adding new transactions)."""
    session = sample_data['session']
    account = sample_data['account']
    btc = sample_data['btc']
    
    # Create initial transaction
    initial_txn = Transaction(
        transaction_id="buy1",
        user_id=account.user_id,
        account_id=account.account_id,
        asset_id=btc.asset_id,
        type="buy",
        quantity=Decimal('1.0'),
        timestamp=datetime(2024, 1, 1, 10, 0, 0)
    )
    session.add(initial_txn)
    session.commit()
    
    # Run initial position update
    engine = PositionEngine(session)
    engine.update_positions_from_transactions(
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 2)
    )
    
    # Verify initial position
    initial_positions = session.query(PositionDaily).filter_by(
        account_id=account.account_id,
        asset_id=btc.asset_id
    ).count()
    assert initial_positions == 2  # Jan 1 and Jan 2
    
    # Add new transaction
    new_txn = Transaction(
        transaction_id="buy2",
        user_id=account.user_id,
        account_id=account.account_id,
        asset_id=btc.asset_id,
        type="buy",
        quantity=Decimal('0.5'),
        timestamp=datetime(2024, 1, 3, 10, 0, 0)
    )
    session.add(new_txn)
    session.commit()
    
    # Run incremental update
    engine.update_positions_from_transactions(
        start_date=date(2024, 1, 3),
        end_date=date(2024, 1, 3)
    )
    
    # Verify updated positions
    final_position = session.query(PositionDaily).filter_by(
        account_id=account.account_id,
        asset_id=btc.asset_id,
        date=date(2024, 1, 3)
    ).first()
    
    assert final_position is not None
    assert final_position.quantity == Decimal('1.5')  # 1.0 + 0.5


def test_position_engine_empty_transactions(sample_data):
    """Test behavior with no transactions."""
    session = sample_data['session']
    
    # Run position engine with no transactions
    engine = PositionEngine(session)
    records_updated = engine.update_positions_from_transactions(
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 1)
    )
    
    # Should return 0 records updated
    assert records_updated == 0
    
    # Should have no position records
    positions = session.query(PositionDaily).all()
    assert len(positions) == 0 