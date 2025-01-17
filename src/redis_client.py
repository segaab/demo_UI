import aioredis
from loguru import logger
import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

class RedisClient:
    def __init__(self):
        """Initialize Redis client"""
        self.redis = None
        self.is_connected = False

    async def connect(self, host: str = '127.0.0.1', port: int = 6379, db: int = 0) -> bool:
        """Establish connection to Redis"""
        try:
            self.redis = await aioredis.from_url(
                f"redis://{host}:{port}/{db}",
                encoding="utf-8",
                decode_responses=True
            )
            await self.redis.ping()
            self.is_connected = True
            logger.success(f"Connected to Redis at {host}:{port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {str(e)}")
            self.is_connected = False
            return False

    async def close(self):
        """Close Redis connection"""
        if self.redis:
            await self.redis.close()
            self.is_connected = False
            logger.info("Redis connection closed")

    async def store_article(self, article: Dict[str, Any], expire_seconds: int = 86400) -> bool:
        """Store article with expiration"""
        if not self.is_connected:
            logger.error("Redis not connected")
            return False

        try:
            article_id = article.get('id')
            if not article_id:
                logger.error("Article missing ID")
                return False

            # Store article
            key = f"article:{article_id}"
            await self.redis.set(key, json.dumps(article), ex=expire_seconds)
            
            # Add to recent articles set
            score = datetime.fromisoformat(article['timestamp']).timestamp()
            await self.redis.zadd('recent_articles', {article_id: score})
            
            return True
        except Exception as e:
            logger.error(f"Error storing article: {str(e)}")
            return False

    async def get_recent_articles(self, limit: int = 15) -> List[Dict[str, Any]]:
        """Get most recent articles"""
        if not self.is_connected:
            logger.error("Redis not connected")
            return []

        try:
            # Get recent article IDs
            article_ids = await self.redis.zrevrange('recent_articles', 0, limit-1)
            
            # Fetch articles
            articles = []
            for article_id in article_ids:
                article_data = await self.redis.get(f"article:{article_id}")
                if article_data:
                    articles.append(json.loads(article_data))
            
            return articles
        except Exception as e:
            logger.error(f"Error fetching recent articles: {str(e)}")
            return []

    async def clear_cache(self) -> bool:
        """Clear all cached articles"""
        if not self.is_connected:
            logger.error("Redis not connected")
            return False

        try:
            # Clear article data
            async for key in self.redis.scan_iter("article:*"):
                await self.redis.delete(key)
            
            # Clear recent articles set
            await self.redis.delete('recent_articles')
            
            logger.info("Cache cleared successfully")
            return True
        except Exception as e:
            logger.error(f"Error clearing cache: {str(e)}")
            return False 