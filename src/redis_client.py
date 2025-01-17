import aioredis
from loguru import logger
import json
from typing import Dict, Any

class RedisClient:
    def __init__(self):
        self.redis = None

    async def setup(self):
        """Basic Redis connection setup"""
        try:
            self.redis = await aioredis.from_url(
                f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}",
                encoding="utf-8",
                decode_responses=True
            )
            await self.redis.ping()
            logger.info(f"Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
        except Exception as e:
            logger.error(f"Redis connection failed: {str(e)}")
            raise

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