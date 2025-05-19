"""
API client for fetching data from NASA's Near Earth Object Web Service (NeoWs) API.
Handles rate limiting, retries, and error handling.
"""
import time
import logging
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Dict, Any
from datetime import datetime

from src import config  # Import config correctly

# Get logger for this module
logger = logging.getLogger(__name__)

class NeoApiClient:
    """Client for interacting with NASA's Near Earth Object Web Service API.
    
    Includes:
    - Rate limiting to stay under API limits
    - Automatic retries with exponential backoff
    - Error handling and logging
    """
    
    def __init__(self):
        self.session = self._create_retry_session()
        self.last_request_time = 0
        self.request_count = 0
        self.hour_start = time.time()
        
    def _create_retry_session(self) -> requests.Session:
        """Create a session with retry capability."""
        retry_strategy = Retry(
            total=config.MAX_RETRIES,
            backoff_factor=config.REQUEST_BACKOFF_FACTOR,
            status_forcelist=[429, 500, 502, 503, 504],  # Retry on these HTTP status codes
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session = requests.Session()
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        
        return session
        
    def _check_rate_limit(self):
        """Enforce rate limits and reset counters when an hour passes."""
        current_time = time.time()
        
        # Check if an hour has passed since we started counting
        if current_time - self.hour_start > 3600:
            hour_requests = self.request_count
            logger.info(f"Resetting hourly request counter - made {hour_requests} requests in the last hour")
            self.hour_start = current_time
            self.request_count = 0
            
        # If we're approaching the rate limit, wait until the next hour
        if self.request_count >= config.MAX_REQUESTS_PER_HOUR:
            wait_time = 3600 - (current_time - self.hour_start) + 1  # +1 for safety
            restart_time = datetime.fromtimestamp(current_time + wait_time).strftime('%H:%M:%S')
            logger.warning(f"Rate limit reached ({self.request_count}/{config.MAX_REQUESTS_PER_HOUR}). Waiting {wait_time:.1f} seconds before resuming at {restart_time}.")
            time.sleep(wait_time)
            self.hour_start = time.time()
            self.request_count = 0
            logger.info("Rate limit wait complete, resuming operations")
            
        # Enforce minimum delay between requests to distribute them evenly
        elapsed = current_time - self.last_request_time
        if elapsed < config.RATE_LIMIT_DELAY:
            delay = config.RATE_LIMIT_DELAY - elapsed
            if delay > 0.5:  # Only log if delay is significant
                logger.debug(f"Rate limiting: sleeping for {delay:.2f}s to maintain request spacing")
            time.sleep(delay)
        
        self.last_request_time = time.time()
        self.request_count += 1
        
        # Log every 50 requests to show progress
        if self.request_count % 50 == 0:
            percent = (self.request_count / config.MAX_REQUESTS_PER_HOUR) * 100
            logger.info(f"Rate limit usage: {self.request_count}/{config.MAX_REQUESTS_PER_HOUR} ({percent:.1f}%)")
        
    def fetch_neo_page(self, page: int = 0, size: int = None) -> Dict[str, Any]:
        """
        Fetch one page of NEO browse results with rate limiting and retries.
        
        Args:
            page: zero-based page index
            size: number of NEOs per page
            
        Returns:
            JSON response as dict
            
        Raises:
            requests.RequestException: If all retries fail
        """
        # Use default batch size if size is None
        if size is None:
            size = config.DEFAULT_BATCH_SIZE
            
        self._check_rate_limit()
        
        params = {
            'page': page,
            'size': size,
            'api_key': config.API_KEY
        }
        
        start_time = time.time()
        try:
            logger.info(f"Fetching NEO data, page {page}, size {size}")
            response = self.session.get(config.BASE_URL, params=params)
            response.raise_for_status()
            
            elapsed = time.time() - start_time
            data = response.json()
            count = len(data.get('near_earth_objects', []))
            
            logger.info(f"Successfully fetched page {page} with {count} objects in {elapsed:.2f}s (status: {response.status_code})")
            return data
            
        except requests.RequestException as e:
            elapsed = time.time() - start_time
            logger.error(f"Error fetching NEO page {page} after {elapsed:.2f}s: {str(e)}")
            logger.error(f"URL: {config.BASE_URL}, Params: {params}")
            raise
