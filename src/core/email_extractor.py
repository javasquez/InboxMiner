"""
Core email extraction service for the Inbox Miner.
Handles the main workflow of connecting, searching, and storing emails.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from loguru import logger
from sqlalchemy.exc import IntegrityError

from src.connectors import EmailConnector, EmailFilter
from src.database import db_manager
from src.models import RawEmail, EmailProcessingLog


class EmailExtractor:
    """
    Main service for extracting emails from inbox and storing them in the database.
    Handles the complete workflow from connection to storage.
    """
    
    def __init__(self):
        self.connector = EmailConnector()
        self.db_manager = db_manager
    
    def extract_emails(
        self, 
        sender: Optional[str] = None,
        subject: Optional[str] = None,
        date_filter: Optional[Dict[str, Any]] = None,
        processor_type: Optional[str] = None
    ) -> int:
        """
        Extract emails matching the given criteria and store them in the database.
        
        Args:
            sender: Email sender to filter by (e.g., "@bancolombia.com.co")
            subject: Subject keywords to filter by
            date_filter: Date filtering criteria
            processor_type: Type of processor this extraction is for (e.g., 'bancolombia')
        
        Returns:
            Number of emails successfully extracted and stored
        """
        start_time = datetime.utcnow()
        extracted_count = 0
        error_count = 0
        
        logger.info(f"Starting email extraction - Sender: {sender}, Subject: {subject}")
        
        try:
            # Create email filter
            email_filter = EmailFilter(
                sender=sender,
                subject=subject,
                date_filter=date_filter
            )
            
            # Connect and search for emails
            with self.connector as conn:
                email_ids = conn.search_emails(email_filter)
                
                if not email_ids:
                    logger.info("No emails found matching criteria")
                    return 0
                
                logger.info(f"Found {len(email_ids)} emails to process")
                
                # Process each email
                for email_id in email_ids:
                    try:
                        # Fetch email data
                        email_data = conn.fetch_email(email_id)
                        
                        # Store in database
                        if self._store_email(email_data, processor_type):
                            extracted_count += 1
                            self._log_processing_activity(
                                action="extracted",
                                processor_type=processor_type,
                                status="success",
                                message=f"Email stored: {email_data['message_id']}"
                            )
                        
                    except Exception as e:
                        error_count += 1
                        logger.error(f"Error processing email ID {email_id}: {e}")
                        self._log_processing_activity(
                            action="extracted",
                            processor_type=processor_type,
                            status="error",
                            message=f"Failed to process email ID {email_id}",
                            error_details=str(e)
                        )
            
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            logger.info(
                f"Email extraction completed - "
                f"Extracted: {extracted_count}, Errors: {error_count}, "
                f"Time: {processing_time:.2f}s"
            )
            
            return extracted_count
            
        except Exception as e:
            logger.error(f"Email extraction failed: {e}")
            self._log_processing_activity(
                action="extraction_batch",
                processor_type=processor_type,
                status="error",
                message="Batch extraction failed",
                error_details=str(e)
            )
            raise
    
    def _store_email(self, email_data: Dict[str, Any], processor_type: Optional[str] = None) -> bool:
        """
        Store email data in the database.
        Returns True if successful, False if already exists.
        """
        try:
            with self.db_manager.get_session() as session:
                # Check if email already exists
                existing = session.query(RawEmail).filter_by(
                    message_id=email_data['message_id']
                ).first()
                
                if existing:
                    logger.debug(f"Email already exists: {email_data['message_id']}")
                    return False
                
                # Create new email record
                raw_email = RawEmail(
                    message_id=email_data['message_id'],
                    sender=email_data['sender'],
                    subject=email_data['subject'],
                    body_plain=email_data.get('body_plain'),
                    body_html=email_data.get('body_html'),
                    received_date=email_data['received_date'],
                    processor_type=processor_type,
                    raw_headers=email_data.get('raw_headers')
                )
                
                session.add(raw_email)
                session.flush()  # Get the ID
                
                logger.debug(f"Stored email: {raw_email.message_id}")
                return True
                
        except IntegrityError as e:
            logger.debug(f"Email already exists (integrity error): {email_data['message_id']}")
            return False
        except Exception as e:
            logger.error(f"Error storing email: {e}")
            raise
    
    def _log_processing_activity(
        self,
        action: str,
        processor_type: Optional[str] = None,
        status: str = "success",
        message: Optional[str] = None,
        error_details: Optional[str] = None,
        raw_email_id: Optional[int] = None,
        processing_time_ms: Optional[int] = None
    ) -> None:
        """Log processing activity to the database."""
        try:
            with self.db_manager.get_session() as session:
                log_entry = EmailProcessingLog(
                    raw_email_id=raw_email_id,
                    action=action,
                    processor_type=processor_type,
                    status=status,
                    message=message,
                    error_details=error_details,
                    processing_time_ms=processing_time_ms
                )
                session.add(log_entry)
        except Exception as e:
            logger.error(f"Failed to log processing activity: {e}")
    
    def get_extraction_stats(self, processor_type: Optional[str] = None) -> Dict[str, Any]:
        """Get statistics about extracted emails."""
        try:
            with self.db_manager.get_session() as session:
                query = session.query(RawEmail)
                
                if processor_type:
                    query = query.filter_by(processor_type=processor_type)
                
                total_emails = query.count()
                processed_emails = query.filter_by(processed=True).count()
                unprocessed_emails = total_emails - processed_emails
                
                # Get latest extraction date
                latest_email = query.order_by(RawEmail.created_at.desc()).first()
                latest_extraction = latest_email.created_at if latest_email else None
                
                return {
                    "total_emails": total_emails,
                    "processed_emails": processed_emails,
                    "unprocessed_emails": unprocessed_emails,
                    "latest_extraction": latest_extraction,
                    "processor_type": processor_type
                }
                
        except Exception as e:
            logger.error(f"Error getting extraction stats: {e}")
            return {}