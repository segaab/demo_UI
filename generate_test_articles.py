import json
import os
from datetime import datetime, timedelta
import uuid

# Sample article data
SAMPLE_ARTICLES = [
    {
        "title": "Bitcoin Surges Past $50,000 as Institutional Interest Grows",
        "description": "Bitcoin has surpassed the $50,000 mark for the first time in 2024, driven by increased institutional adoption and the recent approval of spot Bitcoin ETFs.",
        "categories": ["Cryptocurrency", "Bitcoin", "Markets", "ETF"],
        "source": "https://ambcrypto.com/feed/"
    },
    {
        "title": "Ethereum Layer 2 Solutions See Record Growth in TVL",
        "description": "Ethereum L2 scaling solutions have reached a new all-time high in Total Value Locked (TVL), with Arbitrum and Optimism leading the charge.",
        "categories": ["Ethereum", "Layer 2", "DeFi", "Scaling"],
        "source": "https://ambcrypto.com/feed/"
    },
    {
        "title": "SEC Commissioner Discusses Crypto Regulatory Framework",
        "description": "A SEC Commissioner has outlined potential changes to cryptocurrency regulations, highlighting the need for clearer guidelines in the digital asset space.",
        "categories": ["Regulation", "SEC", "Cryptocurrency", "Policy"],
        "source": "https://ambcrypto.com/feed/"
    },
    {
        "title": "Solana DeFi Ecosystem Experiences Rapid Expansion",
        "description": "The Solana blockchain's DeFi ecosystem has seen significant growth, with new protocols and increased user adoption driving SOL price higher.",
        "categories": ["Solana", "DeFi", "Blockchain", "Trading"],
        "source": "https://ambcrypto.com/feed/"
    },
    {
        "title": "Major Bank Announces Crypto Custody Services",
        "description": "A leading financial institution has revealed plans to offer cryptocurrency custody services to institutional clients, marking another step in crypto adoption.",
        "categories": ["Banking", "Custody", "Institutional", "Adoption"],
        "source": "https://ambcrypto.com/feed/"
    }
]

def generate_test_articles(num_articles=15):
    """Generate test articles and save them to a JSON file"""
    # Create output directory if it doesn't exist
    output_dir = "article_exports"
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate articles
    articles = []
    base_time = datetime.now()
    
    for i in range(num_articles):
        # Use modulo to cycle through sample articles
        sample = SAMPLE_ARTICLES[i % len(SAMPLE_ARTICLES)]
        
        # Create article with unique ID and timestamp
        article = {
            'id': str(uuid.uuid4()),
            'title': sample['title'],
            'link': f"https://example.com/article/{i}",
            'description': sample['description'],
            'published': (base_time - timedelta(hours=i)).isoformat(),
            'categories': sample['categories'],
            'source': sample['source'],
            'timestamp': (base_time - timedelta(hours=i)).isoformat()
        }
        articles.append(article)
    
    # Create export data
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    export_data = {
        "timestamp": datetime.now().isoformat(),
        "total_articles": len(articles),
        "articles": articles
    }
    
    # Save to file
    filename = f"articles_{timestamp}.json"
    filepath = os.path.join(output_dir, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, indent=2, ensure_ascii=False)
    
    print(f"Generated {len(articles)} test articles and saved to {filepath}")
    return filepath

if __name__ == "__main__":
    filepath = generate_test_articles(15)
    
    # Verify the generated file
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
        print("\nVerification:")
        print(f"Total articles: {data['total_articles']}")
        print(f"First article title: {data['articles'][0]['title']}")
        print(f"Last article title: {data['articles'][-1]['title']}") 