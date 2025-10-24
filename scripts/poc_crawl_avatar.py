"""
PoC Script: Crawl Avatar Wiki

Crawls a targeted portion of the Avatar: The Last Airbender wiki
focused on main characters and their relationships.
"""
import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.logging_config import setup_project_logger
from src.crawler.core.crawler import WikiaCrawler
import yaml


def load_config():
    """Load crawler configuration."""
    config_path = Path(__file__).parent.parent / "config" / "crawler_config.yaml"

    with open(config_path) as f:
        config = yaml.safe_load(f)

    return config["crawler"]


async def main():
    project_name = "avatar_poc"

    # Setup logging
    logger, log_file = setup_project_logger(project_name)

    logger.info("="*80)
    logger.info("AVATAR WIKI POC - PHASE 1: CRAWLING")
    logger.info("="*80)
    logger.info(f"Log file: {log_file}")

    # Load config
    config = load_config()

    # Start URL - Aang's page (will follow links to other characters)
    start_url = "https://avatar.fandom.com/wiki/Aang"

    logger.info(f"Starting URL: {start_url}")
    logger.info(f"Target: 100 pages")

    # Initialize crawler
    crawler = WikiaCrawler(
        project_name=project_name,
        config=config
    )

    # Crawl
    stats = await crawler.crawl_wikia(
        start_urls=[start_url],
        max_pages=100
    )

    # Report
    logger.info("\n" + "="*80)
    logger.info("CRAWL COMPLETE - SUMMARY")
    logger.info("="*80)
    logger.info(f"Pages crawled: {stats['pages_crawled']}")
    logger.info(f"Pages attempted: {stats['pages_attempted']}")
    logger.info(f"Errors: {stats['errors']}")
    logger.info(f"Duration: {stats['duration_seconds']:.1f}s")
    logger.info(f"URLs in queue: {stats['urls_in_queue']}")

    # Cleanup
    await crawler.cleanup()

    return stats


if __name__ == "__main__":
    asyncio.run(main())
