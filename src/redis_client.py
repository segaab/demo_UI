import redis.asyncio as aioredis
from loguru import logger
from config import REDIS_HOST, REDIS_PORT, REDIS_DB
import json
from typing import List, Dict, Any

class RedisClient:
    def __init__(self):
        self.redis = None

    async def setup(self):
        """Async initialization"""
        self.redis = await aioredis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            decode_responses=True
        )
        await self.redis.ping()
        logger.info(f"Successfully connected to Redis at {REDIS_HOST}:{REDIS_PORT}")

    async def close(self):
        """Close Redis connection"""
        if self.redis:
            await self.redis.close()

    async def is_article_exists(self, article_link: str) -> bool:
        """Check if article link hash exists in Redis"""
        try:
            key = f"article:{article_link}"
            return bool(await self.redis.exists(key))
        except Exception as e:
            logger.error(f"Redis error while checking article: {str(e)}")
            return False

    async def save_article(self, article_link: str, article_data: dict = None) -> None:
        """Save article link and data to Redis"""
        try:
            key = f"article:{article_link}"
            if article_data:
                # Store the full article data
                await self.redis.set(key, json.dumps(article_data), ex=86400)  # 24 hour expiry
            else:
                # Just store the link
                await self.redis.set(key, "1", ex=86400)
        except Exception as e:
            logger.error(f"Redis error while saving article: {str(e)}")

    async def get_recent_articles(self, count: int = 15) -> List[Dict[str, Any]]:
        """Get recent articles from Redis"""
        try:
            # Get all article keys
            keys = await self.redis.keys("article:*")
            articles = []
            
            for key in keys:
                value = await self.redis.get(key)
                try:
                    # Try to parse as JSON (for full article data)
                    article_data = json.loads(value)
                    articles.append(article_data)
                except json.JSONDecodeError:
                    # Skip articles that only have link stored
                    continue
            
            # Sort by timestamp and return most recent
            articles.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            return articles[:count]
            
        except Exception as e:
            logger.error(f"Redis error while getting recent articles: {str(e)}")
            return []

    async def clear_cache(self):
        """Clear all articles from Redis"""
        try:
            # Delete all article keys
            keys = await self.redis.keys("article:*")
            if keys:
                await self.redis.delete(*keys)
            logger.info("Redis cache cleared successfully")
        except Exception as e:
            logger.error(f"Redis error while clearing cache: {str(e)}") 