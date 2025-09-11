#!/usr/bin/env python3
"""
Working main entry point for WikiaAnalyzer application.
"""

import argparse
import asyncio
import sys
from pathlib import Path
import yaml

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from crawler.core.crawler import WikiaCrawler


def load_config() -> dict:
    """Load crawler configuration."""
    config_path = Path("config/crawler_config.yaml")
    with open(config_path, 'r') as f:
        full_config = yaml.safe_load(f)
    
    return {
        'respect_robots_txt': full_config['crawler']['respect_robots_txt'],
        'user_agent': full_config['crawler']['user_agent'],
        'default_delay_seconds': full_config['crawler']['default_delay_seconds'],
        'max_requests_per_minute': full_config['crawler']['max_requests_per_minute'],
        'target_namespaces': full_config['crawler']['target_namespaces'],
        'timeout_seconds': full_config['crawler']['timeout_seconds'],
        'max_retries': full_config['crawler']['max_retries'],
        'exclude_patterns': full_config['crawler']['exclude_patterns'],
        'save_state_every_n_pages': full_config['crawler']['save_state_every_n_pages'],
    }


async def crawl_command(args):
    """Execute crawl command with proper session cleanup."""
    print(f"Starting crawl of {args.wikia_url} for project '{args.project_name}'")
    print(f"Max pages: {args.max_pages or 'unlimited'}")
    print(f"[INFO] Loading configuration and initializing crawler...")
    
    config = load_config()
    
    # Use context manager for proper session cleanup
    async with WikiaCrawler(args.project_name, config) as crawler:
        start_urls = [args.wikia_url]
        print(f"[INFO] Starting crawl from: {args.wikia_url}")
        
        stats = await crawler.crawl_wikia(start_urls, max_pages=args.max_pages)
        
        print(f"\n=== CRAWL COMPLETED ===")
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
    
    # Sessions are automatically cleaned up when context exits
    print(f"[INFO] Crawler cleanup completed")


def status_command(args):
    """Show project status."""
    project_path = Path(f"data/projects/{args.project_name}")
    if not project_path.exists():
        print(f"Project '{args.project_name}' not found")
        return
    
    # Count files by type
    content_files = list((project_path / "processed").rglob("*.json"))
    
    by_type = {}
    for file in content_files:
        file_type = file.parent.name
        by_type[file_type] = by_type.get(file_type, 0) + 1
    
    print(f"Project: {args.project_name}")
    print(f"Location: {project_path}")
    print(f"Total pages saved: {len(content_files)}")
    
    if by_type:
        print(f"Content by type:")
        for content_type, count in by_type.items():
            print(f"  - {content_type}: {count}")
    
    # Show some example files
    if content_files:
        print(f"\nExample files:")
        for file in content_files[:3]:
            print(f"  - {file.name}")


def list_command(args):
    """List all projects."""
    projects_dir = Path("data/projects")
    if not projects_dir.exists():
        print("No projects found")
        return
    
    projects = [d.name for d in projects_dir.iterdir() if d.is_dir()]
    if not projects:
        print("No projects found")
        return
        
    print("Available projects:")
    for project in projects:
        project_path = projects_dir / project
        content_files = list((project_path / "processed").rglob("*.json"))
        print(f"  - {project} ({len(content_files)} pages)")


def view_command(args):
    """View content from a project."""
    project_path = Path(f"data/projects/{args.project_name}")
    if not project_path.exists():
        print(f"Project '{args.project_name}' not found")
        return
    
    content_files = list((project_path / "processed").rglob("*.json"))
    if not content_files:
        print(f"No content found in project '{args.project_name}'")
        return
    
    import json
    
    # Show first file content
    with open(content_files[0], 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"Sample content from: {content_files[0].name}")
    print(f"URL: {data.get('url', 'Unknown')}")
    print(f"Title: {data.get('content', {}).get('title', 'Unknown')}")
    
    main_content = data.get('content', {}).get('main_content', '')
    if main_content:
        # Show first 500 characters
        preview = main_content[:500]
        if len(main_content) > 500:
            preview += "..."
        print(f"Content preview:\n{preview}")
    
    print(f"\nUse: cat \"{content_files[0]}\" | jq . to view full content")


async def main():
    """Main application entry point."""
    parser = argparse.ArgumentParser(description="WikiaAnalyzer - Extract character relationships")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Crawl command
    crawl_parser = subparsers.add_parser("crawl", help="Start crawling a wikia")
    crawl_parser.add_argument("project_name", help="Name for this project")
    crawl_parser.add_argument("wikia_url", help="Base URL of wikia to crawl")
    crawl_parser.add_argument("--max-pages", type=int, help="Maximum pages to crawl")
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Show project status")
    status_parser.add_argument("project_name", help="Project to check")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List all projects")
    
    # View command
    view_parser = subparsers.add_parser("view", help="View content from a project")
    view_parser.add_argument("project_name", help="Project to view")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    if args.command == "crawl":
        await crawl_command(args)
    elif args.command == "status":
        status_command(args)
    elif args.command == "list":
        list_command(args)
    elif args.command == "view":
        view_command(args)


if __name__ == "__main__":
    asyncio.run(main())