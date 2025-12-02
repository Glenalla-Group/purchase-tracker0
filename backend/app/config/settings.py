"""
Application configuration and settings management.
"""

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True
    
    # Frontend URL (for email links)
    frontend_url: str = "http://localhost:5173"
    
    # Google Cloud Project
    google_cloud_project_id: str = ""
    google_pubsub_topic: Optional[str] = None
    google_pubsub_subscription: Optional[str] = None
    
    # Gmail API Configuration
    gmail_credentials_path: str = "credentials.json"
    gmail_token_path: str = "token.json"
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
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    @property
    def gmail_scopes_list(self) -> list[str]:
        """Return Gmail scopes as a list."""
        return [scope.strip() for scope in self.gmail_scopes.split(",")]
    
    @property
    def base_dir(self) -> Path:
        """Return the base directory of the project."""
        return Path(__file__).resolve().parent.parent.parent


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

