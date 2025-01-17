import aioredis
from loguru import logger
import json
from typing import Dict, Any, List

class RedisClient:
    def __init__(self):
        self.redis = None

    async def connect(self, host: str, port: int, db: int = 0) -> bool:
        """Connect to Redis"""
        try:
            self.redis = await aioredis.from_url(
                f"redis://{host}:{port}/{db}",
                encoding="utf-8",
                decode_responses=True
            )
            await self.redis.ping()
            logger.info(f"Connected to Redis at {host}:{port}")
            return True
        except Exception as e:
            logger.error(f"Redis connection failed: {str(e)}")
            return False

    async def close(self):
        """Close Redis connection"""
        if self.redis:
            await self.redis.close()

    async def save_article(self, key: str, data: Dict[str, Any]):
        """Save article data"""
        await self.redis.set(key, json.dumps(data), ex=86400)  # 24h expiry

    async def get_article(self, key: str) -> Dict[str, Any]:
        """Get article data"""
        data = await self.redis.get(key)
        return json.loads(data) if data else None

    async def get_recent_articles(self, limit: int = 15) -> List[Dict[str, Any]]:
        """Get most recent articles from Redis"""
        try:
            keys = await self.redis.keys("article:*")
            if not keys:
                return []
            
            articles = []
            for key in keys:
                data = await self.get_article(key)
                if data:
                    articles.append(data)
            
            # Sort by timestamp and return limited number
            articles.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            return articles[:limit]
        except Exception as e:
            logger.error(f"Error getting recent articles: {str(e)}")
            return []

    async def clear_cache(self):
        """Clear all articles from Redis"""
        try:
            keys = await self.redis.keys("article:*")
            if keys:
                await self.redis.delete(*keys)
            logger.info("Redis cache cleared")
        except Exception as e:
            logger.error(f"Error clearing cache: {str(e)}") 