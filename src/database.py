import sqlite3
import logging
from typing import Dict

class Database:
    def __init__(self, db_file: str):
        self.db_file = db_file
        self.init_database()

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