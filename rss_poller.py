import asyncio
import aiohttp
import feedparser
import redis
import uuid
import json
from datetime import datetime

# Redis configuration
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_DB = 0

# RSS feeds to poll (example feeds)
RSS_FEEDS = [
    'https://ambcrypto.com/feed/'
]

# How often to poll (in seconds)
POLL_INTERVAL = 300  # 5 minutes

class RSSPoller:
    def __init__(self):
        self.redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            decode_responses=True
        )

    async def fetch_feed(self, session, url):
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    content = await response.text()
                    feed = feedparser.parse(content)
                    
                    for entry in feed.entries:
                        article_id = str(uuid.uuid4())
                        article = {
                            'id': article_id,
                            'title': entry.get('title', ''),
                            'link': entry.get('link', ''),
                            'description': entry.get('description', ''),
                            'published': entry.get('published', ''),
                            'timestamp': datetime.now().isoformat()
                        }
                        
                        # Store in Redis with 24-hour expiration
                        self.redis_client.setex(
                            f"article:{article_id}",
                            86400,  # 24 hours in seconds
                            json.dumps(article)
                        )
                        print(f"Stored article: {article['title']}")
                        
        except Exception as e:
            print(f"Error fetching {url}: {str(e)}")

    async def poll_feeds(self):
        async with aiohttp.ClientSession() as session:
            while True:
                tasks = [self.fetch_feed(session, url) for url in RSS_FEEDS]
                await asyncio.gather(*tasks)
                await asyncio.sleep(POLL_INTERVAL)

def main():
    poller = RSSPoller()
    asyncio.run(poller.poll_feeds())

if __name__ == "__main__":
    main() 