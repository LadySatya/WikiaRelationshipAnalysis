#!/usr/bin/env python3
"""
Integration test script for WikiaCrawler - validates end-to-end functionality.

Use this to test the crawler infrastructure and content extraction before
using the main CLI. Good for debugging and development validation.

For normal usage, use: python main.py crawl <project> <url> --max-pages <N>
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
    
    # Extract crawler section and flatten
    crawler_config = full_config['crawler']
    
    # Ensure all required keys are present with defaults
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


async def test_phase_1():
    """Phase 1: Dry run test with 5 pages."""
    print("=== PHASE 1: DRY RUN TEST (5 pages) ===")
    
    try:
        # Load configuration
        config = load_config()
        print(f"[OK] Configuration loaded")
        print(f"  - Rate limit: {config['default_delay_seconds']}s delay, {config['max_requests_per_minute']} req/min")
        print(f"  - User agent: {config['user_agent']}")
        
        # Initialize crawler with context manager
        async with WikiaCrawler("avatar_test", config) as crawler:
            print(f"[OK] Crawler initialized")
            print(f"  - Project path: {crawler.project_path}")
            
            # Check project structure was created
            if crawler.project_path.exists():
                dirs = [d.name for d in crawler.project_path.rglob("*") if d.is_dir()]
                print(f"[OK] Project structure created ({len(dirs)} directories)")
            
            # Start crawl
            start_urls = ["https://avatar.fandom.com/wiki/Avatar_Wiki"]
            print(f"[OK] Starting crawl with URLs: {start_urls}")
            
            stats = await crawler.crawl_wikia(start_urls, max_pages=5)
        
        print(f"\\n=== CRAWL COMPLETED ===")
        print(f"Pages attempted: {stats['pages_attempted']}")
        print(f"Pages crawled: {stats['pages_crawled']}")  
        print(f"Errors: {stats['errors']}")
        print(f"Duration: {stats['duration_seconds']:.2f}s")
        print(f"URLs in queue: {stats['urls_in_queue']}")
        
        return stats
        
    except Exception as e:
        print(f"[ERROR] Error during Phase 1: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_phase_2():
    """Phase 2: Extended test with 50 pages."""
    print("\\n=== PHASE 2: EXTENDED TEST (50 pages) ===")
    
    try:
        config = load_config()
        
        # Use context manager for proper session cleanup
        async with WikiaCrawler("avatar_extended", config) as crawler:
            # Try a category page that should have many links
            start_urls = ["https://avatar.fandom.com/wiki/Category:Characters"]
            print(f"Starting extended crawl with URLs: {start_urls}")
            
            stats = await crawler.crawl_wikia(start_urls, max_pages=50)
        
        print(f"\\n=== EXTENDED CRAWL COMPLETED ===")
        print(f"Pages attempted: {stats['pages_attempted']}")
        print(f"Pages crawled: {stats['pages_crawled']}")
        print(f"Errors: {stats['errors']}")
        print(f"Duration: {stats['duration_seconds']:.2f}s")
        print(f"URLs in queue: {stats['urls_in_queue']}")
        
        return stats
        
    except Exception as e:
        print(f"[ERROR] Error during Phase 2: {e}")
        import traceback
        traceback.print_exc()
        return None


async def main():
    """Run both test phases."""
    print("WikiaCrawler Live Test Suite")
    print("=" * 40)
    
    # Phase 1
    phase1_stats = await test_phase_1()
    
    # Only proceed to Phase 2 if Phase 1 succeeded
    if phase1_stats:
        await asyncio.sleep(2)  # Brief pause between phases
        phase2_stats = await test_phase_2()
    else:
        print("Skipping Phase 2 due to Phase 1 failure")


if __name__ == "__main__":
    asyncio.run(main())