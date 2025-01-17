import os
from dotenv import load_dotenv
from loguru import logger

# Load environment variables
load_dotenv()

# Redis Configuration (minimal)
REDIS_HOST = os.getenv('REDIS_HOST', '127.0.0.1')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6381'))
REDIS_DB = int(os.getenv('REDIS_DB', '0'))

# RSS Feed Configuration
RSS_FEEDS = [
    'https://ambcrypto.com/feed/',
    # Other feeds commented out for now
]

# Polling Configuration
POLLING_INTERVAL = int(os.getenv('POLLING_INTERVAL', '120'))
ARTICLES_BUFFER_SIZE = int(os.getenv('ARTICLES_BUFFER_SIZE', '15'))
INITIAL_RETRY_DELAY = 5
MAX_RETRY_DELAY = 300
LOG_LEVEL = "INFO"
CLOUDFLARE_POLLING_INTERVAL = 300  # 5 minutes

def is_cloudflare_feed(feed_url: str) -> bool:
    """Check if feed is protected by Cloudflare"""
    cloudflare_domains = []  # Empty since ambcrypto isn't Cloudflare protected
    return any(domain in feed_url for domain in cloudflare_domains)

# Configure logging
logger.add(
    "logs/app.log",
    rotation="500 MB",
    retention="10 days",
    level=LOG_LEVEL
) 