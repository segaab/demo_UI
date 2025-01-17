import os
from dotenv import load_dotenv
from loguru import logger

# Load environment variables
load_dotenv()

# Redis Configuration
REDIS_HOST = os.getenv('REDIS_HOST', '127.0.0.1')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
REDIS_DB = int(os.getenv('REDIS_DB', '0'))

# Polling Configuration
POLLING_INTERVAL = int(os.getenv('POLLING_INTERVAL', '120'))
ARTICLES_BUFFER_SIZE = int(os.getenv('ARTICLES_BUFFER_SIZE', '15'))

# Configure logging
logger.add(
    "logs/app.log",
    rotation="500 MB",
    retention="10 days",
    level="INFO"
) 