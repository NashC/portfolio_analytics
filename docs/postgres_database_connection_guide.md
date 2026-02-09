# PostgreSQL Database Connection Guide

> **Note:** All credentials in this guide are placeholders. Set your actual database credentials via environment variables or a `.env` file. See [Environment Setup](#environment-setup) below.

## Database Overview
This guide provides instructions for connecting to the Asset Price Database PostgreSQL instance. The database contains financial market data including daily OHLCV (Open, High, Low, Close, Volume) data for stocks, ETFs, and cryptocurrencies.

## Connection Details

### Default Configuration (Docker Development)
```
Host: localhost
Port: 5432
Database: assetpricedb
Username: <your-username>
Password: <your-password>
```

### Connection String Format
```
postgresql://<your-username>:<your-password>@localhost:5432/assetpricedb
```

## Connection Methods

### 1. Using Python with SQLAlchemy (Recommended)

#### Install Dependencies
```bash
pip install sqlalchemy psycopg2-binary pandas
```

#### Basic Connection
```python
import os
from sqlalchemy import create_engine, text
import pandas as pd

# Connection string
DATABASE_URL = os.environ["DATABASE_URL"]  # e.g. postgresql://<your-username>:<your-password>@localhost:5432/assetpricedb

# Create engine
engine = create_engine(DATABASE_URL)

# Test connection
with engine.connect() as conn:
    result = conn.execute(text("SELECT version()"))
    print(result.fetchone())
```

#### Using the Project's Database Client
```python
from app.db_client import StockDB

# Initialize client (uses .env file or default connection)
db = StockDB()

# Or with explicit connection string
db = StockDB(dsn="postgresql://<your-username>:<your-password>@localhost:5432/assetpricedb")

# Test connection
health = db.health_check()
print(f"Database status: {health['status']}")
```

### 2. Using psql Command Line

#### Direct Connection
```bash
psql -h localhost -p 5432 -U <your-username> -d assetpricedb
# Enter password when prompted
```

#### Using Connection String
```bash
psql "postgresql://<your-username>:<your-password>@localhost:5432/assetpricedb"
```

#### Environment Variable Method
```bash
export PGHOST=localhost
export PGPORT=5432
export PGDATABASE=assetpricedb
export PGUSER=<your-username>
export PGPASSWORD=<your-password>

psql
```

### 3. Using Python with psycopg2

```python
import psycopg2
import pandas as pd

# Connection parameters
conn_params = {
    'host': 'localhost',
    'port': 5432,
    'database': 'assetpricedb',
    'user': '<your-username>',
    'password': '<your-password>'
}

# Connect and query
with psycopg2.connect(**conn_params) as conn:
    df = pd.read_sql("SELECT * FROM price_gold LIMIT 10", conn)
    print(df.head())
```

### 4. Using DBeaver or Other GUI Tools

#### Connection Settings
- **Connection Type**: PostgreSQL
- **Server Host**: localhost
- **Port**: 5432
- **Database**: assetpricedb
- **Username**: `<your-username>`
- **Password**: `<your-password>`

#### Test Query
```sql
SELECT 
    symbol,
    price_date,
    close_price,
    volume
FROM price_gold 
WHERE symbol = 'AAPL' 
ORDER BY price_date DESC 
LIMIT 10;
```

## Database Schema Overview

### Key Tables
- **`asset`**: Master table of all tradeable instruments
- **`price_raw`**: Raw price data with full lineage
- **`price_gold`**: Materialized view with deduplicated, analysis-ready data
- **`batch_meta`**: ETL batch tracking and metadata
- **`data_source`**: Data provider information

### Important Views
- **`price_gold`**: Primary view for analytics (deduplicated daily prices)
- **`asset_summary`**: Trading statistics per asset
- **`data_quality_summary`**: Quality metrics by source

## Common Query Patterns

### Get Available Symbols
```sql
SELECT symbol, asset_type, exchange, company_name 
FROM asset 
WHERE is_active = true 
ORDER BY symbol;
```

### Get Price Data for Analysis
```sql
SELECT 
    symbol,
    price_date,
    open_price,
    high_price,
    low_price,
    close_price,
    volume,
    adj_close_price
FROM price_gold 
WHERE symbol IN ('AAPL', 'MSFT', 'GOOGL')
    AND price_date >= '2024-01-01'
ORDER BY symbol, price_date;
```

### Get Latest Prices
```sql
SELECT DISTINCT ON (symbol)
    symbol,
    price_date,
    close_price,
    volume
FROM price_gold
ORDER BY symbol, price_date DESC;
```

### Check Data Quality
```sql
SELECT 
    bm.batch_name,
    bm.status,
    bm.quality_score,
    bm.row_count,
    bm.start_time
FROM batch_meta bm
ORDER BY bm.start_time DESC
LIMIT 20;
```

## Environment Setup

### Using .env File (Recommended)
Create a `.env` file in your project root:
```bash
DATABASE_URL=postgresql://<your-username>:<your-password>@localhost:5432/assetpricedb
QC_MIN_SCORE=75.0
LOG_LEVEL=INFO
```

### Using Environment Variables
```bash
export DATABASE_URL="postgresql://<your-username>:<your-password>@localhost:5432/assetpricedb"
export QC_MIN_SCORE=75.0
export LOG_LEVEL=INFO
```

## Docker Setup

### Start Database Services
```bash
# Start PostgreSQL and PGAdmin
docker-compose up -d

# Check services are running
docker-compose ps
```

### Access PGAdmin Web Interface
- **URL**: http://localhost:8080
- **Email**: `<your-email>`
- **Password**: `<your-admin-password>`

#### Add Server in PGAdmin
- **Name**: Asset Price DB
- **Host**: postgres (Docker internal network)
- **Port**: 5432
- **Database**: assetpricedb
- **Username**: `<your-username>`
- **Password**: `<your-password>`

## Troubleshooting

### Connection Refused
```bash
# Check if Docker services are running
docker-compose ps

# Check PostgreSQL logs
docker-compose logs postgres

# Restart services if needed
docker-compose restart
```

### Authentication Failed
- Verify username/password match your `.env` configuration
- Check if database exists: `assetpricedb`
- Ensure PostgreSQL is accepting connections

### Permission Denied
```bash
# Check database permissions
psql -h localhost -U <your-username> -d assetpricedb -c "\du"
```

### Performance Issues
```sql
-- Check active connections
SELECT count(*) FROM pg_stat_activity WHERE datname = 'assetpricedb';

-- Check table sizes
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables 
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

## Security Notes

### Development Environment
- Default credentials are for development only
- Database is exposed on localhost:5432
- No SSL/TLS encryption configured

### Production Considerations
- Change default passwords
- Enable SSL/TLS encryption
- Restrict network access
- Use connection pooling
- Monitor connection limits

## Sample Data

The database includes sample data for testing:
- **Stocks**: ABNB, ADBE, CRM, JNJ
- **Cryptocurrencies**: BTC, ETH

### Quick Data Check
```sql
-- Count records by asset type
SELECT 
    a.asset_type,
    COUNT(*) as price_records
FROM price_gold pg
JOIN asset a ON pg.asset_id = a.asset_id
GROUP BY a.asset_type;

-- Date range coverage
SELECT 
    MIN(price_date) as earliest_date,
    MAX(price_date) as latest_date,
    COUNT(DISTINCT price_date) as trading_days
FROM price_gold;
```

## API Access (Alternative)

If you prefer REST API access over direct database connections:

```bash
# Start FastAPI server
uvicorn app.fastapi_server:app --reload

# Access API documentation
# http://localhost:8000/docs
```

### API Examples
```bash
# Get symbols
curl "http://localhost:8000/symbols"

# Get price data
curl "http://localhost:8000/prices?symbols=AAPL&start_date=2024-01-01&end_date=2024-01-31"

# Health check
curl "http://localhost:8000/health"
``` 