"""
Phase 1 CLI commands: Crawling wikia sites.
"""

from pathlib import Path
from typing import Optional
from .utils import load_crawler_config


async def crawl_command(project_name: str, wikia_url: str, max_pages: Optional[int] = None):
    """
    Start crawling a wikia site.

    Args:
        project_name: Name for this project
        wikia_url: Starting URL to crawl
        max_pages: Maximum pages to crawl (None = unlimited)
    """
    from crawler.core.crawler import WikiaCrawler

    print(f"[INFO] Starting crawl of {wikia_url} for project '{project_name}'")
    print(f"[INFO] Max pages: {max_pages or 'unlimited'}")
    print(f"[INFO] Loading configuration and initializing crawler...")

    config = load_crawler_config()

    # Use context manager for proper session cleanup
    async with WikiaCrawler(project_name, config) as crawler:
        start_urls = [wikia_url]
        print(f"[INFO] Starting crawl from: {wikia_url}")

        stats = await crawler.crawl_wikia(start_urls, max_pages=max_pages)

        print(f"\n{'=' * 80}")
        print("CRAWL COMPLETED")
        print('=' * 80)
        print(f"Pages crawled: {stats['pages_crawled']}")
        print(f"Errors: {stats['errors']}")
        print(f"Duration: {stats['duration_seconds']:.2f}s")
        print(f"URLs discovered: {stats['urls_in_queue']}")
        print(f"Project saved to: {crawler.project_path}")

        # Show content summary
        content_files = list((crawler.project_path / "processed").rglob("*.json"))
        print(f"\nContent files saved: {len(content_files)}")

        # Show by type
        by_type = {}
        for file in content_files:
            file_type = file.parent.name
            by_type[file_type] = by_type.get(file_type, 0) + 1

        for content_type, count in by_type.items():
            print(f"  - {content_type}: {count}")

        print(f"\n[INFO] Next step: python main.py index {project_name}")

    print(f"[INFO] Crawler cleanup completed")


async def resume_command(project_name: str, max_pages: Optional[int] = None):
    """
    Resume an interrupted crawl.

    Args:
        project_name: Name of the project to resume
        max_pages: Additional maximum pages to crawl (None = unlimited)
    """
    from crawler.core.crawler import WikiaCrawler

    # Check that project exists
    project_path = Path(f"data/projects/{project_name}")
    if not project_path.exists():
        print(f"[ERROR] Project '{project_name}' not found")
        print(f"[ERROR] Use 'python main.py crawl {project_name} <url>' to start a new crawl")
        return

    # Check for saved state
    state_file = project_path / "cache" / "crawl_state.json"
    if not state_file.exists():
        print(f"[ERROR] No saved crawl state found for project '{project_name}'")
        print(f"[ERROR] Cannot resume - no previous crawl to continue")
        return

    print(f"[INFO] Resuming crawl for project '{project_name}'")
    print(f"[INFO] Max additional pages: {max_pages or 'unlimited'}")
    print(f"[INFO] Loading saved state from: {state_file}")

    config = load_crawler_config()

    # Use context manager for proper session cleanup
    async with WikiaCrawler(project_name, config) as crawler:
        # State is automatically loaded in __init__
        # Just continue crawling (empty start_urls uses queue from state)
        stats = await crawler.crawl_wikia([], max_pages=max_pages)

        print(f"\n{'=' * 80}")
        print("CRAWL RESUMED AND COMPLETED")
        print('=' * 80)
        print(f"Pages crawled (this session): {stats['pages_crawled']}")
        print(f"Errors: {stats['errors']}")
        print(f"Duration: {stats['duration_seconds']:.2f}s")
        print(f"URLs remaining: {stats['urls_in_queue']}")

        # Show total content
        content_files = list((crawler.project_path / "processed").rglob("*.json"))
        print(f"\nTotal content files: {len(content_files)}")

        print(f"\n[INFO] Next step: python main.py index {project_name}")

    print(f"[INFO] Crawler cleanup completed")
