"""
Main entry point for the Email Inbox Miner application.
Demonstrates basic usage of the email extraction system.
"""
from datetime import date

from loguru import logger

from src.core import EmailExtractor
from src.database import db_manager
from src.utils.logging import setup_logging


def main():
    """Main function demonstrating email extraction."""
    setup_logging()
    logger.info("Starting Email Inbox Miner")

    try:
        db_manager.create_tables()
        logger.info("Database initialized")

        extractor = EmailExtractor()

        logger.info("Starting Bancolombia email extraction")

        # IMAP SINCE is inclusive, so this means >= 2025-01-01
        date_filter = {
            "operator": ">",
            "date": date(2025, 1, 1),
        }

        extracted_count = extractor.extract_emails(
            sender="alertasynotificaciones@an.notificacionesbancolombia.com",
            subject="Alertas y Notificaciones",
            date_filter=date_filter,
            processor_type="bancolombia",
        )

        logger.info(f"Extracted {extracted_count} emails")

        stats = extractor.get_extraction_stats("bancolombia")
        logger.info(f"Extraction stats: {stats}")

    except Exception as e:
        logger.error(f"Application error: {e}")
        raise


if __name__ == "__main__":
    main()
