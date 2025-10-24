#!/usr/bin/env python3
"""
Main entry point for WikiaAnalyzer application.

This CLI provides a unified interface for all phases of the character
relationship extraction pipeline:

Phase 1 - Crawling:
  crawl    Start crawling a wikia site
  resume   Resume an interrupted crawl

Phase 2 - Processing:
  index    Build vector database from crawled pages
  discover Discover characters from indexed data
  build    Build relationship profiles for characters

Phase 3 - Validation:
  validate Show results and statistics

Pipeline:
  pipeline Run full pipeline (crawl -> index -> discover -> build -> validate)

Meta:
  status   Show project status
  list     List all projects
  view     View sample content from a project
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from cli import (
    crawl_command,
    resume_command,
    index_command,
    discover_command,
    build_command,
    validate_command,
    pipeline_command,
)


def status_command(args):
    """Show project status."""
    project_path = Path(f"data/projects/{args.project_name}")
    if not project_path.exists():
        print(f"[ERROR] Project '{args.project_name}' not found")
        print(f"[INFO] Use 'python main.py list' to see available projects")
        return

    # Count files by directory
    processed_dir = project_path / "processed"
    characters_dir = project_path / "characters"
    relationships_dir = project_path / "relationships"

    processed_files = list(processed_dir.glob("*.json")) if processed_dir.exists() else []
    character_files = list(characters_dir.glob("*.json")) if characters_dir.exists() else []
    graph_file = relationships_dir / "graph.json" if relationships_dir.exists() else None

    print(f"\n{'=' * 80}")
    print(f"Project: {args.project_name}")
    print('=' * 80)
    print(f"Location: {project_path}")
    print("")

    # Phase 1 status
    print("[Phase 1 - Crawling]")
    if processed_files:
        print(f"  Status: Complete")
        print(f"  Pages crawled: {len(processed_files)}")
    else:
        print(f"  Status: Not started")
        print(f"  Next: python main.py crawl {args.project_name} <url>")
    print("")

    # Phase 2a status (indexing)
    print("[Phase 2a - Indexing]")
    chroma_dir = project_path / "vector_store"
    if chroma_dir.exists():
        print(f"  Status: Complete")
        print(f"  Vector store: {chroma_dir}")
    else:
        print(f"  Status: Not started")
        if processed_files:
            print(f"  Next: python main.py index {args.project_name}")
    print("")

    # Phase 2b status (discovery + profiles)
    print("[Phase 2b - Character Discovery & Profiles]")
    if character_files:
        print(f"  Status: Discovery complete")
        print(f"  Characters discovered: {len(character_files)}")

        if graph_file and graph_file.exists():
            import json
            with open(graph_file, 'r') as f:
                graph = json.load(f)
            print(f"  Relationships extracted: {graph['metadata']['total_relationships']}")
            print(f"  Status: Profiles complete")
        else:
            print(f"  Status: Profiles not started")
            print(f"  Next: python main.py build {args.project_name}")
    else:
        print(f"  Status: Not started")
        if chroma_dir.exists():
            print(f"  Next: python main.py discover {args.project_name}")
    print("")

    # Phase 3 status
    print("[Phase 3 - Validation]")
    if graph_file and graph_file.exists():
        print(f"  Status: Ready for validation")
        print(f"  Next: python main.py validate {args.project_name}")
    else:
        print(f"  Status: Not ready")
    print("")

    print('=' * 80)


def list_command(args):
    """List all projects."""
    projects_dir = Path("data/projects")
    if not projects_dir.exists():
        print("No projects found")
        print(f"\nCreate a project: python main.py crawl <project_name> <url>")
        return

    projects = [d for d in projects_dir.iterdir() if d.is_dir()]
    if not projects:
        print("No projects found")
        print(f"\nCreate a project: python main.py crawl <project_name> <url>")
        return

    print(f"\n{'=' * 80}")
    print("Available Projects")
    print('=' * 80)
    print("")

    for project_dir in sorted(projects):
        project_name = project_dir.name
        processed_dir = project_dir / "processed"
        characters_dir = project_dir / "characters"

        processed_files = list(processed_dir.glob("*.json")) if processed_dir.exists() else []
        character_files = list(characters_dir.glob("*.json")) if characters_dir.exists() else []

        status = "empty"
        if character_files:
            status = f"{len(character_files)} characters"
        elif processed_files:
            status = f"{len(processed_files)} pages"

        print(f"  {project_name:30s} ({status})")

    print("")
    print('=' * 80)
    print(f"\nView details: python main.py status <project_name>")


def view_command(args):
    """View sample content from a project."""
    project_path = Path(f"data/projects/{args.project_name}")
    if not project_path.exists():
        print(f"[ERROR] Project '{args.project_name}' not found")
        return

    processed_dir = project_path / "processed"
    content_files = list(processed_dir.glob("*.json")) if processed_dir.exists() else []

    if not content_files:
        print(f"No content found in project '{args.project_name}'")
        print(f"Run: python main.py crawl {args.project_name} <url>")
        return

    import json

    # Show first file content
    with open(content_files[0], 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"\n{'=' * 80}")
    print(f"Sample content from: {content_files[0].name}")
    print('=' * 80)

    content = data.get('content', data)
    print(f"URL: {content.get('url', 'Unknown')}")
    print(f"Title: {content.get('title', 'Unknown')}")

    main_content = content.get('main_content', '')
    if main_content:
        # Show first 500 characters
        preview = main_content[:500]
        if len(main_content) > 500:
            preview += "..."
        print(f"\nContent preview:\n{preview}")

    print(f"\n{'=' * 80}")
    print(f"Total files: {len(content_files)}")


async def main():
    """Main application entry point."""
    parser = argparse.ArgumentParser(
        description="WikiaAnalyzer - Extract character relationships from wikia sites",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full pipeline
  python main.py pipeline avatar_wiki https://avatar.fandom.com/wiki/Aang --max-pages 100

  # Step by step
  python main.py crawl avatar_wiki https://avatar.fandom.com/wiki/Aang --max-pages 100
  python main.py index avatar_wiki
  python main.py discover avatar_wiki
  python main.py build avatar_wiki --max-characters 10
  python main.py validate avatar_wiki

  # Project management
  python main.py list
  python main.py status avatar_wiki
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ========== Phase 1: Crawling ==========

    # crawl command
    crawl_parser = subparsers.add_parser("crawl", help="Start crawling a wikia")
    crawl_parser.add_argument("project_name", help="Name for this project")
    crawl_parser.add_argument("wikia_url", help="Starting URL to crawl")
    crawl_parser.add_argument("--max-pages", type=int, help="Maximum pages to crawl")

    # resume command
    resume_parser = subparsers.add_parser("resume", help="Resume interrupted crawl")
    resume_parser.add_argument("project_name", help="Project to resume")
    resume_parser.add_argument("--max-pages", type=int, help="Additional pages to crawl")

    # ========== Phase 2: Processing ==========

    # index command
    index_parser = subparsers.add_parser("index", help="Build vector database index")
    index_parser.add_argument("project_name", help="Project to index")

    # discover command
    discover_parser = subparsers.add_parser("discover", help="Discover characters")
    discover_parser.add_argument("project_name", help="Project to analyze")
    discover_parser.add_argument("--min-mentions", type=int, default=3,
                                 help="Minimum mentions required (default: 3)")
    discover_parser.add_argument("--confidence", type=float, default=0.7,
                                 help="Minimum confidence threshold (default: 0.7)")

    # build command
    build_parser = subparsers.add_parser("build", help="Build relationship profiles")
    build_parser.add_argument("project_name", help="Project to build profiles for")
    build_parser.add_argument("--max-characters", type=int, default=5,
                              help="Maximum characters to profile (default: 5)")

    # ========== Phase 3: Validation ==========

    # validate command
    validate_parser = subparsers.add_parser("validate", help="Validate and show results")
    validate_parser.add_argument("project_name", help="Project to validate")

    # ========== Pipeline ==========

    # pipeline command
    pipeline_parser = subparsers.add_parser("pipeline", help="Run full pipeline")
    pipeline_parser.add_argument("project_name", help="Name for this project")
    pipeline_parser.add_argument("wikia_url", nargs="?", help="Starting URL (required unless --skip-crawl)")
    pipeline_parser.add_argument("--max-pages", type=int, help="Maximum pages to crawl")
    pipeline_parser.add_argument("--max-characters", type=int, default=5,
                                 help="Maximum characters to profile (default: 5)")
    pipeline_parser.add_argument("--skip-crawl", action="store_true",
                                 help="Skip crawling (use existing data)")

    # ========== Meta Commands ==========

    # status command
    status_parser = subparsers.add_parser("status", help="Show project status")
    status_parser.add_argument("project_name", help="Project to check")

    # list command
    list_parser = subparsers.add_parser("list", help="List all projects")

    # view command
    view_parser = subparsers.add_parser("view", help="View sample content")
    view_parser.add_argument("project_name", help="Project to view")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Route to appropriate command handler
    try:
        if args.command == "crawl":
            await crawl_command(args.project_name, args.wikia_url, args.max_pages)
        elif args.command == "resume":
            await resume_command(args.project_name, args.max_pages)
        elif args.command == "index":
            index_command(args.project_name)
        elif args.command == "discover":
            discover_command(args.project_name, args.min_mentions, args.confidence)
        elif args.command == "build":
            build_command(args.project_name, args.max_characters)
        elif args.command == "validate":
            validate_command(args.project_name)
        elif args.command == "pipeline":
            await pipeline_command(
                args.project_name,
                args.wikia_url,
                args.max_pages,
                args.max_characters,
                args.skip_crawl
            )
        elif args.command == "status":
            status_command(args)
        elif args.command == "list":
            list_command(args)
        elif args.command == "view":
            view_command(args)
    except KeyboardInterrupt:
        print("\n[INFO] Operation cancelled by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
