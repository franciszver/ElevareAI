"""
Application Settings and Configuration
Loads from environment variables with sensible defaults
"""

import os
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # ========================================================================
    # Database Configuration
    # ========================================================================
    db_host: str = Field(default="localhost", description="Database host")
    db_port: int = Field(default=5432, description="Database port")
    db_name: str = Field(default="elevareai", description="Database name")
    db_user: str = Field(default="postgres", description="Database user")
    db_password: str = Field(default="", description="Database password")
    db_pool_size: int = Field(default=5, description="Connection pool size")
    db_max_overflow: int = Field(default=10, description="Max overflow connections")

    # ========================================================================
    # OpenRouter Configuration
    # ========================================================================
    openrouter_api_key: str = Field(default="", description="OpenRouter API key")
    openrouter_model: str = Field(
        default="openai/gpt-oss-20b:free", description="OpenRouter model"
    )
    openrouter_temperature: float = Field(
        default=0.7, description="OpenRouter temperature"
    )
    openrouter_max_tokens: int = Field(
        default=2000, description="OpenRouter max tokens"
    )
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1", description="OpenRouter base URL"
    )

    # ========================================================================
    # Application Configuration
    # ========================================================================
    environment: str = Field(default="development", description="Environment")
    log_level: str = Field(default="INFO", description="Log level")
    api_version: str = Field(default="v1", description="API version")
    api_base_url: str = Field(
        default="http://localhost:8000", description="API base URL"
    )

    # API Keys
    ai_service_api_key: Optional[str] = Field(
        default=None, description="Service API key"
    )

    # JWT Authentication
    jwt_secret: str = Field(default="", description="JWT signing secret")
    jwt_expiry_minutes: int = Field(
        default=1440, description="JWT access token expiry in minutes"
    )

    # Demo accounts
    demo_password: str = Field(
        default="",
        description="Password for seeded demo accounts (set locally/in Render dashboard; never committed)",
    )

    # ========================================================================
    # Feature Flags
    # ========================================================================
    enable_ai_practice_generation: bool = Field(
        default=True, description="Enable AI practice generation"
    )
    enable_nudges: bool = Field(default=True, description="Enable nudges")
    enable_analytics: bool = Field(default=True, description="Enable analytics")

    # ========================================================================
    # Rate Limiting
    # ========================================================================
    rate_limit_per_minute: int = Field(default=100, description="Rate limit per minute")
    rate_limit_per_hour: int = Field(default=1000, description="Rate limit per hour")

    # ========================================================================
    # Nudge Configuration
    # ========================================================================
    default_nudge_frequency_cap: int = Field(
        default=1, description="Default nudge frequency cap (per day)"
    )
    nudge_inactivity_threshold_days: int = Field(
        default=7, description="Inactivity threshold for nudges"
    )
    nudge_min_sessions_threshold: int = Field(
        default=3, description="Minimum sessions threshold"
    )

    # ========================================================================
    # Confidence Thresholds
    # ========================================================================
    confidence_high_threshold: float = Field(
        default=0.75, description="High confidence threshold"
    )
    confidence_medium_threshold: float = Field(
        default=0.50, description="Medium confidence threshold"
    )

    # ========================================================================
    # Adaptive Practice (Elo Rating)
    # ========================================================================
    elo_k_factor: int = Field(default=32, description="Elo K factor (learning rate)")
    elo_default_rating: int = Field(default=1000, description="Default Elo rating")
    elo_min_rating: int = Field(default=400, description="Minimum Elo rating")
    elo_max_rating: int = Field(default=2000, description="Maximum Elo rating")

    # ========================================================================
    # External Service URLs
    # ========================================================================
    rails_app_url: Optional[str] = Field(default=None, description="Rails app URL")
    webhook_secret: Optional[str] = Field(default=None, description="Webhook secret")

    # ========================================================================
    # CORS Configuration
    # ========================================================================
    allowed_origins: str = Field(
        default="*",
        description="Comma-separated CORS origins; * allows all (dev)",
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()


def get_database_url() -> str:
    """Get database connection URL"""
    return (
        f"postgresql://{settings.db_user}:{settings.db_password}"
        f"@{settings.db_host}:{settings.db_port}/{settings.db_name}"
    )
