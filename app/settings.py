from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database
    DATABASE_URL: str = "sqlite:///./data/databases/portfolio.db"
    
    # API Keys (optional)
    COINBASE_API_KEY: Optional[str] = None
    COINBASE_API_SECRET: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_API_SECRET: Optional[str] = None
    
    # Paths
    DATA_DIR: str = "data"
    RAW_DATA_DIR: str = "data/raw"
    CACHE_DIR: str = "data/cache"
    
    # API Settings
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    DEBUG: bool = False
    
    # External services
    COINGECKO_API_URL: str = "https://api.coingecko.com/api/v3"
    
    # Application settings
    LOG_LEVEL: str = "INFO"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )


# Create global settings instance
settings = Settings() 