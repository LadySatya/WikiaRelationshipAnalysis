#!/usr/bin/env python3
"""
CLI script to resume an interrupted crawl.
"""

import argparse
import asyncio
from pathlib import Path
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from crawler import WikiaCrawler


def list_resumable_projects() -> list:
    """List projects that have saved crawl state."""
    pass


def validate_project_exists(project_name: str) -> Path:
    """Validate that project exists and has saved state."""
    pass


def show_project_status(project_name: str) -> dict:
    """Show current status of project crawl."""
    pass


async def main():
    """Main resume execution function."""
    parser = argparse.ArgumentParser(description="Resume an interrupted wikia crawl")
    parser.add_argument("project_name", help="Name of project to resume")
    parser.add_argument("--list", action="store_true", help="List resumable projects")
    parser.add_argument("--status", action="store_true", help="Show project status only")
    parser.add_argument("--max-pages", type=int, help="Additional pages to crawl")
    
    args = parser.parse_args()
    
    if args.list:
        # Implementation stub
        print("Resumable projects:")
        return
    
    if args.status:
        # Implementation stub
        print(f"Status for project '{args.project_name}':")
        return
    
    # Implementation stub
    print(f"Resuming crawl for project '{args.project_name}'")


if __name__ == "__main__":
    asyncio.run(main())