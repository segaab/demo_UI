import json
import os
import requests
from datetime import datetime
from loguru import logger
from typing import List, Dict, Any

class ArticleAnalyzer:
    def __init__(self):
        self.articles_dir = "article_exports"
        self.analysis_dir = "analysis_outputs"
        self.model = "QuantFactory/Llama-3-8B-Instruct-Finance-RAG-GGUF"
        os.makedirs(self.analysis_dir, exist_ok=True)
        os.makedirs(self.articles_dir, exist_ok=True)
        logger.info(f"Initialized ArticleAnalyzer with model: {self.model}")

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
        articles_text = ""
        for article in articles:
            articles_text += f"Title: {article['title']}\n"
            articles_text += f"Content: {article['description']}\n\n"

        prompt = f"""Use the following articles to provide:

1. Analysis (2-5 pages):
   - Market overview
   - Key trends and patterns
   - Technical analysis insights
   - Fundamental factors
   - Risk assessment

2. Trading Ideas:
   - One actionable trade idea for each market category
   - Entry/exit points
   - Risk management suggestions

3. Tickers to Watch:
   - All related trading pairs (e.g., BTCUSD, ETHUSD, SOLUSD)
   - Key price levels
   - Volume analysis

Articles:
{articles_text}

Please provide a detailed, professional analysis."""

        return prompt

    async def analyze_articles(self) -> Dict[str, Any]:
        """Analyze articles using Ollama with finance model"""
        articles = self.get_latest_articles()
        if not articles:
            return {"error": "No articles available"}

        prompt = self.prepare_prompt(articles)
        
        try:
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "temperature": 0.7,
                    "top_p": 0.9
                }
            )
            
            if response.status_code != 200:
                raise Exception(f"Ollama API error: {response.status_code}")

            analysis = response.json()["response"]
            
            # Save analysis with metadata
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            analysis_data = {
                "timestamp": datetime.now().isoformat(),
                "model": self.model,
                "articles_analyzed": len(articles),
                "analysis": analysis,
                "article_ids": [a["id"] for a in articles]
            }

            # Save timestamped and latest versions
            self._save_analysis(analysis_data, timestamp)
            
            return analysis_data

        except Exception as e:
            logger.error(f"Analysis error: {str(e)}")
            return {"error": str(e)}

    def _save_analysis(self, analysis_data: Dict[str, Any], timestamp: str):
        """Save analysis to both timestamped and latest files"""
        # Save timestamped version
        output_file = f"analysis_{timestamp}.json"
        output_path = os.path.join(self.analysis_dir, output_file)
        
        with open(output_path, 'w') as f:
            json.dump(analysis_data, f, indent=2)
        
        # Save as latest
        latest_path = os.path.join(self.analysis_dir, "latest_analysis.json")
        with open(latest_path, 'w') as f:
            json.dump(analysis_data, f, indent=2)
        
        logger.info(f"Analysis saved to {output_path}")

async def main():
    """Main function"""
    logger.info("Starting Article Analysis Service")
    analyzer = ArticleAnalyzer()
    await analyzer.analyze_articles()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main()) 