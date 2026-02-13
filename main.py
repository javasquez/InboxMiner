"""
Main entry point for the Email Inbox Miner application.
Demonstrates basic usage of the email extraction system.
"""
from datetime import date, datetime
from loguru import logger

from src.utils.logging import setup_logging
from src.core import EmailExtractor
from src.database import db_manager


def main():
    """Main function demonstrating email extraction."""
    # Setup logging
    setup_logging()
    logger.info("Starting Email Inbox Miner")
    
    try:
        # Initialize database
        db_manager.create_tables()
        logger.info("Database initialized")
        
        # Create email extractor
        extractor = EmailExtractor()
        
        # Example: Extract Bancolombia emails from the last 30 days
        logger.info("Starting Bancolombia email extraction")
        
        # Date filter example - emails from the last 30 days
        date_filter = {
            "operator": ">",
            "date": date(2024, 12, 1)  # Adjust this date as needed
        }
        
        extracted_count = extractor.extract_emails(
            sender="@bancolombia.com.co",  # Will match any sender containing this
            subject="Movimiento",  # Will match subjects containing this word
            date_filter=date_filter,
            processor_type="bancolombia"
        )
        
        logger.info(f"Extracted {extracted_count} emails")
        
        # Get extraction statistics
        stats = extractor.get_extraction_stats("bancolombia")
        logger.info(f"Extraction stats: {stats}")
        
    except Exception as e:
        logger.error(f"Application error: {e}")
        raise


if __name__ == "__main__":
    main()