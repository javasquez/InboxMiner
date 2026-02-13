"""
Email connector for IMAP-based email retrieval.
Supports filtering by sender, subject, and date ranges.
Designed to be extensible for different email providers.
"""
import email
import imaplib
import re
import ssl
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import msal
from loguru import logger

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
        self.connection: Optional[imaplib.IMAP4] = None
        self.email_settings = settings.email
        self.ms_settings = settings.microsoft_auth

    @staticmethod
    def _parse_scopes(scopes_value: str) -> List[str]:
        """Parse scopes from comma or whitespace separated string."""
        return [scope for scope in re.split(r"[\s,]+", scopes_value.strip()) if scope]

    def _acquire_microsoft_access_token(self) -> str:
        """Acquire Microsoft OAuth access token using device code flow."""
        if not self.ms_settings.client_id:
            raise ValueError("MS_CLIENT_ID must be configured before connecting")

        authority = f"https://login.microsoftonline.com/{self.ms_settings.tenant_id}"
        scopes = self._parse_scopes(self.ms_settings.scopes)
        if not scopes:
            raise ValueError("MS_SCOPES must include at least one scope")

        token_cache = msal.SerializableTokenCache()
        cache_file = Path(self.ms_settings.token_cache_file)
        if cache_file.exists():
            token_cache.deserialize(cache_file.read_text(encoding="utf-8"))

        app = msal.PublicClientApplication(
            client_id=self.ms_settings.client_id,
            authority=authority,
            token_cache=token_cache,
        )

        token_result: Optional[Dict[str, Any]] = None
        accounts = app.get_accounts(username=self.email_settings.user)
        if accounts:
            token_result = app.acquire_token_silent(scopes=scopes, account=accounts[0])

        if not token_result or "access_token" not in token_result:
            flow = app.initiate_device_flow(scopes=scopes)
            if "user_code" not in flow:
                raise RuntimeError("Failed to start device code flow for Microsoft login")

            logger.info(flow["message"])
            token_result = app.acquire_token_by_device_flow(flow)

        access_token = token_result.get("access_token")
        if not access_token:
            error_message = token_result.get("error_description") or str(token_result)
            raise RuntimeError(f"Microsoft token acquisition failed: {error_message}")

        if token_cache.has_state_changed:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(token_cache.serialize(), encoding="utf-8")

        return access_token

    def connect(self) -> None:
        """Establish connection to the email server."""
        try:
            if not self.email_settings.user:
                raise ValueError("EMAIL_USER must be configured before connecting")

            if self.email_settings.use_ssl:
                context = ssl.create_default_context()
                self.connection = imaplib.IMAP4_SSL(
                    self.email_settings.host,
                    self.email_settings.port,
                    ssl_context=context,
                )
            else:
                self.connection = imaplib.IMAP4(
                    self.email_settings.host,
                    self.email_settings.port,
                )

            access_token = self._acquire_microsoft_access_token()
            auth_string = (
                f"user={self.email_settings.user}\x01"
                f"auth=Bearer {access_token}\x01\x01"
            ).encode("utf-8")
            self.connection.authenticate("XOAUTH2", lambda _: auth_string)
            status, _ = self.connection.select("INBOX")
            if status != "OK":
                raise RuntimeError("Failed to select INBOX after authentication")
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

    @staticmethod
    def _normalize_date(value: Union[date, datetime]) -> date:
        """Normalize date or datetime input to date."""
        return value.date() if isinstance(value, datetime) else value

    @staticmethod
    def _quote_imap(value: str) -> str:
        """Quote string values for IMAP search criteria."""
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'

    def _build_search_criteria(self, email_filter: EmailFilter) -> List[str]:
        """Build IMAP search criteria from EmailFilter."""
        criteria_parts: List[str] = []

        if email_filter.sender:
            criteria_parts.extend(["FROM", self._quote_imap(email_filter.sender)])

        if email_filter.subject:
            criteria_parts.extend(["SUBJECT", self._quote_imap(email_filter.subject)])

        if email_filter.date_filter:
            date_filter = email_filter.date_filter
            operator = date_filter.get("operator")

            if operator == "=":
                target_date = self._normalize_date(date_filter["date"])
                criteria_parts.extend(["ON", target_date.strftime("%d-%b-%Y")])

            elif operator == ">":
                target_date = self._normalize_date(date_filter["date"])
                criteria_parts.extend(["SINCE", target_date.strftime("%d-%b-%Y")])

            elif operator == "range":
                start_date = self._normalize_date(date_filter["start_date"])
                end_date = self._normalize_date(date_filter["end_date"])
                # IMAP BEFORE is exclusive; add one day to make end_date inclusive.
                end_exclusive = end_date + timedelta(days=1)
                criteria_parts.extend(["SINCE", start_date.strftime("%d-%b-%Y")])
                criteria_parts.extend(["BEFORE", end_exclusive.strftime("%d-%b-%Y")])

        if not criteria_parts:
            criteria_parts.append("ALL")

        return criteria_parts

    def search_emails(self, email_filter: EmailFilter) -> List[str]:
        """
        Search for emails matching the given criteria.
        Returns list of email IDs.
        """
        if not self.connection:
            raise ConnectionError("Not connected to email server")

        search_criteria = self._build_search_criteria(email_filter)
        logger.info(f"Searching emails with criteria: {' '.join(search_criteria)}")

        try:
            status, message_ids = self.connection.search(None, *search_criteria)
            if status != "OK":
                raise Exception(f"Search failed: {status}")

            if message_ids[0]:
                ids = message_ids[0].split()
                logger.info(f"Found {len(ids)} emails matching criteria")
                return [msg_id.decode() for msg_id in ids]

            logger.info("No emails found matching criteria")
            return []

        except Exception as e:
            logger.error(f"Error searching emails: {e}")
            raise

    @staticmethod
    def _decode_payload(part: email.message.Message, payload: Any) -> str:
        """Decode email payload while respecting MIME charset."""
        if payload is None:
            return ""
        if isinstance(payload, str):
            return payload

        charset = part.get_content_charset() or "utf-8"
        for candidate in (charset, "utf-8", "latin-1"):
            try:
                return payload.decode(candidate, errors="replace")
            except Exception:
                continue
        return payload.decode("utf-8", errors="ignore")

    def _extract_bodies(self, email_message: email.message.Message) -> Dict[str, str]:
        """Extract plain and HTML bodies while ignoring attachments."""
        plain_parts: List[str] = []
        html_parts: List[str] = []

        if email_message.is_multipart():
            for part in email_message.walk():
                if part.is_multipart():
                    continue

                disposition = (part.get_content_disposition() or "").lower()
                if disposition == "attachment":
                    continue

                content_type = part.get_content_type().lower()
                if content_type not in {"text/plain", "text/html"}:
                    continue

                decoded = self._decode_payload(part, part.get_payload(decode=True)).strip()
                if not decoded:
                    continue

                if content_type == "text/plain":
                    plain_parts.append(decoded)
                else:
                    html_parts.append(decoded)
        else:
            content_type = email_message.get_content_type().lower()
            decoded = self._decode_payload(
                email_message,
                email_message.get_payload(decode=True),
            ).strip()
            if decoded:
                if content_type == "text/html":
                    html_parts.append(decoded)
                else:
                    plain_parts.append(decoded)

        return {
            "body_plain": "\n\n".join(plain_parts),
            "body_html": "\n\n".join(html_parts),
        }

    def fetch_email(self, email_id: str) -> Dict[str, Any]:
        """
        Fetch a single email by ID and return parsed data.
        Returns dict with email components.
        """
        if not self.connection:
            raise ConnectionError("Not connected to email server")

        try:
            status, msg_data = self.connection.fetch(email_id, "(RFC822)")
            if status != "OK" or not msg_data or msg_data[0] is None:
                raise Exception(f"Fetch failed for email ID {email_id}: {status}")

            raw_email = msg_data[0][1]
            email_message = email.message_from_bytes(raw_email)
            bodies = self._extract_bodies(email_message)

            headers = "\n".join(
                f"{header}: {value}" for header, value in email_message.items()
            )

            return {
                "message_id": email_message.get("Message-ID", f"generated-{email_id}"),
                "sender": email_message.get("From", ""),
                "subject": email_message.get("Subject", ""),
                "received_date": self._parse_date(email_message.get("Date")),
                "body_plain": bodies["body_plain"],
                "body_html": bodies["body_html"],
                "raw_headers": headers,
            }

        except Exception as e:
            logger.error(f"Error fetching email ID {email_id}: {e}")
            raise

    def _parse_date(self, date_str: Optional[str]) -> datetime:
        """Parse email date string to naive UTC datetime."""
        if not date_str:
            return datetime.utcnow()

        try:
            from email.utils import parsedate_to_datetime

            parsed = parsedate_to_datetime(date_str)
            if parsed.tzinfo is not None:
                return parsed.astimezone(timezone.utc).replace(tzinfo=None)
            return parsed
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
