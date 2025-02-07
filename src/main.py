import logging
from .logging_config import setup_logging
from .scraper import TorontoCouncilScraper

def main():
    # Set up logging
    setup_logging()
    
    # Initialize and run scraper
    scraper = TorontoCouncilScraper()
    scraper.scrape_agenda_items()
    
    # Print summary
    logging.info("\nScraping Summary:")
    logging.info(f"Total items in database: {scraper.get_item_count()}")

if __name__ == "__main__":
    main()