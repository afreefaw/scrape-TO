import json
import os
import time
import logging
from typing import Optional

class ProgressTracker:
    def __init__(self, progress_file: str):
        self.progress_file = progress_file

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