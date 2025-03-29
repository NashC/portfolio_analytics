import pandas as pd
from analytics import calculate_cost_basis_fifo, calculate_cost_basis_avg

def test_calculate_cost_basis_fifo():
    # Create sample transactions.
    data = {
        "timestamp": pd.to_datetime(["2023-01-01", "2023-01-05"]),
        "asset": ["AAPL", "AAPL"],
        "type": ["buy", "sell"],
        "quantity": [10, 5],
        "price": [150, 155],
        "fees": [1, 1],
        "currency": ["USD", "USD"]
    }
    transactions = pd.DataFrame(data)
    
    fifo_result = calculate_cost_basis_fifo(transactions)
    # Since this is a stub, simply verify the output is a DataFrame.
    assert isinstance(fifo_result, pd.DataFrame)

def test_calculate_cost_basis_avg():
    data = {
        "timestamp": pd.to_datetime(["2023-01-01", "2023-01-05"]),
        "asset": ["AAPL", "AAPL"],
        "type": ["buy", "sell"],
        "quantity": [10, 5],
        "price": [150, 155],
        "fees": [1, 1],
        "currency": ["USD", "USD"]
    }
    transactions = pd.DataFrame(data)
    
    avg_result = calculate_cost_basis_avg(transactions)
    assert isinstance(avg_result, pd.DataFrame)
