import typer
from pathlib import Path
from typing import Optional

app = typer.Typer(help="Portfolio Analytics CLI")


@app.command()
def ingest(
    source: str = typer.Argument(..., help="Source file or directory to ingest"),
    format: str = typer.Option("csv", help="Input format (csv, json)"),
    output: Optional[Path] = typer.Option(None, help="Output directory for processed data"),
):
    """Ingest data from various sources."""
    from app.ingestion.loader import load_data
    load_data(source, format, output)


@app.command()
def update_prices(
    symbols: Optional[str] = typer.Option(None, help="Comma-separated list of symbols to update"),
    force: bool = typer.Option(False, help="Force update even if recent data exists"),
):
    """Update price data for portfolio assets."""
    from app.services.price_service import update_prices
    update_prices(symbols.split(",") if symbols else None, force)


@app.command()
def generate_report(
    start_date: Optional[str] = typer.Option(None, help="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = typer.Option(None, help="End date (YYYY-MM-DD)"),
    output: Optional[Path] = typer.Option(None, help="Output file path"),
):
    """Generate portfolio performance report."""
    from app.valuation.reporting import generate_report
    generate_report(start_date, end_date, output)


if __name__ == "__main__":
    app() 