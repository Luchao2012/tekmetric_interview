"""
Configuration settings for NASA Near Earth Object API.
"""
import os
import logging
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Set up logging configuration
LOG_DIR = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Use date-based log files for better organization with cron jobs
log_date = datetime.now().strftime('%Y%m%d')
LOG_FILE = LOG_DIR / f"neo_collector_{log_date}.log"

# Configure rotating log handler to prevent files from growing too large
from logging.handlers import RotatingFileHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler(
            LOG_FILE,
            maxBytes=10*1024*1024,  # 10MB max file size
            backupCount=10,         # Keep 10 backup files
        ),
        logging.StreamHandler()
    ]
)

# Load environment variables
load_dotenv()
logger = logging.getLogger(__name__)
logger.info("Loading configuration")

# API Configuration
API_KEY = os.getenv("NASA_API_KEY")
BASE_URL = "https://api.nasa.gov/neo/rest/v1/neo/browse"

# Rate Limiting Configuration
MAX_REQUESTS_PER_HOUR = 1000
REQUEST_BACKOFF_FACTOR = 1.5  # Exponential backoff factor
MAX_RETRIES = 5
RATE_LIMIT_DELAY = 3600 / MAX_REQUESTS_PER_HOUR  # Time between requests to stay under limit

# Data Storage Configuration
DATA_DIR = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / "data" / "neo"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Processing Configuration
DEFAULT_BATCH_SIZE = 20  # Number of NEOs per API request
DEFAULT_CHUNK_SIZE = 100  # Number of NEOs per DataFrame chunk for processing
