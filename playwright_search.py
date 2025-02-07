from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import json
import os
from typing import Dict, Optional
import time

class TorontoCouncilScraper:
    def __init__(self, config_file: str = "scraper_config.json"):
        self.base_url = "https://secure.toronto.ca/council/#/advancedSearch"
        self.results_file = "agenda_items.json"
        self.progress_file = "scraping_progress.json"
        
        # Load configuration
        with open(config_file, 'r') as f:
            self.config = json.load(f)
            
        self.pages_per_checkpoint = self.config.get('pages_per_checkpoint', 20)
        self.rows_per_page = self.config.get('rows_per_page', 100)
        self.headless = self.config.get('headless', False)
        
    def load_existing_results(self) -> Dict:
        if os.path.exists(self.results_file):
            try:
                with open(self.results_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                print(f"Error reading {self.results_file}, starting fresh")
        return {}

    def save_results(self, results: Dict):
        try:
            with open(self.results_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, sort_keys=True)
            print(f"Successfully saved {len(results)} items to {self.results_file}")
        except Exception as e:
            print(f"Error saving results: {e}")

    def save_progress(self, current_page: int):
        try:
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "last_completed_page": current_page,
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                }, f, indent=2)
            print(f"Progress saved: completed up to page {current_page}")
        except Exception as e:
            print(f"Error saving progress: {e}")

    def load_progress(self) -> Optional[int]:
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, 'r') as f:
                    data = json.load(f)
                    return data.get("last_completed_page")
            except Exception as e:
                print(f"Error loading progress: {e}")
        return None

    def wait_for_table_update(self, page):
        """Wait for the table to finish updating with progressive delay."""
        try:
            # First attempt with minimal delay
            page.wait_for_selector("tr td a[target='_blank']", timeout=5000)
        except PlaywrightTimeoutError:
            # If first attempt fails, try again with additional delay
            print("Initial table update wait failed, retrying with delay...")
            time.sleep(1)
            try:
                page.wait_for_selector("tr td a[target='_blank']", timeout=10000)
            except Exception as e:
                print(f"Error waiting for table update after delay: {e}")
        except Exception as e:
            print(f"Error waiting for table update: {e}")

    def set_rows_per_page(self, page) -> bool:
        """Set the number of rows displayed per page."""
        try:
            print(f"Setting rows per page to {self.rows_per_page}...")
            
            # Wait for and find the row count selector with specific class
            select = page.locator("select.form-control.input-sm[aria-label='Row count']").first
            select.wait_for(state="visible", timeout=10000)
            
            # Get initial row count
            initial_rows = len(page.locator("tr td:first-child").all())
            print(f"Initial row count: {initial_rows}")
            
            # Wait a moment for the select to be fully interactive
            time.sleep(1)
            
            # Change the value and wait for it to take effect
            print(f"Setting rows per page to {self.rows_per_page}...")
            select.select_option(value=str(self.rows_per_page))
            
            # Wait for the value to be actually selected
            is_selected = page.wait_for_function(f"""() => {{
                const select = document.querySelector('select[aria-label="Row count"]');
                return select && select.value === '{self.rows_per_page}';
            }}""", timeout=10000)
            
            if not is_selected:
                print("Failed to confirm row count selection")
                return False
            
            # Wait longer for the table to update
            time.sleep(2)
            self.wait_for_table_update(page)
            
            # Multiple attempts to verify row count change
            max_attempts = 3
            for attempt in range(max_attempts):
                rows = page.locator("tr td:first-child").all()
                actual_rows = len(rows)
                print(f"Attempt {attempt + 1}: Found {actual_rows} rows")
                
                if actual_rows > initial_rows:
                    print(f"Successfully increased rows per page to {actual_rows}")
                    return True
                    
                if attempt < max_attempts - 1:
                    print("Waiting before next attempt...")
                    time.sleep(2)
            
            print(f"Failed to increase rows after {max_attempts} attempts")
            return False
            
        except Exception as e:
            print(f"Error setting rows per page: {e}")
            return False

    def go_to_page(self, page, page_number: int) -> bool:
        """Navigate to a specific page number in the results."""
        try:
            # Use a more specific selector and get the first matching element
            page_link = page.locator(f"a.page-link[aria-label='Page {page_number}']").first
            
            if not page_link:
                print(f"Page {page_number} not found in pagination")
                return False
                
            print(f"Navigating to page {page_number}...")
            page_link.click()
            
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
            print(f"Error navigating to page {page_number}: {e}")
            return False
            
    def extract_page_results(self, page) -> Dict:
        """Extract results from the current page."""
        results = {}
        
        try:
            # Wait for and get all rows
            rows = page.locator("tr").all()
            print(f"Found {len(rows)} rows to process")
            
            for row in rows:
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
                        
                        results[item_number] = {
                            "item_number": item_number,
                            "link": f"https://secure.toronto.ca{href}" if href.startswith('/') else href,
                            "title": title,
                            "committee": committee,
                            "date": date
                        }
                        print(f"Found item: {item_number} - {title}")
                except Exception as e:
                    print(f"Error processing row: {e}")
                    continue
                    
            print(f"Successfully processed {len(results)} items from this page")
            return results
            
        except Exception as e:
            print(f"Error extracting results: {e}")
            return results
            
    def scrape_agenda_items(self):
        """
        Scrape agenda items using parameters from config file.
        """
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context(viewport={'width': 1280, 'height': 800})
            page = context.new_page()
            
            try:
                existing_results = self.load_existing_results()
                
                print(f"Navigating to {self.base_url}")
                page.goto(self.base_url, wait_until="networkidle")
                
                print("Waiting for search form to load...")
                page.wait_for_selector("#word-or-phrase", state="visible", timeout=10000)
                time.sleep(1)
                
                print("Clicking search button...")
                search_button = page.locator("button.btn-primary").first
                search_button.click()
                
                print("Waiting for results table...")
                page.wait_for_selector("tr td a[target='_blank']", timeout=10000)
                
                # Set rows per page and verify it worked
                rows_set = self.set_rows_per_page(page)
                if not rows_set:
                    print("Failed to set rows per page to 100, stopping")
                    return existing_results
                
                # Determine starting page
                start_page = self.config['start_page']
                end_page = self.config['end_page']
                
                # Check for progress
                last_page = self.load_progress()
                if last_page and last_page >= start_page:
                    print(f"Resuming from last completed page: {last_page}")
                    current_page = last_page + 1
                else:
                    current_page = start_page
                
                while True:
                    if current_page > 1:
                        if not self.go_to_page(page, current_page):
                            print(f"Failed to navigate to page {current_page}")
                            break
                    
                    print(f"\nProcessing page {current_page}...")
                    page_results = self.extract_page_results(page)
                    existing_results.update(page_results)
                    
                    # Check if we've reached the end page
                    if current_page >= end_page:
                        print(f"Reached end page {end_page}")
                        # Save progress since we're done
                        self.save_results(existing_results)
                        self.save_progress(current_page)
                        break
                    
                    # Try to go to next page before marking current as complete
                    next_page = current_page + 1
                    if self.go_to_page(page, next_page):
                        # Only save progress after confirming we can move forward
                        if current_page % self.pages_per_checkpoint == 0:
                            self.save_results(existing_results)
                            self.save_progress(current_page)
                        current_page = next_page
                    else:
                        print(f"Could not navigate to page {next_page}, stopping")
                        # Save progress since we're stopping
                        self.save_results(existing_results)
                        self.save_progress(current_page)
                        break
                
                return existing_results
                
            except Exception as e:
                print(f"An error occurred: {e}")
                # Save progress on error
                self.save_progress(current_page - 1)
                return existing_results
                
            finally:
                time.sleep(1)
                browser.close()

def main():
    scraper = TorontoCouncilScraper()
    
    results = scraper.scrape_agenda_items()
    
    # Print summary
    print("\nScraping Summary:")
    print(f"Total items: {len(results)}")

if __name__ == "__main__":
    main()