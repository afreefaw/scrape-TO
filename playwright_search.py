from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import json
import os
import sqlite3
from typing import Dict, Optional
import time
import logging
from datetime import datetime

class TorontoCouncilScraper:
    def __init__(self, config_file: str = "scraper_config.json"):
        # Set up logging
        self.setup_logging()
        
        self.base_url = "https://secure.toronto.ca/council/#/advancedSearch"
        self.db_file = "agenda_items.db"
        self.progress_file = "scraping_progress.json"
        
        # Load configuration
        with open(config_file, 'r') as f:
            self.config = json.load(f)
            
        self.pages_per_checkpoint = self.config.get('pages_per_checkpoint', 20)
        self.rows_per_page = self.config.get('rows_per_page', 100)
        self.headless = self.config.get('headless', False)
        self.pages_per_browser = 200  # Restart browser every 200 pages
        
        # Initialize database
        self.init_database()

    def setup_logging(self):
        """Set up logging configuration."""
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(log_dir, f"scraper_{timestamp}.log")
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        
    def init_database(self):
        """Initialize SQLite database with required schema."""
        conn = sqlite3.connect(self.db_file)
        try:
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS agenda_items
                        (item_number TEXT PRIMARY KEY,
                         link TEXT,
                         title TEXT,
                         committee TEXT,
                         date TEXT,
                         created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
            conn.commit()
        except Exception as e:
            logging.error(f"Database initialization error: {e}")
            raise
        finally:
            conn.close()
            
    def save_items_to_db(self, items: list[Dict]):
        """Save multiple agenda items to the database in a single transaction."""
        if not items:
            return
            
        conn = sqlite3.connect(self.db_file)
        try:
            c = conn.cursor()
            
            # First check for duplicates
            item_numbers = [item['item_number'] for item in items]
            c.execute('SELECT item_number FROM agenda_items WHERE item_number IN ({})'.format(
                ','.join('?' * len(item_numbers))), item_numbers)
            existing_items = {row[0] for row in c.fetchall()}
            
            new_items = [item for item in items if item['item_number'] not in existing_items]
            update_items = [item for item in items if item['item_number'] in existing_items]
            
            # Insert new items
            if new_items:
                c.executemany('''INSERT INTO agenda_items
                                (item_number, link, title, committee, date)
                                VALUES (?, ?, ?, ?, ?)''',
                             [(item['item_number'],
                               item['link'],
                               item['title'],
                               item['committee'],
                               item['date']) for item in new_items])
            
            # Update existing items
            if update_items:
                c.executemany('''UPDATE agenda_items 
                                SET link = ?, title = ?, committee = ?, date = ?
                                WHERE item_number = ?''',
                             [(item['link'],
                               item['title'],
                               item['committee'],
                               item['date'],
                               item['item_number']) for item in update_items])
            
            conn.commit()
            logging.info(f"Database update: {len(new_items)} new items, {len(update_items)} duplicates")
        except Exception as e:
            logging.error(f"Database save error: {e}")
            raise
        finally:
            conn.close()

    def get_item_count(self) -> int:
        """Get total number of items in database."""
        conn = sqlite3.connect(self.db_file)
        try:
            c = conn.cursor()
            c.execute('SELECT COUNT(*) FROM agenda_items')
            return c.fetchone()[0]
        finally:
            conn.close()

    def save_progress(self, current_page: int):
        """Save current progress to file."""
        try:
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "last_completed_page": current_page,
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                }, f, indent=2)
            logging.info(f"Progress saved: completed up to page {current_page}")
        except Exception as e:
            logging.error(f"Error saving progress: {e}")

    def load_progress(self) -> Optional[int]:
        """Load progress from file."""
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, 'r') as f:
                    data = json.load(f)
                    return data.get("last_completed_page")
            except Exception as e:
                logging.error(f"Error loading progress: {e}")
        return None

    def wait_for_table_update(self, page):
        """Wait for the table to finish updating with progressive delay."""
        try:
            # First attempt with minimal delay
            page.wait_for_selector("tr td a[target='_blank']", timeout=5000)
        except PlaywrightTimeoutError:
            # If first attempt fails, try again with additional delay
            logging.warning("Initial table update wait failed, retrying with delay...")
            time.sleep(1)
            try:
                page.wait_for_selector("tr td a[target='_blank']", timeout=10000)
            except Exception as e:
                logging.error(f"Error waiting for table update after delay: {e}")
        except Exception as e:
            logging.error(f"Error waiting for table update: {e}")

    def set_rows_per_page(self, page) -> bool:
        """Set the number of rows displayed per page."""
        try:
            # Wait for and find the row count selector with specific class
            select = page.locator("select.form-control.input-sm[aria-label='Row count']").first
            select.wait_for(state="visible", timeout=10000)
            
            # Get initial row count
            initial_rows = len(page.locator("tr td:first-child").all())
            logging.info(f"Initial row count: {initial_rows}")
            
            # Wait a moment for the select to be fully interactive
            time.sleep(1)
            
            # Change the value and wait for it to take effect
            select.select_option(value=str(self.rows_per_page))
            
            # Wait for the value to be actually selected
            is_selected = page.wait_for_function(f"""() => {{
                const select = document.querySelector('select[aria-label="Row count"]');
                return select && select.value === '{self.rows_per_page}';
            }}""", timeout=10000)
            
            if not is_selected:
                logging.error("Failed to confirm row count selection")
                return False
            
            # Wait longer for the table to update
            time.sleep(2)
            self.wait_for_table_update(page)
            
            # Multiple attempts to verify row count change
            max_attempts = 3
            for attempt in range(max_attempts):
                rows = page.locator("tr td:first-child").all()
                actual_rows = len(rows)
                logging.info(f"Attempt {attempt + 1}: Found {actual_rows} rows")
                
                if actual_rows > initial_rows:
                    logging.info(f"Successfully increased rows per page to {actual_rows}")
                    return True
                    
                if attempt < max_attempts - 1:
                    logging.info("Waiting before next attempt...")
                    time.sleep(2)
            
            logging.error(f"Failed to increase rows after {max_attempts} attempts")
            return False
            
        except Exception as e:
            logging.error(f"Error setting rows per page: {e}")
            return False

    def go_to_page(self, page, page_number: int) -> bool:
        """Navigate to a specific page number in the results."""
        try:
            # Use a more specific selector and check if it exists
            page_link = page.locator(f"a.page-link[aria-label='Page {page_number}']")
            
            if page_link.count() == 0:
                logging.warning(f"Page {page_number} not found in pagination")
                return False
                
            logging.info(f"Navigating to page {page_number}...")
            
            # Wait for the link to be clickable
            page_link.first.wait_for(state="visible", timeout=5000)
            time.sleep(1)  # Give Angular a moment to fully initialize the element
            
            # Click and wait for network activity to settle
            page_link.first.click()
            page.wait_for_load_state("networkidle", timeout=10000)
            time.sleep(2)  # Give time for Angular to update the view
            
            # Wait for table to update
            self.wait_for_table_update(page)
            
            # Verify we're on the correct page using aria-current attribute
            active_page = page.locator("li.page-item[aria-current='true']").first
            if active_page:
                current_page_text = active_page.get_attribute("title")
                if current_page_text:
                    return current_page_text == f"Page {page_number}"
            
            return False
            
        except Exception as e:
            logging.error(f"Error navigating to page {page_number}: {e}")
            return False
            
    def extract_page_results(self, page) -> list[Dict]:
        """Extract results from the current page."""
        items = []
        try:
            # Wait for and get all data rows (excluding header)
            data_rows = page.locator("table tbody tr").all()
            logging.info(f"Found {len(data_rows)} data rows to process")
            
            for row in data_rows:
                try:
                    link_element = row.locator("td a[target='_blank']")
                    if link_element.count() == 0:
                        continue
                        
                    item_number = link_element.text_content().strip()
                    if not item_number:
                        continue
                        
                    item_number = item_number.split('\n')[0].strip()
                    
                    href = link_element.get_attribute('href')
                    if href:
                        title = row.locator("td").nth(2).text_content().strip()
                        committee = row.locator("td").nth(3).text_content().strip()
                        date = row.locator("td").nth(0).text_content().strip()
                        
                        item = {
                            "item_number": item_number,
                            "link": f"https://secure.toronto.ca{href}" if href.startswith('/') else href,
                            "title": title,
                            "committee": committee,
                            "date": date
                        }
                        items.append(item)
                except Exception as e:
                    logging.error(f"Error processing row: {e}")
                    continue
                    
            logging.info(f"Successfully processed page, extracted {len(items)} items")
            return items
            
        except Exception as e:
            logging.error(f"Error extracting results: {e}")
            return items

    def initialize_browser(self):
        """Initialize and set up browser instance."""
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=self.headless)
        context = browser.new_context(viewport={'width': 1280, 'height': 800})
        page = context.new_page()
        return playwright, browser, page

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
            last_page = self.load_progress()
            if last_page and last_page >= start_page:
                logging.info(f"Resuming from last completed page: {last_page}")
                current_page = last_page + 1
            else:
                current_page = start_page
            
            pages_since_restart = 0
            current_batch = []
            
            while current_page <= end_page:
                # Initialize or reinitialize browser if needed
                if page is None or pages_since_restart >= self.pages_per_browser:
                    if browser:
                        browser.close()
                    if playwright:
                        playwright.stop()
                    
                    logging.info("\nRestarting browser...")
                    playwright, browser, page = self.initialize_browser()
                    pages_since_restart = 0
                    
                    # Re-initialize the page
                    logging.info(f"Navigating to {self.base_url}")
                    page.goto(self.base_url, wait_until="networkidle")
                    
                    logging.info("Waiting for search form to load...")
                    page.wait_for_selector("#word-or-phrase", state="visible", timeout=10000)
                    time.sleep(1)
                    
                    logging.info("Clicking search button...")
                    search_button = page.locator("button.btn-primary").first
                    search_button.click()
                    
                    logging.info("Waiting for results table...")
                    page.wait_for_selector("tr td a[target='_blank']", timeout=10000)
                    
                    # Set rows per page and verify it worked
                    rows_set = self.set_rows_per_page(page)
                    if not rows_set:
                        logging.error("Failed to set rows per page, stopping")
                        break
                    
                    # Navigate to current page if not on first page
                    if current_page > 1:
                        if not self.go_to_page(page, current_page):
                            logging.error(f"Failed to navigate to page {current_page} after browser restart")
                            break
                
                logging.info(f"\nProcessing page {current_page}...")
                page_items = self.extract_page_results(page)
                current_batch.extend(page_items)
                
                # Save progress and items at checkpoints
                if current_page % self.pages_per_checkpoint == 0:
                    logging.info(f"\nSaving checkpoint at page {current_page}...")
                    self.save_items_to_db(current_batch)
                    self.save_progress(current_page)
                    current_batch = []  # Clear the batch after saving
                
                # Try to go to next page
                next_page = current_page + 1
                if next_page <= end_page:
                    if self.go_to_page(page, next_page):
                        current_page = next_page
                        pages_since_restart += 1
                    else:
                        logging.warning(f"Could not navigate to page {next_page}, stopping")
                        # Save any remaining items before stopping
                        if current_batch:
                            self.save_items_to_db(current_batch)
                        self.save_progress(current_page)
                        break
                else:
                    logging.info(f"Reached end page {end_page}")
                    # Save any remaining items before finishing
                    if current_batch:
                        self.save_items_to_db(current_batch)
                    self.save_progress(current_page)
                    break
                
        except Exception as e:
            logging.error(f"An error occurred: {e}")
            if current_page:
                self.save_progress(current_page - 1)
            
        finally:
            if browser:
                browser.close()
            if playwright:
                playwright.stop()

def main():
    scraper = TorontoCouncilScraper()
    scraper.scrape_agenda_items()
    
    # Print summary
    logging.info("\nScraping Summary:")
    logging.info(f"Total items in database: {scraper.get_item_count()}")

if __name__ == "__main__":
    main()