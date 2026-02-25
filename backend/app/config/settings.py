"""
Application configuration and settings management.
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.
    
    Note: ENVIRONMENT must be set as a system environment variable (not in .env files)
    because it determines which .env file to load.
    """
    
    # Environment Configuration (must be set as system env var, not in .env)
    environment: str = "development"  # "development" or "production"
     
    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    
    # Frontend URL (for email links)
    frontend_url: str = "http://localhost:5173"
    
    # Google Cloud Project
    google_cloud_project_id: str = ""
    google_pubsub_topic: Optional[str] = None
    google_pubsub_subscription: Optional[str] = None
    
    # Gmail API Configuration
    gmail_credentials_path: str = ""  # Will be set based on environment
    gmail_token_path: str = ""
    gmail_scopes: str = "https://www.googleapis.com/auth/gmail.readonly,https://www.googleapis.com/auth/gmail.modify"
    
    # SMTP Email Configuration
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""  # For Gmail, use App Password
    smtp_from_email: str = ""
    smtp_from_name: str = "Purchase Tracker"
    
    # Google OAuth Configuration
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    google_oauth_redirect_uri: str = "http://localhost:8000/auth/google/callback"
    
    # Webhook Configuration
    webhook_secret: str = "change-me-in-production"
    
    # Application Settings
    log_level: str = "INFO"
    
    # Database Configuration
    database_url: str = ""
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout: int = 30
    db_pool_recycle: int = 3600
    db_echo: bool = False
    
    # Feature Flags
    enable_purchase_tracker_api: bool = True
    enable_retailers_api: bool = True
    enable_checkin_api: bool = True
    enable_pto_api: bool = True
    enable_holidays_api: bool = True
    enable_tasks_api: bool = True
    enable_retailer_orders_api: bool = True
    enable_gmail_watch: bool = True
    enable_auto_email_processing: bool = False
    
    # Playwright Configuration
    playwright_headless: bool = True
    
    # PrepWorx Automation Credentials
    prepworx_lloyd_lane_email: str = ""
    prepworx_lloyd_lane_password: str = ""
    prepworx_vista_ave_email: str = ""
    prepworx_vista_ave_password: str = ""
    
    # Keepa API Configuration
    keepa_api_key: str = "43n6aphgivclutfndctif5am60ik50ps9gbaj91hhtfh80j24kv345dib6k5561h"
    
    model_config = SettingsConfigDict(
        env_file=".env" if environment == "production" else ".env.development",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    def __init__(self, **kwargs):
        """Initialize settings and set credential path based on environment."""
        super().__init__(**kwargs)
        
        # Set credentials path based on environment if not explicitly provided
        if not self.gmail_credentials_path:
            if self.environment == "production":
                self.gmail_credentials_path = "credentials.json"
            else:
                self.gmail_credentials_path = "credentials-dev.json"

        if not self.gmail_token_path:
            if self.environment == "production":
                self.gmail_token_path = "token.json"
            else:
                self.gmail_token_path = "token-dev.json"
    
    @property
    def gmail_scopes_list(self) -> list[str]:
        """Return Gmail scopes as a list."""
        return [scope.strip() for scope in self.gmail_scopes.split(",")]
    
    @property
    def gmail_pubsub_topic(self) -> Optional[str]:
        """Alias for google_pubsub_topic for backward compatibility."""
        return self.google_pubsub_topic
    
    @property
    def base_dir(self) -> Path:
        """Return the base directory of the project."""
        return Path(__file__).resolve().parent.parent.parent
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.environment == "development"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

