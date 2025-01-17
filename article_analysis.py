import json
import os
import requests
from datetime import datetime
from loguru import logger
from typing import List, Dict, Any

class ArticleAnalyzer:
    def __init__(self):
        """Initialize analyzer with directories"""
        self.articles_dir = "article_exports"
        self.analysis_dir = "analysis_outputs"
        os.makedirs(self.analysis_dir, exist_ok=True)
        os.makedirs(self.articles_dir, exist_ok=True)
        logger.info(f"Initialized directories: {self.analysis_dir}, {self.articles_dir}")

    def get_latest_articles(self) -> List[Dict[str, Any]]:
        """Get articles from most recent export"""
        try:
            files = sorted([f for f in os.listdir(self.articles_dir) if f.startswith("articles_")])
            if not files:
                logger.error("No article files found in article_exports")
                return []
            
            latest = files[-1]
            logger.info(f"Processing latest articles file: {self.articles_dir}/{latest}")
            
            with open(os.path.join(self.articles_dir, latest), 'r') as f:
                data = json.load(f)
                logger.info(f"Successfully loaded {len(data['articles'])} articles from {self.articles_dir}/{latest}")
                return data["articles"]
        except Exception as e:
            logger.error(f"Error reading articles: {str(e)}")
            return []

    def prepare_prompt(self, articles: List[Dict[str, Any]]) -> str:
        """Prepare analysis prompt from articles"""
        prompt = "Analyze these crypto news articles and provide:\n"
        prompt += "1. Key market trends\n"
        prompt += "2. Major developments\n"
        prompt += "3. Overall market sentiment\n\n"
        prompt += "Articles:\n"
        
        for article in articles:
            prompt += f"- {article['title']}\n"
            prompt += f"  Summary: {article['description'][:200]}...\n\n"
        
        return prompt

    async def analyze_articles(self) -> Dict[str, Any]:
        """Analyze articles using Ollama"""
        articles = self.get_latest_articles()
        if not articles:
            return {"error": "No articles available"}

        logger.info("Starting article analysis...")
        prompt = self.prepare_prompt(articles)
        logger.info(f"Prepared prompt with {len(articles)} articles")

        try:
            # Call Ollama API
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "mistral",
                    "prompt": prompt,
                    "stream": False
                }
            )
            
            if response.status_code == 200:
                analysis = response.json()["response"]
                logger.info("Successfully received analysis from Ollama")
            else:
                logger.error(f"Ollama API error: {response.status_code}")
                return {"error": "Analysis failed"}

            # Save analysis
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"analysis_{timestamp}.json"
            output_path = os.path.join(self.analysis_dir, output_file)
            
            analysis_data = {
                "timestamp": datetime.now().isoformat(),
                "articles_analyzed": len(articles),
                "analysis": analysis
            }

            with open(output_path, 'w') as f:
                json.dump(analysis_data, f, indent=2)
            
            # Also save as latest
            with open(os.path.join(self.analysis_dir, "latest_analysis.json"), 'w') as f:
                json.dump(analysis_data, f, indent=2)

            logger.info(f"Analysis complete and saved to {output_path}")
            logger.info(f"Total articles analyzed: {len(articles)}")
            
            return analysis_data

        except Exception as e:
            logger.error(f"Analysis error: {str(e)}")
            return {"error": str(e)}

async def main():
    """Main function"""
    logger.info("Starting Article Analysis Service")
    analyzer = ArticleAnalyzer()
    await analyzer.analyze_articles()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main()) 