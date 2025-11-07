"""
Phase 1 CLI commands: Crawling wikia sites.
"""

from pathlib import Path
from typing import Optional
from .utils import load_crawler_config
from src.utils.logging_config import setup_logging, get_logger


async def crawl_command(project_name: str, wikia_url: str, max_pages: Optional[int] = None):
    """
    Start crawling a wikia site.

    Args:
        project_name: Name for this project
        wikia_url: Starting URL to crawl
        max_pages: Maximum pages to crawl (None = unlimited)
    """
    from crawler.core.crawler import WikiaCrawler

    # Setup logging
    setup_logging(project_name, log_level="INFO")
    logger = get_logger("main")

    logger.info(f"Starting crawl of {wikia_url} for project '{project_name}'")
    logger.info(f"Max pages: {max_pages or 'unlimited'}")
    logger.info("Loading configuration and initializing crawler...")

    config = load_crawler_config()

    # Use context manager for proper session cleanup
    async with WikiaCrawler(project_name, config) as crawler:
        start_urls = [wikia_url]
        logger.info(f"Starting crawl from: {wikia_url}")

        stats = await crawler.crawl_wikia(start_urls, max_pages=max_pages)

        logger.info("=" * 80)
        logger.info("CRAWL COMPLETED")
        logger.info("=" * 80)
        logger.info(f"Pages crawled: {stats['pages_crawled']}")
        logger.info(f"Errors: {stats['errors']}")
        logger.info(f"Duration: {stats['duration_seconds']:.2f}s")
        logger.info(f"URLs discovered: {stats['urls_in_queue']}")
        logger.info(f"Project saved to: {crawler.project_path}")

        # Show content summary
        content_files = list((crawler.project_path / "processed").rglob("*.json"))
        logger.info(f"Content files saved: {len(content_files)}")

        # Show by type
        by_type = {}
        for file in content_files:
            file_type = file.parent.name
            by_type[file_type] = by_type.get(file_type, 0) + 1

        for content_type, count in by_type.items():
            logger.info(f"  - {content_type}: {count}")

        logger.info(f"Next step: python main.py index {project_name}")

    logger.info("Crawler cleanup completed")


async def resume_command(project_name: str, max_pages: Optional[int] = None):
    """
    Resume an interrupted crawl.

    Args:
        project_name: Name of the project to resume
        max_pages: Additional maximum pages to crawl (None = unlimited)
    """
    from crawler.core.crawler import WikiaCrawler

    # Setup logging
    setup_logging(project_name, log_level="INFO")
    logger = get_logger("main")

    # Check that project exists
    project_path = Path(f"data/projects/{project_name}")
    if not project_path.exists():
        logger.error(f"Project '{project_name}' not found")
        logger.error(f"Use 'python main.py crawl {project_name} <url>' to start a new crawl")
        return

    # Check for saved state
    state_file = project_path / "cache" / "crawl_state.json"
    if not state_file.exists():
        logger.error(f"No saved crawl state found for project '{project_name}'")
        logger.error("Cannot resume - no previous crawl to continue")
        return

    logger.info(f"Resuming crawl for project '{project_name}'")
    logger.info(f"Max additional pages: {max_pages or 'unlimited'}")
    logger.info(f"Loading saved state from: {state_file}")

    config = load_crawler_config()

    # Use context manager for proper session cleanup
    async with WikiaCrawler(project_name, config) as crawler:
        # State is automatically loaded in __init__
        # Just continue crawling (empty start_urls uses queue from state)
        stats = await crawler.crawl_wikia([], max_pages=max_pages)

        logger.info("=" * 80)
        logger.info("CRAWL RESUMED AND COMPLETED")
        logger.info("=" * 80)
        logger.info(f"Pages crawled (this session): {stats['pages_crawled']}")
        logger.info(f"Errors: {stats['errors']}")
        logger.info(f"Duration: {stats['duration_seconds']:.2f}s")
        logger.info(f"URLs remaining: {stats['urls_in_queue']}")

        # Show total content
        content_files = list((crawler.project_path / "processed").rglob("*.json"))
        logger.info(f"Total content files: {len(content_files)}")

        logger.info(f"Next step: python main.py index {project_name}")

    print(f"[INFO] Crawler cleanup completed")
