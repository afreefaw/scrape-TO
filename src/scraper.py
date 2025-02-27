import json
import logging
from typing import Optional

from .database import Database
from .progress import ProgressTracker
from .browser_utils import BrowserUtils

class TorontoCouncilScraper:
    def __init__(self, config_file: str = "scraper_config.json"):
        # Load configuration
        with open(config_file, 'r') as f:
            self.config = json.load(f)
            
        # Initialize constants
        self.base_url = "https://secure.toronto.ca/council/#/advancedSearch"
        self.db_file = "agenda_items.db"
        self.progress_file = "scraping_progress.json"
        
        # Load config values
        self.pages_per_checkpoint = self.config.get('pages_per_checkpoint', 20)
        self.rows_per_page = self.config.get('rows_per_page', 100)
        self.headless = self.config.get('headless', False)
        
        # Initialize components
        self.database = Database(self.db_file)
        self.progress_tracker = ProgressTracker(self.progress_file)
        self.browser_utils = BrowserUtils(self.headless, self.rows_per_page)

    def get_item_count(self) -> int:
        """Get total number of items in database."""
        return self.database.get_item_count()

    def scrape_agenda_items(self):
        """Scrape agenda items using parameters from config file."""
        playwright = None
        browser = None
        page = None
        current_page = None
        
        try:
            # Determine starting page
            start_page = self.config['start_page']
            end_page = self.config['end_page']
            
            # Check for progress
            last_page = self.progress_tracker.load_progress()
            if last_page and last_page >= start_page:
                logging.info(f"Resuming from last completed page: {last_page}")
                current_page = last_page + 1
            else:
                current_page = start_page
            
            current_batch = []
            
            # Initialize browser once at the start
            logging.info("\nInitializing browser...")
            playwright, browser, page = self.browser_utils.initialize_browser()
            
            # Initialize the page
            logging.info(f"Navigating to {self.base_url}")
            page.goto(self.base_url, wait_until="networkidle")
            
            logging.info("Waiting for search form to load...")
            page.wait_for_selector("#word-or-phrase", state="visible", timeout=10000)
            
            logging.info("Clicking search button...")
            search_button = page.locator("button.btn-primary").first
            search_button.click()
            
            logging.info("Waiting for results table...")
            page.wait_for_selector("tr td a[target='_blank']", timeout=10000)
            
            # Set rows per page and verify it worked
            rows_set = self.browser_utils.set_rows_per_page(page)
            if not rows_set:
                logging.error("Failed to set rows per page, stopping")
                return
            
            # Navigate to starting page if not on first page
            if current_page > 1:
                if not self.browser_utils.go_to_page(page, current_page):
                    logging.error(f"Failed to navigate to page {current_page}")
                    return
            
            while current_page <= end_page:
                
                logging.info(f"\nProcessing page {current_page}...")
                page_items = self.browser_utils.extract_page_results(page)
                current_batch.extend(page_items)
                
                # Save progress and items at checkpoints
                if current_page % self.pages_per_checkpoint == 0:
                    logging.info(f"\nSaving checkpoint at page {current_page}...")
                    try:
                        self.database.save_items_to_db(current_batch)
                        self.progress_tracker.save_progress(current_page)
                        current_batch = []  # Clear batch only after successful save
                    except Exception as e:
                        logging.error(f"Error saving batch at page {current_page}: {e}")
                        # Save progress up to the last successful checkpoint
                        last_checkpoint = current_page - (current_page % self.pages_per_checkpoint)
                        if last_checkpoint > 0:
                            self.progress_tracker.save_progress(last_checkpoint)
                        raise
                
                # Try to go to next page
                next_page = current_page + 1
                if next_page <= end_page:
                    if self.browser_utils.go_to_page(page, next_page):
                        current_page = next_page
                    else:
                        logging.warning(f"Could not navigate to page {next_page}, stopping")
                        break
                else:
                    logging.info(f"Reached end page {end_page}")
                    break
                    
            # Save any remaining items before finishing
            if current_batch:
                try:
                    self.database.save_items_to_db(current_batch)
                    self.progress_tracker.save_progress(current_page)
                except Exception as e:
                    logging.error(f"Error saving final batch: {e}")
                    # Save progress up to the last successful checkpoint
                    last_checkpoint = current_page - (current_page % self.pages_per_checkpoint)
                    if last_checkpoint > 0:
                        self.progress_tracker.save_progress(last_checkpoint)
                    raise
                
        except Exception as e:
            logging.error(f"An error occurred: {e}")
            if current_page:
                self.progress_tracker.save_progress(current_page - 1)
            
        finally:
            if browser:
                browser.close()
            if playwright:
                playwright.stop()