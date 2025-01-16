import asyncio
import aiohttp
import feedparser
import redis
import uuid
import json
from datetime import datetime
import os

# Configuration
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_DB = 0

RSS_FEEDS = [
    'https://ambcrypto.com/feed/'
]

# Polling configuration
POLL_INTERVAL = 120  # 2 minutes
INITIAL_RETRY_DELAY = 5  # seconds
MAX_RETRY_DELAY = 300  # seconds
REQUIRED_ARTICLES = 15  # Number of articles needed before ready

class RSSPoller:
    def __init__(self):
        self.redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            decode_responses=True
        )
        self.article_buffer = []
        self.is_ready = False
        
        # Create output directory if it doesn't exist
        self.output_dir = "article_exports"
        os.makedirs(self.output_dir, exist_ok=True)

    def export_articles_to_json(self):
        """Export current articles to a JSON file"""
        if not self.article_buffer:
            print("No articles to export")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"articles_{timestamp}.json"
        filepath = os.path.join(self.output_dir, filename)

        export_data = {
            "timestamp": datetime.now().isoformat(),
            "total_articles": len(self.article_buffer),
            "articles": self.article_buffer
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        print(f"Exported {len(self.article_buffer)} articles to {filepath}")

    async def fetch_feed(self, session, url):
        delay = INITIAL_RETRY_DELAY
        while True:
            try:
                async with session.get(url) as response:
                    if response.status == 200:
                        content = await response.text()
                        feed = feedparser.parse(content)
                        
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
                            print(f"Stored article: {article['title']}")
                            print(f"Categories: {', '.join(categories)}")
                            print(f"Buffer size: {len(self.article_buffer)}/{REQUIRED_ARTICLES}")
                        
                        if len(self.article_buffer) >= REQUIRED_ARTICLES:
                            self.is_ready = True
                            # Export articles when buffer is full
                            self.export_articles_to_json()
                        return
                        
            except Exception as e:
                print(f"Error fetching {url}: {str(e)}")
                if delay > MAX_RETRY_DELAY:
                    print(f"Max retry delay reached for {url}")
                    return
                    
                print(f"Retrying in {delay} seconds...")
                await asyncio.sleep(delay)
                delay *= 2  # Exponential backoff

    async def initialize_buffer(self):
        """Initial polling until we have enough articles"""
        print(f"Initializing article buffer (target: {REQUIRED_ARTICLES} articles)")
        async with aiohttp.ClientSession() as session:
            while len(self.article_buffer) < REQUIRED_ARTICLES:
                tasks = [self.fetch_feed(session, url) for url in RSS_FEEDS]
                await asyncio.gather(*tasks)
                if len(self.article_buffer) < REQUIRED_ARTICLES:
                    await asyncio.sleep(5)
            print("Buffer initialization complete!")
            # Export initial batch of articles
            self.export_articles_to_json()

    async def poll_feeds(self):
        # First, initialize the buffer
        await self.initialize_buffer()
        
        # Then continue with regular polling
        async with aiohttp.ClientSession() as session:
            while True:
                tasks = [self.fetch_feed(session, url) for url in RSS_FEEDS]
                await asyncio.gather(*tasks)
                # Export articles after each polling cycle
                self.export_articles_to_json()
                await asyncio.sleep(POLL_INTERVAL)

def main():
    poller = RSSPoller()
    asyncio.run(poller.poll_feeds())

if __name__ == "__main__":
    main() 