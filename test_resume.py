#!/usr/bin/env python3
"""
Test resume functionality.
"""

import asyncio
import sys
from pathlib import Path
import yaml

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from crawler.core.crawler import WikiaCrawler


def load_config() -> dict:
    """Load crawler configuration from YAML file."""
    config_path = Path("config/crawler_config.yaml")
    
    with open(config_path, 'r') as f:
        full_config = yaml.safe_load(f)
    
    crawler_config = full_config['crawler']
    
    config = {
        'respect_robots_txt': crawler_config.get('respect_robots_txt', True),
        'user_agent': crawler_config.get('user_agent', 'WikiaAnalyzer/0.1.0'),
        'default_delay_seconds': crawler_config.get('default_delay_seconds', 1.0),
        'max_requests_per_minute': crawler_config.get('max_requests_per_minute', 60),
        'target_namespaces': crawler_config.get('target_namespaces', ['Main']),
        'timeout_seconds': crawler_config.get('timeout_seconds', 30),
        'max_retries': crawler_config.get('max_retries', 3),
        'exclude_patterns': crawler_config.get('exclude_patterns', []),
        'save_state_every_n_pages': crawler_config.get('save_state_every_n_pages', 10),
    }
    
    return config


async def test_resume():
    """Test resume functionality."""
    print("=== TESTING RESUME FUNCTIONALITY ===")
    
    try:
        config = load_config()
        crawler = WikiaCrawler("avatar_test", config)  # Use existing project
        
        print(f"[OK] Attempting to resume crawl for project 'avatar_test'")
        
        # Try to resume (this should call the resume_crawl method)
        stats = await crawler.resume_crawl()
        
        print(f"[OK] Resume completed")
        print(f"Stats: {stats}")
        
        return stats
        
    except Exception as e:
        print(f"[ERROR] Error during resume test: {e}")
        import traceback
        traceback.print_exc()
        return None


async def main():
    """Run resume test."""
    await test_resume()


if __name__ == "__main__":
    asyncio.run(main())