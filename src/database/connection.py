"""
Database connection and session management for the Inbox Miner.
Provides a centralized way to manage database connections and sessions.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from typing import Generator
from loguru import logger

from config.settings import settings
from src.models import Base


class DatabaseManager:
    """Manages database connections and sessions."""
    
    def __init__(self):
        self.engine = create_engine(
            settings.database.url,
            echo=settings.database.echo
        )
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )
        logger.info(f"Database initialized: {settings.database.url}")
    
    def create_tables(self) -> None:
        """Create all tables in the database."""
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Error creating database tables: {e}")
            raise
    
    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """
        Context manager for database sessions.
        Ensures proper session cleanup and error handling.
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()
    
    def get_db_session(self) -> Session:
        """
        Get a new database session.
        Remember to close the session when done.
        """
        return self.SessionLocal()


# Global database manager instance
db_manager = DatabaseManager()