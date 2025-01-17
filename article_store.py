import json
import os
from datetime import datetime
from typing import List, Dict, Any
from loguru import logger

class ArticleStore:
    def __init__(self):
        self.articles_dir = "article_exports"
        self.latest_file = None
        os.makedirs(self.articles_dir, exist_ok=True)
        logger.info(f"Initialized ArticleStore in {self.articles_dir}")

    def save_articles(self, articles: List[Dict[str, Any]]) -> str:
        """Save articles to JSON file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"articles_{timestamp}.json"
        filepath = os.path.join(self.articles_dir, filename)
        
        data = {
            "timestamp": datetime.now().isoformat(),
            "total_articles": len(articles),
            "articles": articles
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        self.latest_file = filepath
        return filepath

    def get_latest_articles(self, limit: int = 15) -> List[Dict[str, Any]]:
        """Get most recent articles"""
        try:
            files = sorted([f for f in os.listdir(self.articles_dir) if f.startswith("articles_")])
            if not files:
                return []
            
            latest = files[-1]
            with open(os.path.join(self.articles_dir, latest), 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data["articles"][:limit]
        except Exception as e:
            logger.error(f"Error reading articles: {str(e)}")
            return [] 