"""
Email Inbox Miner data models.
"""
from .email import RawEmail, EmailProcessingLog, Base

__all__ = ["RawEmail", "EmailProcessingLog", "Base"]