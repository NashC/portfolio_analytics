from datetime import datetime, date
from pathlib import Path
from typing import Optional, List

from sqlalchemy import create_engine, Column, Integer, String, Float, Date, DateTime, ForeignKey, UniqueConstraint, Index, Boolean, Text, Numeric
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.sql import func

from app.settings import settings

# Create declarative base
Base = declarative_base()

class User(Base):
    """User model for storing user information."""
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True)
    created_at = Column(DateTime, server_default=func.now())
    last_login = Column(DateTime)

    # Relationships
    accounts = relationship("Account", back_populates="user")
    transactions = relationship("Transaction", back_populates="user")

class Institution(Base):
    """Institution model for storing financial institutions."""
    __tablename__ = "institutions"

    institution_id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    type = Column(String)  # 'exchange', 'bank', 'broker', 'wallet'
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    accounts = relationship("Account", back_populates="institution")

class Account(Base):
    """Account model for storing user accounts at institutions."""
    __tablename__ = "accounts"

    account_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    institution_id = Column(Integer, ForeignKey("institutions.institution_id"), nullable=False)
    account_number = Column(String)
    account_name = Column(String, nullable=False)
    account_type = Column(String)
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="accounts")
    institution = relationship("Institution", back_populates="accounts")
    transactions = relationship("Transaction", back_populates="account", foreign_keys="[Transaction.account_id]")
    positions = relationship("PositionDaily", back_populates="account")

class Asset(Base):
    """Asset model for storing cryptocurrency information."""
    __tablename__ = "assets"

    asset_id = Column(Integer, primary_key=True)
    symbol = Column(String, unique=True, nullable=False)
    name = Column(String)
    type = Column(String)  # 'crypto', 'stock', 'fiat', 'other'
    coingecko_id = Column(String)
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    prices = relationship("PriceData", back_populates="asset")
    transactions = relationship("Transaction", back_populates="asset")
    positions = relationship("PositionDaily", back_populates="asset")

class Transaction(Base):
    """Transaction model for storing financial transactions."""
    __tablename__ = "transactions"

    transaction_id = Column(String, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    account_id = Column(Integer, ForeignKey("accounts.account_id"), nullable=False)
    asset_id = Column(Integer, ForeignKey("assets.asset_id"), nullable=False)
    type = Column(String, nullable=False)  # 'buy', 'sell', 'transfer_in', 'transfer_out', 'staking_reward'
    quantity = Column(Numeric(18, 8), nullable=False)
    price = Column(Numeric(18, 8))
    fees = Column(Numeric(18, 8))
    timestamp = Column(DateTime, nullable=False)
    source_account_id = Column(Integer, ForeignKey("accounts.account_id"))
    destination_account_id = Column(Integer, ForeignKey("accounts.account_id"))
    transfer_id = Column(String)
    notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="transactions")
    account = relationship("Account", back_populates="transactions", foreign_keys=[account_id])
    asset = relationship("Asset", back_populates="transactions")

    # Indexes
    __table_args__ = (
        Index('ix_transactions_user_timestamp', 'user_id', 'timestamp'),
        Index('ix_transactions_asset_timestamp', 'asset_id', 'timestamp'),
        Index('ix_transactions_account_timestamp', 'account_id', 'timestamp'),
    )

class PositionDaily(Base):
    """Daily position tracking table for portfolio returns calculation."""
    __tablename__ = "position_daily"

    position_id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False)
    account_id = Column(Integer, ForeignKey("accounts.account_id"), nullable=False)
    asset_id = Column(Integer, ForeignKey("assets.asset_id"), nullable=False)
    quantity = Column(Numeric(18, 8), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    account = relationship("Account", back_populates="positions")
    asset = relationship("Asset", back_populates="positions")

    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint('date', 'account_id', 'asset_id', name='uix_position_daily_date_account_asset'),
        Index('ix_position_daily_asset_date', 'asset_id', 'date'),
        Index('ix_position_daily_account_date', 'account_id', 'date'),
        Index('ix_position_daily_date', 'date'),
    )

class DataSource(Base):
    """Data source model for tracking price data providers."""
    __tablename__ = "data_sources"

    source_id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    type = Column(String)  # 'exchange', 'broker', 'data_provider', 'aggregator'
    priority = Column(Integer, default=0)
    api_key = Column(Text)
    api_secret = Column(Text)
    base_url = Column(String)
    rate_limit = Column(Integer)
    last_request = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    prices = relationship("PriceData", back_populates="source")

class PriceData(Base):
    """Price data model for storing historical price information."""
    __tablename__ = "price_data"

    price_id = Column(Integer, primary_key=True)
    asset_id = Column(Integer, ForeignKey("assets.asset_id"), nullable=False)
    source_id = Column(Integer, ForeignKey("data_sources.source_id"), nullable=False)
    date = Column(Date, nullable=False)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)
    market_cap = Column(Float)
    total_supply = Column(Float)
    circulating_supply = Column(Float)
    price_change_24h = Column(Float)
    price_change_percentage_24h = Column(Float)
    raw_data = Column(Text)  # JSON data
    confidence_score = Column(Float, default=1.0)
    last_updated = Column(DateTime, server_default=func.now())

    # Relationships
    asset = relationship("Asset", back_populates="prices")
    source = relationship("DataSource", back_populates="prices")

    # Constraints
    __table_args__ = (
        UniqueConstraint('asset_id', 'source_id', 'date', name='uix_price_data_asset_source_date'),
        Index('ix_price_data_asset_date', 'asset_id', 'date'),
        Index('ix_price_data_source', 'source_id'),
    )

class AssetSourceMapping(Base):
    """Mapping between assets and data sources."""
    __tablename__ = "asset_source_mappings"

    mapping_id = Column(Integer, primary_key=True)
    asset_id = Column(Integer, ForeignKey("assets.asset_id"), nullable=False)
    source_id = Column(Integer, ForeignKey("data_sources.source_id"), nullable=False)
    source_symbol = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    last_successful_fetch = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    asset = relationship("Asset")
    source = relationship("DataSource")

    # Constraints
    __table_args__ = (
        UniqueConstraint('asset_id', 'source_id', name='uix_asset_source_mapping'),
        Index('ix_asset_source_mapping_asset', 'asset_id'),
        Index('ix_asset_source_mapping_source', 'source_id'),
    )

# Create engine and session factory
engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Initialize the database by creating all tables."""
    Base.metadata.create_all(bind=engine)

def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close() 