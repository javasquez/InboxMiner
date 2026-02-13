"""
Email connector for IMAP-based email retrieval.
Supports filtering by sender, subject, and date ranges.
Designed to be extensible for different email providers.
"""
import imaplib
import email
import ssl
from datetime import datetime, date
from typing import List, Optional, Dict, Any, Tuple, Union
from email.message import EmailMessage
from loguru import logger
from dataclasses import dataclass

from config.settings import settings


@dataclass
class EmailFilter:
    """Email filtering criteria."""
    sender: Optional[str] = None
    subject: Optional[str] = None
    date_filter: Optional[Dict[str, Union[str, date, datetime]]] = None
    # date_filter examples:
    # {"operator": "=", "date": date(2024, 1, 15)}
    # {"operator": ">", "date": date(2024, 1, 1)}
    # {"operator": "range", "start_date": date(2024, 1, 1), "end_date": date(2024, 1, 31)}


class EmailConnector:
    """
    IMAP email connector for retrieving emails from inbox.
    Supports hotmail/outlook and can be extended for other providers.
    """
    
    def __init__(self):
        self.connection: Optional[imaplib.IMAP4_SSL] = None
        self.email_settings = settings.email
        
    def connect(self) -> None:
        """Establish connection to the email server."""
        try:
            if self.email_settings.use_ssl:
                context = ssl.create_default_context()
                self.connection = imaplib.IMAP4_SSL(
                    self.email_settings.host, 
                    self.email_settings.port,
                    ssl_context=context
                )
            else:
                self.connection = imaplib.IMAP4(
                    self.email_settings.host, 
                    self.email_settings.port
                )
            
            # Login
            self.connection.login(
                self.email_settings.user, 
                self.email_settings.password
            )
            
            # Select inbox
            self.connection.select('INBOX')
            logger.info(f"Connected to email server: {self.email_settings.host}")
            
        except Exception as e:
            logger.error(f"Failed to connect to email server: {e}")
            raise
    
    def disconnect(self) -> None:
        """Close the connection to the email server."""
        if self.connection:
            try:
                self.connection.logout()
                logger.info("Disconnected from email server")
            except Exception as e:
                logger.warning(f"Error during disconnect: {e}")
            finally:
                self.connection = None
    
    def _build_search_criteria(self, email_filter: EmailFilter) -> str:
        """Build IMAP search criteria from EmailFilter."""
        criteria_parts = []
        
        # Sender filter
        if email_filter.sender:
            criteria_parts.append(f'FROM "{email_filter.sender}"')
        
        # Subject filter
        if email_filter.subject:
            criteria_parts.append(f'SUBJECT "{email_filter.subject}"')
        
        # Date filter
        if email_filter.date_filter:
            date_filter = email_filter.date_filter
            operator = date_filter.get("operator")
            
            if operator == "=":
                target_date = date_filter["date"]
                if isinstance(target_date, datetime):
                    target_date = target_date.date()
                criteria_parts.append(f'ON {target_date.strftime("%d-%b-%Y")}')
                
            elif operator == ">":
                target_date = date_filter["date"]
                if isinstance(target_date, datetime):
                    target_date = target_date.date()
                criteria_parts.append(f'SINCE {target_date.strftime("%d-%b-%Y")}')
                
            elif operator == "range":
                start_date = date_filter["start_date"]
                end_date = date_filter["end_date"]
                if isinstance(start_date, datetime):
                    start_date = start_date.date()
                if isinstance(end_date, datetime):
                    end_date = end_date.date()
                criteria_parts.append(f'SINCE {start_date.strftime("%d-%b-%Y")}')
                criteria_parts.append(f'BEFORE {end_date.strftime("%d-%b-%Y")}')
        
        # If no criteria, search all emails (be careful with this)
        if not criteria_parts:
            criteria_parts.append('ALL')
        
        return ' '.join(criteria_parts)
    
    def search_emails(self, email_filter: EmailFilter) -> List[str]:
        """
        Search for emails matching the given criteria.
        Returns list of email UIDs.
        """
        if not self.connection:
            raise ConnectionError("Not connected to email server")
        
        search_criteria = self._build_search_criteria(email_filter)
        logger.info(f"Searching emails with criteria: {search_criteria}")
        
        try:
            status, message_ids = self.connection.search(None, search_criteria)
            if status != 'OK':
                raise Exception(f"Search failed: {status}")
            
            # Parse message IDs
            if message_ids[0]:
                ids = message_ids[0].split()
                logger.info(f"Found {len(ids)} emails matching criteria")
                return [id.decode() for id in ids]
            else:
                logger.info("No emails found matching criteria")
                return []
                
        except Exception as e:
            logger.error(f"Error searching emails: {e}")
            raise
    
    def fetch_email(self, email_id: str) -> Dict[str, Any]:
        """
        Fetch a single email by ID and return parsed data.
        Returns dict with email components.
        """
        if not self.connection:
            raise ConnectionError("Not connected to email server")
        
        try:
            # Fetch the email
            status, msg_data = self.connection.fetch(email_id, '(RFC822)')
            if status != 'OK':
                raise Exception(f"Fetch failed for email ID {email_id}: {status}")
            
            # Parse the email
            raw_email = msg_data[0][1]
            email_message = email.message_from_bytes(raw_email)
            
            # Extract email components
            email_data = {
                'message_id': email_message.get('Message-ID', f'generated-{email_id}'),
                'sender': email_message.get('From', ''),
                'subject': email_message.get('Subject', ''),
                'received_date': self._parse_date(email_message.get('Date')),
                'body_plain': '',
                'body_html': '',
                'raw_headers': str(email_message),
            }
            
            # Extract body content
            if email_message.is_multipart():
                for part in email_message.walk():
                    content_type = part.get_content_type()
                    if content_type == 'text/plain':
                        body = part.get_payload(decode=True)
                        if body:
                            email_data['body_plain'] = body.decode('utf-8', errors='ignore')
                    elif content_type == 'text/html':
                        body = part.get_payload(decode=True)
                        if body:
                            email_data['body_html'] = body.decode('utf-8', errors='ignore')
            else:
                # Single part message
                body = email_message.get_payload(decode=True)
                if body:
                    content_type = email_message.get_content_type()
                    body_text = body.decode('utf-8', errors='ignore')
                    if content_type == 'text/html':
                        email_data['body_html'] = body_text
                    else:
                        email_data['body_plain'] = body_text
            
            return email_data
            
        except Exception as e:
            logger.error(f"Error fetching email ID {email_id}: {e}")
            raise
    
    def _parse_date(self, date_str: Optional[str]) -> datetime:
        """Parse email date string to datetime object."""
        if not date_str:
            return datetime.utcnow()
        
        try:
            # Use email.utils to parse the date
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(date_str)
        except Exception:
            logger.warning(f"Could not parse date: {date_str}")
            return datetime.utcnow()
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()