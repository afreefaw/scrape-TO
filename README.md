# Toronto Council Agenda Scraper

A Python-based tool for scraping Toronto City Council agenda items, extracting detailed information, and downloading associated documents.

## Overview

This project automates the collection of Toronto City Council agenda items through a three-phase process:

### Phase 1: Initial Scraping
The first phase navigates through the Toronto City Council's advanced search interface to collect basic information about agenda items. It uses a headless browser to paginate through search results, capturing item numbers and their corresponding URLs. This data is stored in a SQLite database for further processing.

### Phase 2: Detail Extraction
Once basic item information is collected, the second phase visits each individual agenda item's page to extract detailed information including:
- Full item title
- Item body text
- Associated document links
This phase can be configured to filter specific items by year and code, making it easier to focus on particular types of agenda items.

### Phase 3: Document Download
The final phase downloads all associated documents for each agenda item. Documents are organized in folders by item code, making it easy to locate files related to specific agenda items. The system tracks download progress and can resume interrupted downloads.

## Requirements

- Python 3.x
- Required packages listed in `requirements.txt`

## Configuration

The project uses three configuration files:

1. `scraper_config.json` - Configure initial scraping parameters:
   - start_page: Starting page number
   - end_page: Ending page number
   - pages_per_checkpoint: Number of pages between progress saves
   - rows_per_page: Number of items per page
   - headless: Whether to run browser in headless mode

2. `details_config.json` - Configure detail extraction:
   - extract_file: File to store filtered items
   - progress_file: File to track progress
   - batch_size: Number of items per batch
   - filter: Settings to filter specific items by year and code

3. `download_config.json` - Configure file downloading:
   - db_file: Database file containing item details
   - download_dir: Directory to save downloaded files
   - progress_file: File to track download progress
   - batch_size: Number of files per batch

## Usage

1. Initial Scraping:
```bash
python scrape_details.py
```

2. Extract Details:
```bash
python download_files.py
```

3. Download Documents:
```bash
python src/file_downloader.py
```

## Data Storage

- `agenda_items.db`: Stores basic agenda item information
- `agenda_details.db`: Stores detailed information for each item
- `downloads/`: Directory containing downloaded documents organized by agenda item code

## Progress Tracking

The system maintains progress files to allow for resuming operations:
- `scraping_progress.json`: Tracks initial scraping progress
- `details_progress.json`: Tracks detail extraction progress
- `download_progress.json`: Tracks file download progress

Each phase saves its progress regularly, allowing for safe interruption and resumption of the process at any point. This is particularly useful when dealing with large numbers of agenda items or when downloading many documents.