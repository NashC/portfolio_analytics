from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.settings import settings

app = FastAPI(
    title="Portfolio Analytics API",
    description="API for portfolio tracking and analytics",
    version="0.1.0",
    debug=settings.DEBUG,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import and include routers
# from app.api import portfolio, analytics, valuation
# app.include_router(portfolio.router, prefix="/api/v1/portfolio", tags=["portfolio"])
# app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["analytics"])
# app.include_router(valuation.router, prefix="/api/v1/valuation", tags=["valuation"])


@app.get("/")
async def root():
    """Root endpoint returning API information."""
    return {
        "name": "Portfolio Analytics API",
        "version": "0.1.0",
        "status": "operational",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"} 