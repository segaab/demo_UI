import redis
import json
from loguru import logger
from typing import Dict, Any, List

class RedisClient:
    def __init__(self):
        self.redis = None
        self.is_connected = False

    def connect(self, host: str = '127.0.0.1', port: int = 6381, db: int = 0) -> bool:
        """Connect to Redis"""
        try:
            self.redis = redis.Redis(
                host=host,
                port=port,
                db=db,
                decode_responses=True
            )
            self.redis.ping()  # Test connection
            self.is_connected = True
            logger.info(f"Connected to Redis at {host}:{port}")
            return True
        except Exception as e:
            logger.error(f"Redis connection failed: {str(e)}")
            return False

    def save_article(self, key: str, data: Dict[str, Any]):
        """Save article data"""
        if not self.is_connected:
            raise ConnectionError("Redis not connected")
        self.redis.set(key, json.dumps(data), ex=86400)  # 24h expiry

    def get_article(self, key: str) -> Dict[str, Any]:
        """Get article data"""
        if not self.is_connected:
            raise ConnectionError("Redis not connected")
        data = self.redis.get(key)
        return json.loads(data) if data else None

    def get_recent_articles(self, limit: int = 15) -> List[Dict[str, Any]]:
        """Get most recent articles"""
        if not self.is_connected:
            raise ConnectionError("Redis not connected")
        try:
            keys = self.redis.keys("article:*")
            articles = []
            for key in keys:
                data = self.get_article(key)
                if data:
                    articles.append(data)
            articles.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            return articles[:limit]
        except Exception as e:
            logger.error(f"Error getting articles: {str(e)}")
            return []

    def clear_cache(self):
        """Clear all articles"""
        if not self.is_connected:
            raise ConnectionError("Redis not connected")
        try:
            keys = self.redis.keys("article:*")
            if keys:
                self.redis.delete(*keys)
            logger.info("Cache cleared")
        except Exception as e:
            logger.error(f"Error clearing cache: {str(e)}") 