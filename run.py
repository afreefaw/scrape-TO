from src.logging_config import setup_logging
from src.scraper import TorontoCouncilScraper

def main():
    # Set up logging
    setup_logging()
    
    # Initialize and run scraper
    scraper = TorontoCouncilScraper()
    scraper.scrape_agenda_items()
    
    # Print summary
    print("\nScraping Summary:")
    print(f"Total items in database: {scraper.get_item_count()}")

if __name__ == "__main__":
    main()