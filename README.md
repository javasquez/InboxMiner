# Email Inbox Miner

A scalable Python application for extracting, processing, and analyzing emails from your inbox. Initially designed for processing Bancolombia bank emails, but built to be easily extensible for any type of email analysis.

## Features

- **Email Extraction**: Connect to IMAP servers (Hotmail, Outlook, Gmail, etc.)
- **Flexible Filtering**: Filter emails by sender, subject, and date ranges
- **Scalable Architecture**: Easily extensible for different email processors
- **Database Storage**: SQLite database for raw email storage and processing logs
- **Robust Error Handling**: Comprehensive logging and error tracking
- **Future-Ready**: Designed to handle various email types (financial, newsletters, etc.)

## Project Structure

```text
email_inbox_miner/
|-- src/
|   |-- core/                 # Core business logic
|   |   `-- email_extractor.py
|   |-- connectors/           # Email connection handlers
|   |   `-- email_connector.py
|   |-- database/             # Database management
|   |   `-- connection.py
|   |-- models/               # Data models
|   |   `-- email.py
|   `-- utils/                # Utility functions
|       `-- logging.py
|-- config/                   # Configuration files
|   `-- settings.py
|-- tests/                    # Unit tests
|-- data/                     # Database files
|-- logs/                     # Application logs
|-- requirements.txt
|-- .env.example
`-- main.py
```

## Setup

1. **Clone and Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Environment**:
   Copy `.env.example` to `.env` and update with your email and Microsoft app values:
   ```bash
   EMAIL_HOST=outlook.office365.com
   EMAIL_PORT=993
   EMAIL_USER=your_email@hotmail.com
   MS_CLIENT_ID=your_azure_app_client_id
   MS_TENANT_ID=consumers
   MS_SCOPES=https://outlook.office.com/IMAP.AccessAsUser.All offline_access
   MS_TOKEN_CACHE_FILE=./data/msal_token_cache.json
   ```

3. **Run the Application**:
   ```bash
   python main.py
   ```

## Usage

### Basic Email Extraction

```python
from src.core import EmailExtractor
from datetime import date

extractor = EmailExtractor()

# Extract emails with filters
extracted_count = extractor.extract_emails(
    sender="@bancolombia.com.co",
    subject="Movimiento",
    date_filter={
        "operator": ">",
        "date": date(2024, 1, 1)
    },
    processor_type="bancolombia"
)
```

### Date Filter Options

```python
# Exact date match
date_filter = {"operator": "=", "date": date(2024, 1, 15)}

# After specific date
date_filter = {"operator": ">", "date": date(2024, 1, 1)}

# Date range
date_filter = {
    "operator": "range",
    "start_date": date(2024, 1, 1),
    "end_date": date(2024, 1, 31)
}
```

## Database Schema

### raw_emails Table
- Stores all extracted emails in their original form
- Includes metadata like sender, subject, dates, and processing status
- Designed as the single source of truth for all email data

### email_processing_logs Table
- Tracks all processing activities and errors
- Useful for monitoring and debugging

## Extending for New Email Types

1. **Add Processor Configuration** in `config/settings.py`:
   ```python
   "trading_newsletter": {
       "sender_patterns": ["@tradingcompany.com"],
       "subject_patterns": ["Market Alert", "Daily Brief"],
       "enabled": True
   }
   ```

2. **Use the Same Extraction Interface**:
   ```python
   extractor.extract_emails(
       sender="@tradingcompany.com",
       subject="Market Alert",
       processor_type="trading_newsletter"
   )
   ```

## Security Notes

- Uses Microsoft OAuth2 (`MSAL`) with IMAP `XOAUTH2` authentication
- `MS_SCOPES` must include `https://outlook.office.com/IMAP.AccessAsUser.All`
- Tokens are cached in `MS_TOKEN_CACHE_FILE` to avoid interactive login each run
- Store credentials in environment variables, never in code
- The `.env` file is git-ignored by default

## Next Steps (Future Development)

1. **Silver Table Creation**: Process raw emails into structured data
2. **Content Parsers**: Specific parsers for different email types
3. **Data Analysis**: Financial transaction analysis tools
4. **Web Interface**: Dashboard for monitoring and analysis
5. **Multiple Email Accounts**: Support for multiple email sources

## Requirements

- Python 3.8+
- IMAP-enabled email account
- Internet connection for email access

## License

This project is for personal use and educational purposes.
