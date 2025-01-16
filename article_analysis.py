import json
import os
import logging
from datetime import datetime
import asyncio
import aiohttp
from typing import List, Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('analysis.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ArticleAnalyzer:
    def __init__(self):
        self.ollama_url = "http://localhost:11434/api/generate"  # Default Ollama API endpoint
        self.model = "llama2"  # Default model
        self.latest_analysis_file = "latest_analysis.json"
        
        # Create analysis output directory
        self.output_dir = "analysis_outputs"
        os.makedirs(self.output_dir, exist_ok=True)
        logger.info(f"Initialized ArticleAnalyzer with output directory: {self.output_dir}")

    def load_articles(self, filepath: str) -> List[Dict[str, Any]]:
        """Load articles from a JSON file"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                logger.info(f"Successfully loaded {len(data['articles'])} articles from {filepath}")
                return data['articles']
        except Exception as e:
            logger.error(f"Error loading articles from {filepath}: {str(e)}")
            return []

    def prepare_prompt(self, articles: List[Dict[str, Any]]) -> str:
        """Prepare the analysis prompt from articles"""
        articles_text = "\n\n".join([
            f"Title: {article['title']}\nDescription: {article['description']}\n"
            for article in articles
        ])
        
        prompt = f"""Use the following articles to answer the questions:

{articles_text}

Please provide:
1. Analysis (2-5 pages)
2. Trading Ideas (1 for each market category that is related to the articles)
3. Tickers to watch (All related tickers, e.g., BTCUSD, ETHUSD, SOLUSD, etc.)

Format your response in clear sections with headers."""

        logger.info(f"Prepared prompt with {len(articles)} articles")
        return prompt

    async def analyze_articles(self, articles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Send articles to Ollama for analysis"""
        prompt = self.prepare_prompt(articles)
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.ollama_url,
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False
                    }
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info("Successfully received analysis from Ollama")
                        return {
                            "timestamp": datetime.now().isoformat(),
                            "analysis": result["response"],
                            "articles_analyzed": len(articles)
                        }
                    else:
                        error_msg = f"Ollama API error: {response.status}"
                        logger.error(error_msg)
                        return {"error": error_msg}
                        
        except Exception as e:
            error_msg = f"Error during analysis: {str(e)}"
            logger.error(error_msg)
            return {"error": error_msg}

    def save_analysis(self, analysis: Dict[str, Any], timestamp: str) -> str:
        """Save analysis results to file"""
        filename = f"analysis_{timestamp}.json"
        filepath = os.path.join(self.output_dir, filename)
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(analysis, f, indent=2, ensure_ascii=False)
            
            # Update latest analysis symlink
            latest_path = os.path.join(self.output_dir, self.latest_analysis_file)
            if os.path.exists(latest_path):
                os.remove(latest_path)
            os.symlink(filepath, latest_path)
            
            logger.info(f"Analysis saved to {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Error saving analysis: {str(e)}")
            return ""

async def main():
    analyzer = ArticleAnalyzer()
    
    # Find the most recent articles file
    article_dir = "article_exports"
    try:
        files = [f for f in os.listdir(article_dir) if f.startswith("articles_")]
        if not files:
            logger.error("No article files found")
            return
        
        latest_file = max(files)
        filepath = os.path.join(article_dir, latest_file)
        logger.info(f"Processing latest articles file: {filepath}")
        
        # Load and analyze articles
        articles = analyzer.load_articles(filepath)
        if not articles:
            logger.error("No articles loaded")
            return
        
        # Run analysis
        analysis = await analyzer.analyze_articles(articles)
        if "error" in analysis:
            logger.error(f"Analysis failed: {analysis['error']}")
            return
        
        # Save results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        saved_path = analyzer.save_analysis(analysis, timestamp)
        if saved_path:
            logger.info(f"Analysis complete and saved to {saved_path}")
        else:
            logger.error("Failed to save analysis")
            
    except Exception as e:
        logger.error(f"Unexpected error in main: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main()) 