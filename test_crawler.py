#!/usr/bin/env python3
"""
Simple test script to manually test the crawler components.
This allows testing individual components without the full orchestrator.
"""

import asyncio
import sys
from pathlib import Path
import tempfile
import yaml

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from crawler.core.session_manager import SessionManager
from crawler.core.url_manager import URLManager
from crawler.extraction.page_extractor import PageExtractor
from crawler.extraction.link_discoverer import LinkDiscoverer
from crawler.extraction.wikia_parser import WikiaParser
from crawler.utils.content_filters import ContentFilter
from crawler.persistence.content_saver import ContentSaver
from crawler.rate_limiting.rate_limiter import RateLimiter


def load_config():
    """Load default configuration."""
    return {
        'user_agent': 'WikiaAnalyzer/1.0 (Educational Research)',
        'timeout_seconds': 30,
        'default_delay': 1.0,
        'requests_per_minute': 30,
        'max_pages': 5  # Limit for testing
    }


async def test_basic_crawling():
    """Test basic crawling functionality on a small scale."""
    print("*** Testing WikiaAnalyzer Components ***")
    print("=" * 50)
    
    config = load_config()
    
    # Create test project directory in current working directory
    project_path = Path.cwd() / "test_data"
    project_path.mkdir(exist_ok=True)
    
    print(f"Project directory: {project_path}")
    
    # Initialize components
    print("\nInitializing components...")
    session_manager = SessionManager(config['user_agent'], config['timeout_seconds'])
    url_manager = URLManager(project_path)
    page_extractor = PageExtractor()
    link_discoverer = LinkDiscoverer()
    wikia_parser = WikiaParser()
    content_filter = ContentFilter()
    content_saver = ContentSaver(project_path)
    rate_limiter = RateLimiter(config['default_delay'], config['requests_per_minute'])
    
    print("All components initialized successfully!")
    
    # Test URL - using a simple wiki page for testing
    test_url = input("\nEnter a wiki URL to test (or press Enter for example): ").strip()
    if not test_url:
        test_url = "https://naruto.fandom.com/wiki/Naruto_Uzumaki"
    
    print(f"\nTesting with URL: {test_url}")
    
    # Test URL management
    print("\nTesting URL Manager...")
    added = url_manager.add_url(test_url, priority=10)
    print(f"   URL added to queue: {added}")
    print(f"   Queue size: {url_manager.queue_size()}")
    
    next_url = url_manager.get_next_url()
    print(f"   Next URL from queue: {next_url}")
    
    if next_url:
        # Test HTTP session and page fetching
        print("\nTesting Session Manager...")
        try:
            await rate_limiter.wait_if_needed(test_url)
            
            async with session_manager:
                response = await session_manager.get(test_url)
                print(f"   Response status: {response.status}")
                
                if response.status == 200:
                    html_content = await response.text()
                    print(f"   Content length: {len(html_content)} characters")
                    
                    # Test content extraction
                    print("\nTesting Page Extractor...")
                    extracted_data = page_extractor.extract_content(html_content, test_url)
                    print(f"   Page title: {extracted_data.get('title', 'N/A')}")
                    print(f"   Page type: {extracted_data.get('page_type', 'N/A')}")
                    print(f"   Links found: {len(extracted_data.get('links', []))}")
                    print(f"   Categories: {len(extracted_data.get('categories', []))}")
                    
                    # Test Wikia-specific parsing
                    print("\nTesting Wikia Parser...")
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(html_content, 'html.parser')
                    wikia_data = wikia_parser.extract_wikia_content(soup, test_url)
                    print(f"   Namespace: {wikia_data.get('namespace', 'N/A')}")
                    print(f"   Is character page: {wikia_data.get('is_character_page', False)}")
                    print(f"   Is location page: {wikia_data.get('is_location_page', False)}")
                    print(f"   Character links: {len(wikia_data.get('character_links', set()))}")
                    print(f"   Infobox data: {len(wikia_data.get('infobox', {}))}")
                    
                    # Test link discovery
                    print("\nTesting Link Discoverer...")
                    discovered_links = link_discoverer.discover_links(soup, test_url)
                    print(f"   High priority links: {len(discovered_links.get('high_priority', set()))}")
                    print(f"   Medium priority links: {len(discovered_links.get('medium_priority', set()))}")
                    print(f"   Low priority links: {len(discovered_links.get('low_priority', set()))}")
                    
                    # Test content filtering
                    print("\nTesting Content Filter...")
                    cleaned_soup = content_filter.remove_wikia_chrome(soup)
                    main_content = content_filter.extract_main_content_area(cleaned_soup)
                    if main_content:
                        meaningful_text = content_filter.extract_meaningful_text(main_content)
                        print(f"   Meaningful text length: {len(meaningful_text) if meaningful_text else 0}")
                    
                    # Test content saving
                    print("\nTesting Content Saver...")
                    combined_data = {**extracted_data, **wikia_data}
                    
                    # Convert sets to lists for JSON serialization
                    def convert_sets_to_lists(obj):
                        if isinstance(obj, set):
                            return list(obj)
                        elif isinstance(obj, dict):
                            return {k: convert_sets_to_lists(v) for k, v in obj.items()}
                        elif isinstance(obj, list):
                            return [convert_sets_to_lists(item) for item in obj]
                        else:
                            return obj
                    
                    combined_data = convert_sets_to_lists(combined_data)
                    saved_path = content_saver.save_page_content(test_url, combined_data)
                    print(f"   Saved to: {saved_path.relative_to(project_path)}")
                    
                    # Test statistics
                    stats = content_saver.get_content_stats()
                    print(f"   Total pages saved: {stats.get('total_pages', 0)}")
                    print(f"   Total files: {stats.get('total_files', 0)}")
                    
                    # Mark URL as processed
                    url_manager.mark_visited(test_url)
                    print(f"   URL marked as visited. Visited count: {url_manager.visited_count()}")
                    
                    print("\nAll components working correctly!")
                    
                    # Show sample of discovered data
                    if extracted_data.get('title'):
                        print(f"\nSample Results:")
                        print(f"   Title: {extracted_data['title']}")
                        if extracted_data.get('categories'):
                            print(f"   Categories: {', '.join(extracted_data['categories'][:3])}...")
                        if wikia_data.get('infobox'):
                            print(f"   Infobox fields: {', '.join(list(wikia_data['infobox'].keys())[:3])}...")
                
                else:
                    print(f"   ERROR: Failed to fetch page: HTTP {response.status}")
                    
        except Exception as e:
            print(f"   ERROR: Error during crawling: {e}")
    
    else:
        print("   ERROR: No URL retrieved from queue")
    
    print(f"\nTest completed! Project files saved in: {project_path}")


def main():
    """Main entry point."""
    try:
        asyncio.run(test_basic_crawling())
    except KeyboardInterrupt:
        print("\n\nWARNING: Test interrupted by user")
    except Exception as e:
        print(f"\nERROR: Test failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()