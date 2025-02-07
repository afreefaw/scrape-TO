import sqlite3
import logging
import requests
import json
import os
from bs4 import BeautifulSoup
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

@dataclass
class AgendaItemDetail:
    code: str
    title: str
    body: str
    links: List[str]

class AgendaDetailScraper:
    def __init__(self, config_file: str = "details_config.json", source_db: str = "agenda_items.db", target_db: str = "agenda_details.db"):
        # Load configuration
        with open(config_file, 'r') as f:
            self.config = json.load(f)
            
        self.source_db = source_db
        self.target_db = target_db
        self.extract_file = self.config['extract_file']
        self.progress_file = self.config['progress_file']
        self.batch_size = self.config.get('batch_size', 50)
        
        # Initialize databases and load/create progress
        self.init_database()
        self.filtered_items = self.load_or_filter_items()
        self.progress = self.load_progress()

    def init_database(self):
        """Initialize the target database with required schema."""
        conn = sqlite3.connect(self.target_db)
        try:
            c = conn.cursor()
            # Create table for agenda item details
            c.execute('''CREATE TABLE IF NOT EXISTS agenda_details
                        (code TEXT PRIMARY KEY,
                         title TEXT,
                         body TEXT,
                         links TEXT,
                         created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
            conn.commit()
        except Exception as e:
            logging.error(f"Database initialization error: {e}")
            raise
        finally:
            conn.close()

    def load_progress(self) -> Dict:
        """Load or initialize progress tracking."""
        if os.path.exists(self.progress_file):
            with open(self.progress_file, 'r') as f:
                return json.load(f)
        return {'processed_count': 0, 'last_index': -1}

    def save_progress(self, index: int):
        """Save current progress."""
        self.progress['last_index'] = index
        self.progress['processed_count'] += 1
        with open(self.progress_file, 'w') as f:
            json.dump(self.progress, f)

    def load_or_filter_items(self) -> List[Dict[str, str]]:
        """Load filtered items from extract file or create new filtered list."""
        if os.path.exists(self.extract_file):
            with open(self.extract_file, 'r') as f:
                return json.load(f)

        # Get all items from database
        items = self.get_source_urls()
        
        # Apply filters if enabled
        if self.config['filter']['enabled']:
            year = self.config['filter']['year']
            code = self.config['filter']['code']
            
            filtered = []
            for item in items:
                # Parse item code (format: YYYY.XX##.##)
                parts = item['code'].split('.')
                if len(parts) >= 2:
                    item_year = parts[0]
                    item_code = parts[1][:2]  # Get first two letters of second part
                    
                    if item_year == year and item_code == code:
                        filtered.append(item)
            
            items = filtered
        
        # Save filtered items
        with open(self.extract_file, 'w') as f:
            json.dump(items, f)
            
        logging.info(f"Filtered {len(items)} items matching criteria")
        return items

    def get_source_urls(self) -> List[Dict[str, str]]:
        """Get all agenda item URLs from the source database."""
        conn = sqlite3.connect(self.source_db)
        try:
            c = conn.cursor()
            c.execute('SELECT item_number, link FROM agenda_items')
            return [{'code': row[0], 'url': row[1]} for row in c.fetchall()]
        finally:
            conn.close()

    def extract_page_details(self, url: str) -> Optional[AgendaItemDetail]:
        """Extract details from an agenda item page."""
        try:
            response = requests.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            # Find the main card div
            card = soup.find('div', class_='card')
            if not card:
                logging.error(f"Could not find card div in {url}")
                return None

            # Extract title from h3 with class 'heading'
            title_elem = card.find('h3', class_='heading')
            if not title_elem:
                logging.error(f"Could not find title in {url}")
                return None

            # Get code and title
            title_text = title_elem.text.strip()
            code = title_text.split(' - ')[0].strip()
            title = ' - '.join(title_text.split(' - ')[1:]).strip()

            # Extract body text from card-body
            card_body = card.find('div', class_='card-body')
            body = card_body.get_text(separator='\n', strip=True) if card_body else ""

            # Extract all links
            base_url = "https://www.toronto.ca"
            links = []
            for a_tag in card.find_all('a', href=True):
                href = a_tag['href']
                if href.startswith('http'):
                    links.append(href)
                else:
                    links.append(base_url + href)

            return AgendaItemDetail(code=code, title=title, body=body, links=links)

        except Exception as e:
            logging.error(f"Error extracting details from {url}: {e}")
            return None

    def save_details(self, details: AgendaItemDetail):
        """Save agenda item details to the database."""
        conn = sqlite3.connect(self.target_db)
        try:
            c = conn.cursor()
            c.execute('''INSERT OR REPLACE INTO agenda_details
                        (code, title, body, links)
                        VALUES (?, ?, ?, ?)''',
                     (details.code,
                      details.title,
                      details.body,
                      str(details.links)))  # Convert list to string
            conn.commit()
            logging.info(f"Saved details for agenda item {details.code}")
        except Exception as e:
            logging.error(f"Error saving details for {details.code}: {e}")
            raise
        finally:
            conn.close()

    def process_all_items(self):
        """Process filtered agenda items with progress tracking."""
        total = len(self.filtered_items)
        if total == 0:
            logging.info("No items match the filter criteria")
            return

        # Start from last processed index + 1
        start_index = self.progress['last_index'] + 1
        if start_index > 0:
            logging.info(f"Resuming from index {start_index}")

        for i in range(start_index, total):
            item = self.filtered_items[i]
            logging.info(f"Processing item {i+1}/{total}: {item['code']}")
            
            try:
                details = self.extract_page_details(item['url'])
                if details:
                    self.save_details(details)
                    self.save_progress(i)
                else:
                    logging.warning(f"Could not extract details for {item['code']}")
            except Exception as e:
                logging.error(f"Error processing {item['code']}: {e}")
                # Don't update progress on error to allow retry
                continue

            # Log batch completion
            if (i + 1) % self.batch_size == 0:
                logging.info(f"Completed batch of {self.batch_size} items")
                logging.info(f"Progress: {i+1}/{total} items ({((i+1)/total)*100:.1f}%)")

        logging.info("\nProcessing Summary:")
        logging.info(f"Total items matching filter: {total}")
        logging.info(f"Successfully processed: {self.progress['processed_count']}")

def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    scraper = AgendaDetailScraper()
    scraper.process_all_items()

if __name__ == "__main__":
    main()