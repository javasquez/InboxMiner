"""
Configuration settings for the Email Inbox Miner application.
Designed to be scalable for different email sources and processors.
"""
from typing import Any, Dict

from pydantic import Field
from pydantic_settings import BaseSettings


class EmailSettings(BaseSettings):
    """Email connection settings."""

    host: str = Field(default="outlook.office365.com", description="IMAP server host")
    port: int = Field(default=993, description="IMAP server port")
    user: str = Field(default="", description="Email username")
    use_ssl: bool = Field(default=True, description="Use SSL connection")

    class Config:
        env_prefix = "EMAIL_"


class DatabaseSettings(BaseSettings):
    """Database connection settings."""

    url: str = Field(default="sqlite:///./data/emails.db", description="Database URL")
    echo: bool = Field(default=False, description="Echo SQL queries")

    class Config:
        env_prefix = "DATABASE_"


class MicrosoftAuthSettings(BaseSettings):
    """Microsoft OAuth settings for Graph API access."""

    tenant_id: str = Field(default="consumers", description="Azure tenant ID")
    client_id: str = Field(default="", description="Azure app client ID")
    scopes: str = Field(
        default="Mail.Read offline_access",
        description="OAuth scopes (space or comma separated)",
    )
    token_cache_file: str = Field(
        default="./data/msal_token_cache.json",
        description="Path to persisted MSAL token cache file",
    )

    class Config:
        env_prefix = "MS_"


class LoggingSettings(BaseSettings):
    """Logging configuration."""

    level: str = Field(default="INFO", description="Log level")
    file: str = Field(default="logs/email_extractor.log", description="Log file path")
    format: str = Field(
        default="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}",
        description="Log format",
    )

    class Config:
        env_prefix = "LOG_"


class AppSettings(BaseSettings):
    """Application settings."""

    name: str = Field(default="Email Inbox Miner", description="Application name")
    debug: bool = Field(default=False, description="Debug mode")
    version: str = Field(default="1.0.0", description="Application version")

    class Config:
        env_prefix = "APP_"


class Settings(BaseSettings):
    """Main settings class combining all configurations."""

    email: EmailSettings = EmailSettings()
    microsoft_auth: MicrosoftAuthSettings = MicrosoftAuthSettings()
    database: DatabaseSettings = DatabaseSettings()
    logging: LoggingSettings = LoggingSettings()
    app: AppSettings = AppSettings()

    # Email processor configurations (extensible for different email types)
    email_processors: Dict[str, Dict[str, Any]] = Field(
        default={
            "bancolombia": {
                "sender_patterns": [
                    "@bancolombia.com.co",
                    "@notificaciones.bancolombia.com.co",
                    "alertasynotificaciones@an.notificacionesbancolombia.com",
                ],
                "subject_patterns": [
                    "Alertas y Notificaciones",
                    "Movimiento",
                    "Transaccion",
                    "Transacción",
                    "Pago",
                    "Transferencia",
                ],
                "enabled": True,
            },
            "trading_newsletter": {
                "sender_patterns": ["@trading.com", "@finance.com"],
                "subject_patterns": ["Market Update", "Trading Alert", "Daily Report"],
                "enabled": False,
            },
        }
    )

    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()
