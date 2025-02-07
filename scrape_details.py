from src.logging_config import setup_logging
from src.agenda_details import AgendaDetailScraper

def main():
    # Set up logging
    setup_logging()
    
    # Initialize and run scraper
    scraper = AgendaDetailScraper()
    scraper.process_all_items()

if __name__ == "__main__":
    main()