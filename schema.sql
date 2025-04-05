-- Users table to store user information
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

-- Institutions table to store information about financial institutions
CREATE TABLE IF NOT EXISTS institutions (
    institution_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    type TEXT CHECK(type IN ('exchange', 'bank', 'broker', 'wallet')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Accounts table to store user accounts at different institutions
CREATE TABLE IF NOT EXISTS accounts (
    account_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    institution_id INTEGER NOT NULL,
    account_number TEXT,
    account_name TEXT NOT NULL,
    account_type TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (institution_id) REFERENCES institutions(institution_id)
);

-- Assets table to store information about different assets
CREATE TABLE IF NOT EXISTS assets (
    asset_id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT UNIQUE NOT NULL,
    name TEXT,
    type TEXT CHECK(type IN ('crypto', 'stock', 'fiat', 'other')),
    coingecko_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Data sources table to track different data providers
CREATE TABLE IF NOT EXISTS data_sources (
    source_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    type TEXT CHECK(type IN ('exchange', 'broker', 'data_provider', 'aggregator')),
    api_key TEXT,
    api_secret TEXT,
    base_url TEXT,
    rate_limit INTEGER,
    last_request TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Historical price data with improved structure
CREATE TABLE IF NOT EXISTS price_data (
    price_id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL,
    date DATE NOT NULL,
    open DECIMAL(18,8) NOT NULL,
    high DECIMAL(18,8) NOT NULL,
    low DECIMAL(18,8) NOT NULL,
    close DECIMAL(18,8) NOT NULL,
    volume DECIMAL(24,8),
    market_cap DECIMAL(24,2),
    total_supply DECIMAL(24,8),
    circulating_supply DECIMAL(24,8),
    price_change_24h DECIMAL(10,2),
    price_change_percentage_24h DECIMAL(10,2),
    source_id INTEGER NOT NULL,
    raw_data JSON,  -- Store complete raw response from source
    confidence_score DECIMAL(5,2),  -- Data quality score (0-100)
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (asset_id) REFERENCES assets(asset_id),
    FOREIGN KEY (source_id) REFERENCES data_sources(source_id),
    UNIQUE (asset_id, date, source_id)
);

-- Asset source mappings table to track which assets are available from which sources
CREATE TABLE IF NOT EXISTS asset_source_mappings (
    mapping_id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL,
    source_id INTEGER NOT NULL,
    source_symbol TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    last_successful_fetch TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (asset_id) REFERENCES assets(asset_id),
    FOREIGN KEY (source_id) REFERENCES data_sources(source_id),
    UNIQUE (asset_id, source_id)
);

-- Transactions table with enhanced tracking
CREATE TABLE IF NOT EXISTS transactions (
    transaction_id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    account_id INTEGER NOT NULL,
    asset_id INTEGER NOT NULL,
    type TEXT NOT NULL CHECK(type IN ('buy', 'sell', 'transfer_in', 'transfer_out', 'staking_reward')),
    quantity DECIMAL(18,8) NOT NULL,
    price DECIMAL(18,8),
    fees DECIMAL(18,8),
    timestamp TIMESTAMP NOT NULL,
    source_account_id INTEGER,
    destination_account_id INTEGER,
    transfer_id TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (account_id) REFERENCES accounts(account_id),
    FOREIGN KEY (asset_id) REFERENCES assets(asset_id),
    FOREIGN KEY (source_account_id) REFERENCES accounts(account_id),
    FOREIGN KEY (destination_account_id) REFERENCES accounts(account_id)
);

-- Cost basis tracking table
CREATE TABLE IF NOT EXISTS cost_basis (
    cost_basis_id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    asset_id INTEGER NOT NULL,
    method TEXT CHECK(method IN ('fifo', 'average')),
    quantity DECIMAL(18,8) NOT NULL,
    cost_basis DECIMAL(18,8) NOT NULL,
    acquisition_date TIMESTAMP NOT NULL,
    disposal_date TIMESTAMP,
    holding_period_days INTEGER,
    realized_gain_loss DECIMAL(18,8),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (asset_id) REFERENCES assets(asset_id)
);

-- Portfolio snapshots table for performance tracking
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    total_value DECIMAL(18,8) NOT NULL,
    base_currency TEXT DEFAULT 'USD',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- Portfolio holdings table (point-in-time asset positions)
CREATE TABLE IF NOT EXISTS portfolio_holdings (
    holding_id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER NOT NULL,
    asset_id INTEGER NOT NULL,
    quantity DECIMAL(18,8) NOT NULL,
    value_in_base DECIMAL(18,8) NOT NULL,
    cost_basis DECIMAL(18,8),
    unrealized_gain_loss DECIMAL(18,8),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (snapshot_id) REFERENCES portfolio_snapshots(snapshot_id),
    FOREIGN KEY (asset_id) REFERENCES assets(asset_id)
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_price_data_asset_date ON price_data(asset_id, date);
CREATE INDEX IF NOT EXISTS idx_price_data_date ON price_data(date);
CREATE INDEX IF NOT EXISTS idx_price_data_close ON price_data(close);
CREATE INDEX IF NOT EXISTS idx_price_data_volume ON price_data(volume);
CREATE INDEX IF NOT EXISTS idx_price_data_source ON price_data(source_id);
CREATE INDEX IF NOT EXISTS idx_asset_source_mappings_asset ON asset_source_mappings(asset_id);
CREATE INDEX IF NOT EXISTS idx_asset_source_mappings_source ON asset_source_mappings(source_id);
CREATE INDEX IF NOT EXISTS idx_transactions_user ON transactions(user_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_transactions_asset ON transactions(asset_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_cost_basis_user ON cost_basis(user_id, asset_id, method);
CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_user ON portfolio_snapshots(user_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_portfolio_holdings_snapshot ON portfolio_holdings(snapshot_id, asset_id); 