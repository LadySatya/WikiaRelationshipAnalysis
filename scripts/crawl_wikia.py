#!/usr/bin/env python3
"""
CLI script to start crawling a wikia site.
"""

import argparse
import asyncio
from pathlib import Path
import sys
import yaml

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from crawler import WikiaCrawler


def load_config(config_path: Path) -> dict:
    """Load crawler configuration from YAML file."""
    pass


def validate_start_urls(urls: list) -> list:
    """Validate and normalize starting URLs."""
    pass


def setup_project(project_name: str, wikia_url: str) -> Path:
    """Set up project directory structure."""
    pass


async def main():
    """Main crawl execution function."""
    parser = argparse.ArgumentParser(description="Crawl a Wikia site for character analysis")
    parser.add_argument("project_name", help="Name for this crawl project")
    parser.add_argument("wikia_url", help="Base URL of the wikia to crawl")
    parser.add_argument("--max-pages", type=int, help="Maximum pages to crawl")
    parser.add_argument("--config", help="Path to config file", default="config/crawler_config.yaml")
    parser.add_argument("--start-urls", nargs="+", help="Specific URLs to start crawling from")
    
    args = parser.parse_args()
    
    # Implementation stub
    print(f"Starting crawl of {args.wikia_url} for project '{args.project_name}'")
    print(f"Max pages: {args.max_pages or 'unlimited'}")


if __name__ == "__main__":
    asyncio.run(main())