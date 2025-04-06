from ingestion import ingest_csv
import yaml

# Load config
with open('config/schema_mapping.yaml', 'r') as f:
    config = yaml.safe_load(f)

# Read Coinbase data
df = ingest_csv('data/transaction_history/coinbase_transaction_history.csv', config['coinbase']['mapping'])

# Print DataFrame info
print('\nDataFrame columns:')
print(df.columns)

# Print raw transaction types
print('\nRaw transaction types before normalization:')
print(df['Transaction Type'].value_counts()) 