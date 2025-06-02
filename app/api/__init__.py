"""
Portfolio Analytics REST API

This module provides REST endpoints for portfolio valuation and returns.
"""

from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.responses import JSONResponse
from datetime import date, datetime
from typing import Optional, List, Dict, Any
import pandas as pd
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.base import engine
from app.valuation import get_portfolio_value, get_value_series
from app.analytics.portfolio import calculate_returns

app = FastAPI(title="Portfolio Analytics API", version="1.0.0")


@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    print("🚀 Portfolio Analytics API starting up...")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown."""
    print("🛑 Portfolio Analytics API shutting down...")
    # Dispose of database engine to close all connections
    engine.dispose()
    print("✅ Database connections closed")


@app.get("/portfolio/value")
async def get_portfolio_value_endpoint(
    target_date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format"),
    account_ids: Optional[List[int]] = Query(None, description="List of account IDs to filter by"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get portfolio value for a specific date.
    
    Args:
        target_date: Date to get portfolio value for (defaults to today)
        account_ids: Optional list of account IDs to filter by
        
    Returns:
        JSON with portfolio value information
    """
    # Parse target date
    if target_date:
        try:
            parsed_date = datetime.strptime(target_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    else:
        parsed_date = date.today()
    
    try:
        # Get portfolio value
        portfolio_value = get_portfolio_value(parsed_date, account_ids)
        
        return {
            "date": parsed_date.isoformat(),
            "portfolio_value": portfolio_value,
            "account_ids": account_ids,
            "currency": "USD"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating portfolio value: {str(e)}")


@app.get("/portfolio/value/series")
async def get_portfolio_value_series(
    start_date: str = Query(..., description="Start date in YYYY-MM-DD format"),
    end_date: str = Query(..., description="End date in YYYY-MM-DD format"),
    account_ids: Optional[List[int]] = Query(None, description="List of account IDs to filter by"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get portfolio value time series.
    
    Args:
        start_date: Start date for the series
        end_date: End date for the series
        account_ids: Optional list of account IDs to filter by
        
    Returns:
        JSON with portfolio value time series
    """
    # Parse dates
    try:
        parsed_start = datetime.strptime(start_date, "%Y-%m-%d").date()
        parsed_end = datetime.strptime(end_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    # Validate date range
    if parsed_start > parsed_end:
        raise HTTPException(status_code=400, detail="Start date must be before end date")
    
    try:
        # Get value series
        value_series = get_value_series(parsed_start, parsed_end, account_ids)
        
        # Convert to JSON-serializable format
        series_data = {}
        for date_idx, value in value_series.items():
            series_data[date_idx.strftime("%Y-%m-%d")] = float(value)
        
        return {
            "start_date": parsed_start.isoformat(),
            "end_date": parsed_end.isoformat(),
            "account_ids": account_ids,
            "currency": "USD",
            "data": series_data
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating portfolio value series: {str(e)}")


@app.get("/portfolio/returns")
async def get_portfolio_returns(
    start_date: str = Query(..., description="Start date in YYYY-MM-DD format"),
    end_date: str = Query(..., description="End date in YYYY-MM-DD format"),
    account_ids: Optional[List[int]] = Query(None, description="List of account IDs to filter by"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get portfolio returns time series.
    
    Args:
        start_date: Start date for the series
        end_date: End date for the series
        account_ids: Optional list of account IDs to filter by
        
    Returns:
        JSON with portfolio returns time series
    """
    # Parse dates
    try:
        parsed_start = datetime.strptime(start_date, "%Y-%m-%d").date()
        parsed_end = datetime.strptime(end_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    # Validate date range
    if parsed_start > parsed_end:
        raise HTTPException(status_code=400, detail="Start date must be before end date")
    
    try:
        # Get value series
        value_series = get_value_series(parsed_start, parsed_end, account_ids)
        
        # Calculate returns
        returns = value_series.pct_change().dropna()
        
        # Calculate cumulative returns
        cumulative_returns = (1 + returns).cumprod() - 1
        
        # Convert to JSON-serializable format
        daily_returns_data = {}
        cumulative_returns_data = {}
        
        for date_idx, return_val in returns.items():
            daily_returns_data[date_idx.strftime("%Y-%m-%d")] = float(return_val)
            
        for date_idx, cum_return_val in cumulative_returns.items():
            cumulative_returns_data[date_idx.strftime("%Y-%m-%d")] = float(cum_return_val)
        
        return {
            "start_date": parsed_start.isoformat(),
            "end_date": parsed_end.isoformat(),
            "account_ids": account_ids,
            "daily_returns": daily_returns_data,
            "cumulative_returns": cumulative_returns_data
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating portfolio returns: {str(e)}")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "portfolio-analytics-api"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
