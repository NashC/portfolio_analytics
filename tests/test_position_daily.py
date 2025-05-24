"""
Tests for position_daily table and related functionality (AP-1).
"""
import pytest
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from app.db.base import Base, PositionDaily, Account, Asset, User, Institution


@pytest.fixture
def test_db():
    """Create a test database with SQLite in-memory."""
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session(), engine


def test_position_daily_table_exists(test_db):
    """Test that position_daily table exists with correct structure."""
    session, engine = test_db
    
    # Check that table exists
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    assert 'position_daily' in tables
    
    # Check table columns
    columns = inspector.get_columns('position_daily')
    column_names = [col['name'] for col in columns]
    
    expected_columns = [
        'position_id', 'date', 'account_id', 'asset_id', 
        'quantity', 'created_at', 'updated_at'
    ]
    
    for col in expected_columns:
        assert col in column_names, f"Column {col} not found in position_daily table"


def test_position_daily_indexes(test_db):
    """Test that required indexes exist on position_daily table."""
    session, engine = test_db
    
    inspector = inspect(engine)
    indexes = inspector.get_indexes('position_daily')
    index_names = [idx['name'] for idx in indexes]
    
    # Check for unique constraint (shows up as index in SQLite)
    unique_constraints = inspector.get_unique_constraints('position_daily')
    
    # Should have unique constraint on (date, account_id, asset_id)
    assert len(unique_constraints) > 0, "No unique constraints found"
    
    # Check that we have the expected constraint columns
    found_unique_constraint = False
    for constraint in unique_constraints:
        if set(constraint['column_names']) == {'date', 'account_id', 'asset_id'}:
            found_unique_constraint = True
            break
    
    assert found_unique_constraint, "Unique constraint on (date, account_id, asset_id) not found"


def test_position_daily_crud_operations(test_db):
    """Test basic CRUD operations on position_daily table."""
    session, engine = test_db
    
    # Create test data
    user = User(username="testuser", email="test@example.com")
    session.add(user)
    session.commit()
    
    institution = Institution(name="Test Exchange", type="exchange")
    session.add(institution)
    session.commit()
    
    account = Account(
        user_id=user.user_id,
        institution_id=institution.institution_id,
        account_name="Test Account"
    )
    session.add(account)
    session.commit()
    
    asset = Asset(symbol="BTC", name="Bitcoin", type="crypto")
    session.add(asset)
    session.commit()
    
    # Test CREATE
    position = PositionDaily(
        date=date(2024, 1, 1),
        account_id=account.account_id,
        asset_id=asset.asset_id,
        quantity=Decimal('1.5')
    )
    session.add(position)
    session.commit()
    
    # Test READ
    retrieved_position = session.query(PositionDaily).filter_by(
        date=date(2024, 1, 1),
        account_id=account.account_id,
        asset_id=asset.asset_id
    ).first()
    
    assert retrieved_position is not None
    assert retrieved_position.quantity == Decimal('1.5')
    assert retrieved_position.date == date(2024, 1, 1)
    
    # Test UPDATE
    retrieved_position.quantity = Decimal('2.0')
    session.commit()
    
    updated_position = session.query(PositionDaily).filter_by(
        position_id=retrieved_position.position_id
    ).first()
    assert updated_position.quantity == Decimal('2.0')
    
    # Test DELETE
    session.delete(updated_position)
    session.commit()
    
    deleted_position = session.query(PositionDaily).filter_by(
        position_id=retrieved_position.position_id
    ).first()
    assert deleted_position is None


def test_position_daily_unique_constraint(test_db):
    """Test that unique constraint on (date, account_id, asset_id) works."""
    session, engine = test_db
    
    # Create test data
    user = User(username="testuser2", email="test2@example.com")
    session.add(user)
    session.commit()
    
    institution = Institution(name="Test Exchange 2", type="exchange")
    session.add(institution)
    session.commit()
    
    account = Account(
        user_id=user.user_id,
        institution_id=institution.institution_id,
        account_name="Test Account 2"
    )
    session.add(account)
    session.commit()
    
    asset = Asset(symbol="ETH", name="Ethereum", type="crypto")
    session.add(asset)
    session.commit()
    
    # Create first position
    position1 = PositionDaily(
        date=date(2024, 1, 1),
        account_id=account.account_id,
        asset_id=asset.asset_id,
        quantity=Decimal('1.0')
    )
    session.add(position1)
    session.commit()
    
    # Try to create duplicate position (should fail)
    position2 = PositionDaily(
        date=date(2024, 1, 1),
        account_id=account.account_id,
        asset_id=asset.asset_id,
        quantity=Decimal('2.0')
    )
    session.add(position2)
    
    with pytest.raises(Exception):  # Should raise integrity error
        session.commit()


def test_position_daily_relationships(test_db):
    """Test that relationships work correctly."""
    session, engine = test_db
    
    # Create test data
    user = User(username="testuser3", email="test3@example.com")
    session.add(user)
    session.commit()
    
    institution = Institution(name="Test Exchange 3", type="exchange")
    session.add(institution)
    session.commit()
    
    account = Account(
        user_id=user.user_id,
        institution_id=institution.institution_id,
        account_name="Test Account 3"
    )
    session.add(account)
    session.commit()
    
    asset = Asset(symbol="ADA", name="Cardano", type="crypto")
    session.add(asset)
    session.commit()
    
    position = PositionDaily(
        date=date(2024, 1, 1),
        account_id=account.account_id,
        asset_id=asset.asset_id,
        quantity=Decimal('100.0')
    )
    session.add(position)
    session.commit()
    
    # Test relationships
    assert position.account == account
    assert position.asset == asset
    assert position in account.positions
    assert position in asset.positions 