#!/usr/bin/env python3
"""
CLI script to start crawling a wikia site.
"""

import argparse
import asyncio
import logging
from pathlib import Path
import sys
import yaml

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from crawler import WikiaCrawler


def setup_logging(verbose: bool = False):
    """Configure logging for console output."""
    level = logging.DEBUG if verbose else logging.INFO

    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )


def load_config(config_path: Path) -> dict:
    """Load crawler configuration from YAML file."""
    try:
        if not config_path.exists():
            print(f"[ERROR] Config file not found: {config_path}")
            sys.exit(1)

        with open(config_path, 'r') as f:
            yaml_data = yaml.safe_load(f)

        # Extract crawler config (handle nested structure)
        if 'crawler' in yaml_data:
            config = yaml_data['crawler']
        else:
            config = yaml_data

        # Validate required fields
        required = ['respect_robots_txt', 'user_agent',
                   'default_delay_seconds', 'max_requests_per_minute',
                   'target_namespaces']

        for field in required:
            if field not in config:
                raise ValueError(f"Missing required config field: {field}")

        return config

    except yaml.YAMLError as e:
        print(f"[ERROR] Invalid YAML in config file: {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"[ERROR] Configuration error: {e}")
        sys.exit(1)


def validate_start_urls(urls: list) -> list:
    """Validate and normalize starting URLs."""
    if not urls:
        raise ValueError("At least one starting URL is required")

    # Basic URL validation
    for url in urls:
        if not url.startswith(('http://', 'https://')):
            raise ValueError(f"Invalid URL (must start with http:// or https://): {url}")

    return urls


async def run_crawl(project_name: str, start_urls: list,
                   config: dict, max_pages: int = None):
    """Execute the crawl with progress reporting."""

    print("=" * 60)
    print(f"Starting crawl: {project_name}")
    print(f"URLs: {', '.join(start_urls)}")
    print(f"Max pages: {max_pages or 'unlimited'}")
    print(f"Rate limit: {config['default_delay_seconds']}s delay between requests")
    print("=" * 60)
    print()

    try:
        # Initialize crawler with context manager for proper cleanup
        async with WikiaCrawler(project_name, config) as crawler:
            # Start crawl
            stats = await crawler.crawl_wikia(start_urls, max_pages)

            # Display results
            print()
            print("=" * 60)
            print("CRAWL COMPLETE")
            print("=" * 60)
            print(f"Pages crawled: {stats['pages_crawled']}")
            print(f"Pages attempted: {stats['pages_attempted']}")
            print(f"Errors: {stats['errors']}")
            print(f"Duration: {stats['duration_seconds']:.2f}s")
            print(f"URLs remaining: {stats['urls_in_queue']}")
            print()
            print(f"Data saved to: data/projects/{project_name}/")
            print("=" * 60)

            return stats

    except KeyboardInterrupt:
        print("\n[INTERRUPTED] Crawl stopped by user")
        sys.exit(130)

    except Exception as e:
        print(f"\n[ERROR] Crawl failed: {e}")
        logging.exception("Detailed error:")
        sys.exit(1)


async def main():
    """Main crawl execution function."""
    parser = argparse.ArgumentParser(
        description="Crawl a Wikia site for character analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Crawl 5 pages from Avatar wiki
  python scripts/crawl_wikia.py avatar_test https://avatar.fandom.com/wiki/Aang --max-pages 5

  # Verbose output showing all DEBUG logs
  python scripts/crawl_wikia.py avatar_test https://avatar.fandom.com/wiki/Aang --max-pages 5 --verbose

  # Use custom config file
  python scripts/crawl_wikia.py my_project https://example.com/wiki/Main --config my_config.yaml
        """
    )

    parser.add_argument("project_name", help="Name for this crawl project")
    parser.add_argument("wikia_url", help="Starting URL to crawl")
    parser.add_argument("--max-pages", type=int, help="Maximum pages to crawl (default: unlimited)")
    parser.add_argument("--config", help="Path to config file",
                       default="config/crawler_config.yaml")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Enable verbose logging (DEBUG level)")
    parser.add_argument("--start-urls", nargs="+", help="Additional URLs to start crawling from")

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.verbose)

    # Load configuration
    config_path = Path(args.config)
    config = load_config(config_path)

    # Prepare start URLs
    start_urls = [args.wikia_url]
    if args.start_urls:
        start_urls.extend(args.start_urls)

    # Validate URLs
    try:
        start_urls = validate_start_urls(start_urls)
    except ValueError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

    # Run crawl
    await run_crawl(args.project_name, start_urls, config, args.max_pages)


if __name__ == "__main__":
    asyncio.run(main())
