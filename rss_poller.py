import asyncio
import aiohttp
import feedparser
import redis
import uuid
import json
from datetime import datetime
import os
from typing import List, Dict, Any
import logging
from dotenv import load_dotenv
import time

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
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
REDIS_DB = int(os.getenv('REDIS_DB', '0'))

RSS_FEEDS = [
    'https://ambcrypto.com/feed/',
    'https://cointelegraph.com/rss',
    'https://news.bitcoin.com/feed/',
    'https://cryptonews.com/news/feed/',
    'https://bitcoinmagazine.com/feed',
    'https://decrypt.co/feed',
    'https://blog.coinbase.com/feed',
    'https://newsbtc.com/feed/'
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
        self.connect_to_redis()
        self.article_buffer = []
        self.is_ready = False
        
        # Create output directory
        self.output_dir = "article_exports"
        os.makedirs(self.output_dir, exist_ok=True)
        logger.info(f"{ICONS['info']} Initialized output directory: {self.output_dir}")

    def connect_to_redis(self, max_retries=3):
        """Establish Redis connection with retries"""
        retry_count = 0
        while retry_count < max_retries:
            try:
                self.redis_client = redis.Redis(
                    host=REDIS_HOST,
                    port=REDIS_PORT,
                    db=REDIS_DB,
                    decode_responses=True,
                    socket_timeout=5,
                    socket_connect_timeout=5
                )
                # Test connection
                self.redis_client.ping()
                logger.info(f"{ICONS['db']} Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
                return
            except redis.ConnectionError as e:
                retry_count += 1
                if retry_count == max_retries:
                    logger.error(f"{ICONS['error']} Could not connect to Redis after {max_retries} attempts")
                    raise
                logger.warning(f"{ICONS['warning']} Redis connection attempt {retry_count} failed, retrying...")
                time.sleep(2)

    def export_articles_to_json(self) -> str:
        """Export current articles to a JSON file"""
        if not self.article_buffer:
            logger.warning(f"{ICONS['warning']} No articles to export")
            return ""

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"articles_{timestamp}.json"
        filepath = os.path.join(self.output_dir, filename)

        export_data = {
            "timestamp": datetime.now().isoformat(),
            "total_articles": len(self.article_buffer),
            "articles": self.article_buffer
        }

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            logger.info(f"{ICONS['save']} Exported {len(self.article_buffer)} articles to {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"{ICONS['error']} Failed to export articles: {str(e)}")
            return ""

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
                            self.redis_client.setex(
                                f"article:{article_id}",
                                86400,
                                json.dumps(article)
                            )
                            self.article_buffer.append(article)
                            new_articles += 1
                            
                        if new_articles > 0:
                            logger.info(f"{ICONS['new']} Added {new_articles} articles from {url}")
                            logger.info(f"{ICONS['info']} Buffer size: {len(self.article_buffer)}/{REQUIRED_ARTICLES}")
                        
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

    async def initialize_buffer(self):
        """Initial polling until we have enough articles"""
        logger.info(f"{ICONS['sync']} Initializing article buffer (target: {REQUIRED_ARTICLES} articles)")
        async with aiohttp.ClientSession() as session:
            while len(self.article_buffer) < REQUIRED_ARTICLES:
                tasks = [self.fetch_feed(session, url) for url in RSS_FEEDS]
                await asyncio.gather(*tasks)
                if len(self.article_buffer) < REQUIRED_ARTICLES:
                    await asyncio.sleep(5)
            logger.info(f"{ICONS['success']} Buffer initialization complete!")
            self.export_articles_to_json()

    async def poll_feeds(self):
        """Main polling loop"""
        # First, initialize the buffer
        await self.initialize_buffer()
        
        # Then continue with regular polling
        logger.info(f"{ICONS['sync']} Starting regular polling cycle (interval: {POLL_INTERVAL}s)")
        async with aiohttp.ClientSession() as session:
            while True:
                tasks = [self.fetch_feed(session, url) for url in RSS_FEEDS]
                await asyncio.gather(*tasks)
                self.export_articles_to_json()
                logger.info(f"{ICONS['sync']} Polling cycle complete, waiting {POLL_INTERVAL} seconds...")
                await asyncio.sleep(POLL_INTERVAL)

def main():
    logger.info(f"{ICONS['info']} Starting RSS Polling Service")
    try:
        poller = RSSPoller()
        asyncio.run(poller.poll_feeds())
    except KeyboardInterrupt:
        logger.info(f"{ICONS['info']} Service stopped by user")
    except Exception as e:
        logger.error(f"{ICONS['error']} Fatal error: {str(e)}")
        raise

if __name__ == "__main__":
    main() 