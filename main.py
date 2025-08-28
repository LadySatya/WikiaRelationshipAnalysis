#!/usr/bin/env python3
"""
Main entry point for WikiaAnalyzer application.
"""

import argparse
import sys
from pathlib import Path


def main():
    """Main application entry point."""
    parser = argparse.ArgumentParser(
        description="WikiaAnalyzer - Character relationship analysis for wikia sites",
        epilog="Use 'python main.py <command> --help' for command-specific help"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Crawl command
    crawl_parser = subparsers.add_parser("crawl", help="Start crawling a wikia")
    crawl_parser.add_argument("project_name", help="Name for this project")
    crawl_parser.add_argument("wikia_url", help="Base URL of wikia to crawl")
    crawl_parser.add_argument("--max-pages", type=int, help="Maximum pages to crawl")
    
    # Resume command
    resume_parser = subparsers.add_parser("resume", help="Resume interrupted crawl")
    resume_parser.add_argument("project_name", help="Project to resume")
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Show project status")
    status_parser.add_argument("project_name", help="Project to check")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List all projects")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Route to appropriate handler
    if args.command == "crawl":
        print(f"Would start crawling {args.wikia_url} for project '{args.project_name}'")
    elif args.command == "resume":
        print(f"Would resume project '{args.project_name}'")
    elif args.command == "status":
        print(f"Would show status for project '{args.project_name}'")
    elif args.command == "list":
        print("Would list all projects")


if __name__ == "__main__":
    main()