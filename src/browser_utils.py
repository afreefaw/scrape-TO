from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError
import logging
import time
from typing import Dict, List, Tuple
from playwright.sync_api import sync_playwright

class BrowserUtils:
    def __init__(self, headless: bool, rows_per_page: int):
        self.headless = headless
        self.rows_per_page = rows_per_page

    def initialize_browser(self) -> Tuple:
        """Initialize and set up browser instance."""
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=self.headless)
        context = browser.new_context(viewport={'width': 1280, 'height': 800})
        page = context.new_page()
        return playwright, browser, page

    def wait_for_table_update(self, page: Page):
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

    def set_rows_per_page(self, page: Page) -> bool:
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

    def go_to_page(self, page: Page, page_number: int) -> bool:
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

    def extract_page_results(self, page: Page) -> List[Dict]:
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