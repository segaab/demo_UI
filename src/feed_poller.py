import asyncio
import aiohttp
import feedparser
import json
import uuid
from datetime import datetime, timedelta
from loguru import logger
from typing import Dict, Any, List
import os
import email.utils  # Add this import at the top
import re  # Make sure this is at the top with other imports

from config import (
    RSS_FEEDS,
    POLLING_INTERVAL,
    INITIAL_RETRY_DELAY,
    MAX_RETRY_DELAY,
    LOG_LEVEL,
    ARTICLES_BUFFER_SIZE,
    CLOUDFLARE_POLLING_INTERVAL,
    is_cloudflare_feed
)
from redis_client import RedisClient

class FeedPoller:
    def __init__(self, send_to_clients):
        self.send_to_clients = send_to_clients
        self.article_buffer = []
        self.is_ready = False
        self.redis_client = None  # Will be initialized in setup
        
        # Create logs directory
        logs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
        os.makedirs(logs_dir, exist_ok=True)
        
        logger.add(
            os.path.join(logs_dir, "feed_poller_{time}.log"),
            rotation="24h",
            level=LOG_LEVEL
        )
        
        logger.info("Feed Poller initialized")

    async def setup(self):
        """Async initialization"""
        self.redis_client = RedisClient()
        await self.redis_client.setup()
        
        # Initialize buffer from Redis
        if os.getenv('REDIS_CLEAR_ON_START', '').lower() == 'true':
            logger.info("Clearing Redis cache on startup...")
            await self.redis_client.clear_cache()
        else:
            # Load existing articles from Redis
            await self.initialize_buffer()
        
        logger.info("Feed Poller setup completed")

    async def fetch_feed(self, session: aiohttp.ClientSession, feed_url: str) -> Dict[str, Any]:
        """Fetch RSS feed with exponential backoff retry mechanism"""
        print(f"\n🔄 Fetching feed from: {feed_url}")
        delay = INITIAL_RETRY_DELAY
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0'
        }
        
        # Remove problematic feeds or use alternative URLs
        if 'coinpaprika.com' in feed_url:
            # Try alternative API or RSS feed URL
            feed_url = feed_url.replace('news/feed', 'news/feed.xml')
            # Or remove this feed entirely
            logger.warning(f"Skipping Cloudflare-protected feed: {feed_url}")
            return None

        timeout = aiohttp.ClientTimeout(
            total=30,
            connect=10,
            sock_read=20
        )
        
        while True:
            try:
                async with session.get(
                    feed_url, 
                    headers=headers, 
                    timeout=timeout,
                    allow_redirects=True
                ) as response:
                    print(f"📡 Got response from {feed_url} (Status: {response.status})")
                    if response.status == 200:
                        content = await response.text()
                        print(f"✅ Successfully fetched feed from: {feed_url}")
                        
                        # Check content length
                        print(f"📄 Content length: {len(content)} bytes")
                        
                        if len(content) < 100:  # Suspicious if content is too short
                            print(f"⚠️  Warning: Very short content from {feed_url}")
                            print(f"Content preview: {content[:100]}")
                            return None
                            
                        feed = feedparser.parse(content)
                        if feed.entries:
                            print(f"📚 Found {len(feed.entries)} entries in feed")
                        return feed
                    else:
                        print(f"❌ HTTP {response.status} error from: {feed_url}")
                        return None
                    
            except asyncio.TimeoutError:
                print(f"⏰ Timeout while fetching {feed_url}")
            except Exception as e:
                print(f"❌ Error fetching {feed_url}: {str(e)}")
            
            logger.info(f"Retrying {feed_url} after {delay} seconds...")
            await asyncio.sleep(delay)
            delay *= 2

    async def initialize_buffer(self):
        """Initialize article buffer from Redis"""
        print("\n📦 Initializing article buffer from Redis...")
        try:
            # Get existing articles from Redis
            existing_articles = await self.redis_client.get_recent_articles(ARTICLES_BUFFER_SIZE)
            if existing_articles:
                print(f"📦 Found latest article in Redis")
                self.article_buffer = existing_articles
                self.is_ready = True
                print(f"✅ Buffer initialized with latest article from Redis")
                return
            else:
                print("📭 No existing articles found in Redis")
                self.article_buffer = []
        except Exception as e:
            print(f"❌ Error initializing buffer: {str(e)}")
            self.article_buffer = []

    def _parse_date(self, entry: Dict[str, Any]) -> str:
        """Convert various date formats to ISO format"""
        # Try different date fields in order of preference
        date_fields = ['published', 'pubDate', 'updated', 'created']
        
        for field in date_fields:
            date_str = entry.get(field)
            if date_str:
                try:
                    # Try parsing as RFC 2822 (common in RSS feeds)
                    parsed_date = email.utils.parsedate_to_datetime(date_str)
                    # Ensure timezone info is preserved
                    if parsed_date.tzinfo is None:
                        # If no timezone info, assume UTC
                        parsed_date = parsed_date.replace(tzinfo=datetime.timezone.utc)
                    # Format with timezone info
                    return parsed_date.isoformat()
                except Exception as e:
                    logger.debug(f"Failed to parse date '{date_str}' from field '{field}': {str(e)}")
                    try:
                        # Try direct ISO format parsing
                        parsed_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                        return parsed_date.isoformat()
                    except Exception as e:
                        logger.debug(f"Failed ISO parsing for date '{date_str}': {str(e)}")
                        continue
        
        # If no valid date found, use current time in UTC
        current_time = datetime.now(datetime.timezone.utc)
        logger.warning(f"No valid date found in entry, using current UTC time: {current_time.isoformat()}")
        return current_time.isoformat()

    def _extract_categories(self, entry: Dict[str, Any]) -> List[Dict[str, str]]:
        """Extract categories from RSS entry"""
        categories = []
        
        try:
            # Try RSS tags/categories
            if 'tags' in entry:
                for tag in entry.tags:
                    if hasattr(tag, 'term'):
                        categories.append({"term": tag.term})
            elif 'category' in entry:
                if isinstance(entry.category, list):
                    for cat in entry.category:
                        if isinstance(cat, str):
                            categories.append({"term": cat})
                        elif hasattr(cat, 'term'):
                            categories.append({"term": cat.term})
                else:
                    categories.append({"term": entry.category})
                    
        except Exception as e:
            logger.debug(f"Error extracting categories: {str(e)}")
        
        # Always ensure at least one category
        if not categories:
            categories.append({"term": "Cryptocurrency"})
            
        return categories

    def _clean_content(self, content: str) -> str:
        """Clean the content by removing alt attributes from img tags"""
        try:
            # Remove alt attributes from img tags
            cleaned = re.sub(r'<img([^>]*?)alt="[^"]*"([^>]*?)>', r'<img\1\2>', content)
            # Also handle single quotes
            cleaned = re.sub(r"<img([^>]*?)alt='[^']*'([^>]*?)>", r'<img\1\2>', cleaned)
            return cleaned
        except Exception as e:
            logger.debug(f"Error cleaning content: {str(e)}")
            return content

    async def process_feed(self, session: aiohttp.ClientSession, feed_url: str) -> None:
        """Process a single RSS feed"""
        feed_data = await self.fetch_feed(session, feed_url)
        if not feed_data or not feed_data.entries:
            print(f"⚠️  Skipping feed processing for: {feed_url}")
            return

        # Process all entries in the feed
        new_articles = []
        print(f"\n📝 Processing {len(feed_data.entries)} entries from: {feed_url}")
        
        for entry in feed_data.entries:
            article_link = entry.link

            # If we have enough articles and this one exists, skip it
            if len(self.article_buffer) >= ARTICLES_BUFFER_SIZE and await self.redis_client.is_article_exists(article_link):
                continue

            # Clean the content before creating article
            content = entry.get("summary", "")
            cleaned_content = self._clean_content(content)

            # Create article data
            article = {
                "id": str(uuid.uuid4()),
                "title": entry.title,
                "content": cleaned_content,  # Use cleaned content
                "source": feed_url.split('/')[2],
                "timestamp": self._parse_date(entry),
                "url": article_link,
                "imageUrl": self._extract_image_url(entry),
                "categories": self._extract_categories(entry)
            }

            # Save article to Redis and buffer
            await self.redis_client.save_article(article_link, article)
            new_articles.append(article)
            print(f"📰 New article: {article['title']}")

        if new_articles:
            # Update the global article buffer
            self.article_buffer.extend(new_articles)
            self.article_buffer.sort(
                key=lambda x: datetime.fromisoformat(x["timestamp"]), 
                reverse=True
            )
            self.article_buffer = self.article_buffer[:ARTICLES_BUFFER_SIZE]
            
            print(f"\n✨ Added {len(new_articles)} new articles (Buffer size: {len(self.article_buffer)})")

            if len(self.article_buffer) >= ARTICLES_BUFFER_SIZE and not self.is_ready:
                self.is_ready = True
                print(f"✅ Service ready! Buffer contains {len(self.article_buffer)} articles")

            # Send latest article to all connected clients
            latest_article = new_articles[0]
            await self.send_to_clients({
                "articles": [latest_article]
            })

    def _extract_image_url(self, entry: Dict[str, Any]) -> str:
        """Extract image URL from RSS entry"""
        # Try different common RSS image locations
        try:
            # Try media:content
            if 'media_content' in entry:
                for media in entry.media_content:
                    if media.get('type', '').startswith('image/'):
                        return media['url']
            
            # Try media:thumbnail
            if 'media_thumbnail' in entry and entry.media_thumbnail:
                return entry.media_thumbnail[0]['url']
            
            # Try enclosures
            if 'enclosures' in entry and entry.enclosures:
                for enclosure in entry.enclosures:
                    if enclosure.get('type', '').startswith('image/'):
                        return enclosure.get('href', '')
            
            # Try to find image in content
            if 'content' in entry and entry.content:
                import re
                content = entry.content[0].value
                img_match = re.search(r'<img[^>]+src="([^">]+)"', content)
                if img_match:
                    return img_match.group(1)
                    
        except Exception as e:
            logger.debug(f"Error extracting image URL: {str(e)}")
        
        # Return empty string if no image found
        return ""

    async def get_initial_articles(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get the buffered articles"""
        if not self.is_ready:
            print("⏳ Service not ready - still collecting initial articles")
            return {"articles": [], "status": "initializing"}
            
        logger.info(f"Returning {len(self.article_buffer)} initial articles")
        return {
            "articles": self.article_buffer,
            "status": "ready"
        }

    async def poll_feeds(self) -> None:
        """Poll all RSS feeds concurrently"""
        print("\n🚀 Starting RSS Feed Polling Service")
        
        # Group feeds by type
        cloudflare_feeds = [feed for feed in RSS_FEEDS if is_cloudflare_feed(feed)]
        regular_feeds = [feed for feed in RSS_FEEDS if not is_cloudflare_feed(feed)]
        
        print(f"\n📊 Feed distribution:")
        print(f"  • Cloudflare-protected feeds: {len(cloudflare_feeds)} (5 min interval)")
        print(f"  • Regular feeds: {len(regular_feeds)} (1 min interval)")
        
        try:
            # Initialize buffer from Redis
            await self.initialize_buffer()
            
            async with aiohttp.ClientSession() as session:
                print("\n📡 Starting initial feed polling...")
                
                # Keep polling until we have enough articles
                while len(self.article_buffer) < ARTICLES_BUFFER_SIZE:
                    print(f"\n📥 Collecting articles ({len(self.article_buffer)}/{ARTICLES_BUFFER_SIZE})...")
                    tasks = [self.process_feed(session, feed_url) for feed_url in RSS_FEEDS]
                    await asyncio.gather(*tasks)
                    
                    if len(self.article_buffer) < ARTICLES_BUFFER_SIZE:
                        await asyncio.sleep(5)
                
                self.is_ready = True
                print(f"✅ Service ready! Buffer contains {len(self.article_buffer)} articles")

                # Track last poll time for Cloudflare feeds
                last_cloudflare_poll = datetime.now()
                
                # Then continue with regular polling
                while True:
                    current_time = datetime.now()
                    
                    # Always poll regular feeds
                    if regular_feeds:
                        tasks = [self.process_feed(session, feed_url) for feed_url in regular_feeds]
                        await asyncio.gather(*tasks)
                    
                    # Poll Cloudflare-protected feeds every 5 minutes
                    if (current_time - last_cloudflare_poll).total_seconds() >= CLOUDFLARE_POLLING_INTERVAL:
                        print(f"\n🔄 Polling Cloudflare-protected feeds... ({current_time.strftime('%H:%M:%S')})")
                        tasks = [self.process_feed(session, feed_url) for feed_url in cloudflare_feeds]
                        await asyncio.gather(*tasks)
                        last_cloudflare_poll = current_time
                    
                    print(f"✅ Polling cycle complete - Buffer contains {len(self.article_buffer)} articles")
                    await asyncio.sleep(POLLING_INTERVAL)
                    
        except Exception as e:
            print(f"❌ Critical error in polling service: {str(e)}")
            raise

    def cleanup_old_articles(self):
        """Remove articles older than X days"""
        cutoff = datetime.now() - timedelta(days=7)
        self.article_buffer = [
            article for article in self.article_buffer
            if datetime.fromisoformat(article['timestamp']) > cutoff
        ]

def main():
    """Main entry point"""
    poller = FeedPoller()
    
    try:
        asyncio.run(poller.poll_feeds())
    except KeyboardInterrupt:
        logger.info("RSS Feed polling service stopped")

if __name__ == "__main__":
    main() 