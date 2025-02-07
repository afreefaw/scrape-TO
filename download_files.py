from src.logging_config import setup_logging
from src.file_downloader import FileDownloader

def main():
    # Set up logging
    setup_logging()
    
    # Initialize and run downloader
    downloader = FileDownloader()
    downloader.download_all()

if __name__ == "__main__":
    main()