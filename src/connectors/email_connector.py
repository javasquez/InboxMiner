"""
Email connector for Microsoft Graph-based email retrieval.
Supports filtering by sender, subject, and date ranges.
Designed to be extensible for different email providers.
"""
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import msal
import requests
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
    Microsoft Graph email connector for retrieving inbox emails.
    Supports Outlook/Hotmail accounts via delegated OAuth2.
    """

    def __init__(self):
        self.connection: Optional[requests.Session] = None
        self.email_settings = settings.email
        self.ms_settings = settings.microsoft_auth
        self._graph_base_url = "https://graph.microsoft.com/v1.0"

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

    @staticmethod
    def _build_date_range(
        email_filter: "EmailFilter",
    ) -> Tuple[Optional[datetime], Optional[datetime]]:
        """Build UTC date range [start, end) from the filter if present."""
        if not email_filter.date_filter:
            return None, None

        date_filter = email_filter.date_filter
        operator = date_filter.get("operator")

        if operator == "=":
            target_date = EmailConnector._normalize_date(date_filter["date"])
            start = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=timezone.utc)
            end = start + timedelta(days=1)
            return start, end

        if operator == ">":
            target_date = EmailConnector._normalize_date(date_filter["date"])
            start = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=timezone.utc)
            return start, None

        if operator == "range":
            start_date = EmailConnector._normalize_date(date_filter["start_date"])
            end_date = EmailConnector._normalize_date(date_filter["end_date"])
            start = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
            end = (
                datetime.combine(end_date, datetime.min.time()).replace(tzinfo=timezone.utc)
                + timedelta(days=1)
            )
            return start, end

        return None, None

    @staticmethod
    def _matches_text_filters(message: Dict[str, Any], email_filter: "EmailFilter") -> bool:
        """Apply sender/subject filters on a Graph message payload."""
        if email_filter.sender:
            sender = (
                message.get("from", {})
                .get("emailAddress", {})
                .get("address", "")
                .lower()
            )
            if email_filter.sender.lower() not in sender:
                return False

        if email_filter.subject:
            subject = (message.get("subject") or "").lower()
            if email_filter.subject.lower() not in subject:
                return False

        return True

    @staticmethod
    def _iso_utc(dt: datetime) -> str:
        """Return Graph-compatible ISO8601 UTC string without microseconds."""
        return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")

    def connect(self) -> None:
        """Establish authenticated Microsoft Graph session."""
        try:
            if not self.email_settings.user:
                raise ValueError("EMAIL_USER must be configured before connecting")

            access_token = self._acquire_microsoft_access_token()
            session = requests.Session()
            session.headers.update(
                {
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                }
            )

            health_response = session.get(
                f"{self._graph_base_url}/me/mailFolders/inbox",
                timeout=30,
            )
            health_response.raise_for_status()
            self.connection = session
            logger.info("Connected to Microsoft Graph mail API")

        except Exception as e:
            logger.error(f"Failed to connect to Microsoft Graph: {e}")
            raise

    def disconnect(self) -> None:
        """Close the Graph session."""
        if self.connection:
            try:
                self.connection.close()
                logger.info("Disconnected from Microsoft Graph")
            except Exception as e:
                logger.warning(f"Error during disconnect: {e}")
            finally:
                self.connection = None

    @staticmethod
    def _normalize_date(value: Union[date, datetime]) -> date:
        """Normalize date or datetime input to date."""
        return value.date() if isinstance(value, datetime) else value

    def _build_graph_filter(self, email_filter: EmailFilter) -> Optional[str]:
        """Build OData date filter for Graph requests."""
        start, end = self._build_date_range(email_filter)
        criteria_parts: List[str] = []
        if start:
            criteria_parts.append(f"receivedDateTime ge {self._iso_utc(start)}")
        if end:
            criteria_parts.append(f"receivedDateTime lt {self._iso_utc(end)}")
        if not criteria_parts:
            return None
        return " and ".join(criteria_parts)

    def search_emails(self, email_filter: EmailFilter) -> List[str]:
        """
        Search for emails matching the given criteria.
        Returns list of email IDs.
        """
        if not self.connection:
            raise ConnectionError("Not connected to email server")

        logger.info("Searching emails via Microsoft Graph")

        try:
            params: Dict[str, str] = {
                "$top": "100",
                "$select": "id,subject,from,receivedDateTime",
                "$orderby": "receivedDateTime desc",
            }
            graph_filter = self._build_graph_filter(email_filter)
            if graph_filter:
                params["$filter"] = graph_filter

            next_url = f"{self._graph_base_url}/me/mailFolders/inbox/messages"
            collected_ids: List[str] = []

            while next_url:
                response = self.connection.get(next_url, params=params, timeout=30)
                response.raise_for_status()
                payload = response.json()
                messages = payload.get("value", [])

                for message in messages:
                    if self._matches_text_filters(message, email_filter):
                        msg_id = message.get("id")
                        if msg_id:
                            collected_ids.append(msg_id)

                next_url = payload.get("@odata.nextLink")
                params = {}

            logger.info(f"Found {len(collected_ids)} emails matching criteria")
            return collected_ids

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
            response = self.connection.get(
                f"{self._graph_base_url}/me/messages/{email_id}",
                params={
                    "$select": ",".join(
                        [
                            "id",
                            "internetMessageId",
                            "from",
                            "subject",
                            "receivedDateTime",
                            "body",
                            "bodyPreview",
                            "internetMessageHeaders",
                        ]
                    )
                },
                timeout=30,
            )
            response.raise_for_status()
            message = response.json()

            body = message.get("body") or {}
            content_type = (body.get("contentType") or "").lower()
            content = body.get("content") or ""
            body_html = content if content_type == "html" else ""
            body_plain = (
                message.get("bodyPreview")
                if content_type == "html"
                else content
            ) or ""

            headers = "\n".join(
                f"{header.get('name', '')}: {header.get('value', '')}"
                for header in message.get("internetMessageHeaders", [])
            )

            return {
                "message_id": message.get("internetMessageId", f"generated-{email_id}"),
                "sender": (
                    message.get("from", {})
                    .get("emailAddress", {})
                    .get("address", "")
                ),
                "subject": message.get("subject", ""),
                "received_date": self._parse_date(message.get("receivedDateTime")),
                "body_plain": body_plain,
                "body_html": body_html,
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
            # Graph returns ISO8601 (e.g. 2026-02-13T18:40:00Z).
            parsed_iso = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            if parsed_iso.tzinfo is not None:
                return parsed_iso.astimezone(timezone.utc).replace(tzinfo=None)
            return parsed_iso
        except Exception:
            pass

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
