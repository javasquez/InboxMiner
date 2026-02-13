"""
Database package for the Email Inbox Miner.
"""
from .connection import DatabaseManager, db_manager

__all__ = ["DatabaseManager", "db_manager"]