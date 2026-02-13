"""
Email data models for the Inbox Miner application.
Defines the structure for raw email storage and processed data.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class RawEmail(Base):
    """
    Raw email storage table - stores emails as received from the inbox.
    This table serves as the source of truth for all email data.
    """
    __tablename__ = "raw_emails"

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(String(255), unique=True, nullable=False, index=True)
    sender = Column(String(255), nullable=False, index=True)
    subject = Column(Text, nullable=False, index=True)
    body_plain = Column(Text, nullable=True)
    body_html = Column(Text, nullable=True)
    received_date = Column(DateTime, nullable=False, index=True)
    processed = Column(Boolean, default=False, index=True)
    processor_type = Column(String(50), nullable=True, index=True)  # e.g., 'bancolombia', 'trading'
    raw_headers = Column(Text, nullable=True)  # Store all headers as JSON string
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<RawEmail(id={self.id}, sender='{self.sender}', subject='{self.subject[:50]}...')>"


class EmailProcessingLog(Base):
    """
    Log table to track email processing activities and errors.
    Helps with monitoring and debugging the extraction process.
    """
    __tablename__ = "email_processing_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    raw_email_id = Column(Integer, nullable=True, index=True)
    action = Column(String(100), nullable=False)  # 'extracted', 'processed', 'error'
    processor_type = Column(String(50), nullable=True)
    status = Column(String(50), nullable=False)  # 'success', 'error', 'skipped'
    message = Column(Text, nullable=True)
    error_details = Column(Text, nullable=True)
    processing_time_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<EmailProcessingLog(id={self.id}, action='{self.action}', status='{self.status}')>"