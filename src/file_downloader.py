import sqlite3
import json
import os
import logging
import requests
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from urllib.parse import urlparse, unquote

class FileDownloader:
    def __init__(self, config_file: str = "download_config.json"):
        # Load configuration
        with open(config_file, 'r') as f:
            self.config = json.load(f)
            
        self.db_file = self.config.get('db_file', 'agenda_details.db')
        self.download_dir = Path(self.config.get('download_dir', 'downloads'))
        self.progress_file = self.config.get('progress_file', 'download_progress.json')
        self.batch_size = self.config.get('batch_size', 20)
        
        # Ensure download directory exists
        self.download_dir.mkdir(parents=True, exist_ok=True)
        
        # Load or initialize progress
        self.progress = self.load_progress()
        
    def load_progress(self) -> Dict:
        """Load or initialize progress tracking."""
        if os.path.exists(self.progress_file):
            with open(self.progress_file, 'r') as f:
                return json.load(f)
        return {
            'downloaded_files': set(),  # Will be converted to/from list in JSON
            'last_item_id': None,
            'total_downloaded': 0,
            'failed_downloads': []
        }
        
    def save_progress(self):
        """Save current progress."""
        # Convert set to list for JSON serialization
        progress_json = {
            'downloaded_files': list(self.progress['downloaded_files']),
            'last_item_id': self.progress['last_item_id'],
            'total_downloaded': self.progress['total_downloaded'],
            'failed_downloads': self.progress['failed_downloads']
        }
        with open(self.progress_file, 'w') as f:
            json.dump(progress_json, f)
            
    def load_items_with_links(self) -> List[Dict]:
        """Load items with links from the database."""
        conn = sqlite3.connect(self.db_file)
        try:
            c = conn.cursor()
            c.execute('SELECT code, links FROM agenda_details')
            items = []
            for row in c.fetchall():
                code, links_str = row
                try:
                    # Convert string representation of list back to list
                    links = eval(links_str)  # Safe since we stored it ourselves
                    if links:  # Only include items that have links
                        items.append({'code': code, 'links': links})
                except Exception as e:
                    logging.error(f"Error parsing links for {code}: {e}")
            return items
        finally:
            conn.close()
            
    def get_filename_from_url(self, url: str) -> str:
        """Extract and clean filename from URL."""
        parsed = urlparse(url)
        filename = unquote(os.path.basename(parsed.path))
        # Clean up filename if needed
        return filename
        
    def download_file(self, url: str, dest_path: Path) -> bool:
        """Download a single file."""
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            with open(dest_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            logging.info(f"Successfully downloaded: {dest_path}")
            return True
            
        except Exception as e:
            logging.error(f"Error downloading {url}: {e}")
            return False
            
    def process_item(self, item: Dict) -> None:
        """Process a single agenda item's links."""
        code = item['code']
        item_dir = self.download_dir / code
        item_dir.mkdir(exist_ok=True)
        
        for url in item['links']:
            if url in self.progress['downloaded_files']:
                continue
                
            filename = self.get_filename_from_url(url)
            if not filename:
                continue
                
            dest_path = item_dir / filename
            if self.download_file(url, dest_path):
                self.progress['downloaded_files'].add(url)
                self.progress['total_downloaded'] += 1
            else:
                self.progress['failed_downloads'].append({
                    'url': url,
                    'code': code,
                    'error_time': str(datetime.now())
                })
                
            # Save progress periodically
            if self.progress['total_downloaded'] % self.batch_size == 0:
                self.save_progress()
                
    def download_all(self):
        """Download files for all agenda items."""
        items = self.load_items_with_links()
        total_items = len(items)
        
        if total_items == 0:
            logging.info("No items with links found")
            return
            
        logging.info(f"Found {total_items} items with links to process")
        
        # Convert downloaded_files from list back to set if loaded from JSON
        if isinstance(self.progress['downloaded_files'], list):
            self.progress['downloaded_files'] = set(self.progress['downloaded_files'])
        
        # Find starting point
        start_idx = 0
        if self.progress['last_item_id']:
            for i, item in enumerate(items):
                if item['code'] == self.progress['last_item_id']:
                    start_idx = i + 1
                    break
        
        if start_idx > 0:
            logging.info(f"Resuming from item {start_idx + 1}")
        
        for i, item in enumerate(items[start_idx:], start_idx):
            logging.info(f"Processing item {i+1}/{total_items}: {item['code']}")
            self.process_item(item)
            self.progress['last_item_id'] = item['code']
            
            # Save progress after each item
            self.save_progress()
        
        # Final progress save and summary
        self.save_progress()
        logging.info("\nDownload Summary:")
        logging.info(f"Total items processed: {total_items}")
        logging.info(f"Total files downloaded: {self.progress['total_downloaded']}")
        logging.info(f"Failed downloads: {len(self.progress['failed_downloads'])}")

def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    downloader = FileDownloader()
    downloader.download_all()

if __name__ == "__main__":
    main()