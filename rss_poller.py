import asyncio
import aiohttp
import feedparser
import uuid
import json
from datetime import datetime
import os
from typing import List, Dict, Any
import logging
from dotenv import load_dotenv
import time
from article_store import ArticleStore
from redis.client import RedisClient

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('poller.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Redis Configuration from environment variables
REDIS_HOST = os.getenv('REDIS_HOST', '127.0.0.1')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6381'))
REDIS_DB = int(os.getenv('REDIS_DB', '0'))

RSS_FEEDS = [
    'https://ambcrypto.com/feed/',
]

# Polling configuration
POLL_INTERVAL = 120  # 2 minutes
INITIAL_RETRY_DELAY = 5  # seconds
MAX_RETRY_DELAY = 300  # seconds
REQUIRED_ARTICLES = 15  # Number of articles needed before ready

# Status Icons
ICONS = {
    'success': '✅',
    'error': '❌',
    'info': 'ℹ️',
    'warning': '⚠️',
    'new': '🆕',
    'sync': '🔄',
    'save': '💾',
    'ready': '🚀',
    'db': '🗄️',
}

class RSSPoller:
    def __init__(self):
        self.redis_client = RedisClient()
        self.article_buffer = []
        self.is_ready = False
        self.article_store = ArticleStore()

    async def setup(self):
        """Initialize Redis connection"""
        connected = await self.redis_client.connect(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB
        )
        if not connected:
            raise ConnectionError("Failed to connect to Redis")
        logger.info(f"{ICONS['db']} Connected to Redis")

    async def fetch_feed(self, session: aiohttp.ClientSession, url: str) -> None:
        """Fetch and process a single RSS feed"""
        delay = INITIAL_RETRY_DELAY
        while True:
            try:
                async with session.get(url) as response:
                    if response.status == 200:
                        content = await response.text()
                        feed = feedparser.parse(content)
                        new_articles = 0
                        
                        for entry in feed.entries:
                            if len(self.article_buffer) >= REQUIRED_ARTICLES:
                                break

                            article_id = str(uuid.uuid4())
                            categories = [tag.get('term', '') for tag in entry.get('tags', [])]
                            
                            article = {
                                'id': article_id,
                                'title': entry.get('title', ''),
                                'link': entry.get('link', ''),
                                'description': entry.get('description', ''),
                                'published': entry.get('published', ''),
                                'categories': categories,
                                'source': url,
                                'timestamp': datetime.now().isoformat()
                            }
                            
                            # Store in Redis with 24-hour expiration
                            await self.redis_client.save_article(
                                f"article:{article_id}",
                                article
                            )
                            self.article_buffer.append(article)
                            new_articles += 1

                        if new_articles > 0:
                            logger.info(f"{ICONS['new']} Added {new_articles} articles from {url}")
                            logger.info(f"{ICONS['info']} Buffer size: {len(self.article_buffer)}/{REQUIRED_ARTICLES}")
                            # Save to file system
                            self.article_store.save_articles(self.article_buffer)
                        
                        if len(self.article_buffer) >= REQUIRED_ARTICLES and not self.is_ready:
                            self.is_ready = True
                            logger.info(f"{ICONS['ready']} Service is ready! Buffer full with {len(self.article_buffer)} articles")
                        return
                        
            except Exception as e:
                logger.error(f"{ICONS['error']} Error fetching {url}: {str(e)}")
                if delay > MAX_RETRY_DELAY:
                    logger.error(f"{ICONS['error']} Max retry delay reached for {url}")
                    return
                    
                logger.warning(f"{ICONS['warning']} Retrying {url} in {delay} seconds...")
                await asyncio.sleep(delay)
                delay *= 2  # Exponential backoff

    async def poll_feeds(self):
        """Main polling loop"""
        await self.setup()
        
        async with aiohttp.ClientSession() as session:
            while True:
                tasks = [self.fetch_feed(session, url) for url in RSS_FEEDS]
                await asyncio.gather(*tasks)
                logger.info(f"{ICONS['sync']} Polling cycle complete")
                await asyncio.sleep(POLL_INTERVAL)

def main():
    """Main entry point"""
    poller = RSSPoller()
    
    try:
        asyncio.run(poller.poll_feeds())
    except KeyboardInterrupt:
        logger.info(f"{ICONS['info']} RSS Feed polling service stopped")
    except Exception as e:
        logger.error(f"{ICONS['error']} Fatal error: {str(e)}")
        raise

if __name__ == "__main__":
    main() 