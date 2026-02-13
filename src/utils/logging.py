"""
Logging configuration for the Email Inbox Miner.
"""
import sys
from loguru import logger
from config.settings import settings


def setup_logging() -> None:
    """Configure application logging."""
    # Remove default logger
    logger.remove()
    
    # Add console logging
    logger.add(
        sys.stdout,
        format=settings.logging.format,
        level=settings.logging.level,
        colorize=True
    )
    
    # Add file logging
    logger.add(
        settings.logging.file,
        format=settings.logging.format,
        level=settings.logging.level,
        rotation="10 MB",
        retention="1 month",
        compression="zip"
    )
    
    logger.info(f"Logging configured - Level: {settings.logging.level}")