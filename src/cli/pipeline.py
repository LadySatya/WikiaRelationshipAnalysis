"""
Pipeline and validation commands.
"""

from pathlib import Path
from typing import Optional

from src.utils.logging_config import get_logger, setup_logging

from .utils import setup_project_logging, validate_project_exists


def validate_command(project_name: str):
    """
    Check a project's knowledge base for grounding and consistency problems.

    Re-verifies every evidence quote against the crawled pages and reports
    relationships without claims, self-relationships, unknown characters,
    likely duplicate characters, and partly read or unprocessed pages.

    Args:
        project_name: Name of the project to validate
    """
    from src.processor.analysis.kb_validation import validate_knowledge_base

    project_path = validate_project_exists(project_name, require_crawled=False)
    logger = setup_project_logging(project_name, "VALIDATION")

    report = validate_knowledge_base(project_path)

    logger.info("")
    logger.info(f"Characters:      {report['characters']}")
    logger.info(f"Relationships:   {report['relationships']}")
    logger.info(f"Claims:          {report['claims']}")
    logger.info(f"Evidence quotes: {report['evidence']}")
    logger.info(
        f"Characters without relationships: {report['characters_without_relationships']}"
    )
    types = ", ".join(
        f"{t}={n}"
        for t, n in sorted(report["relationship_types"].items(), key=lambda x: -x[1])
    )
    logger.info(f"Relationship types: {types or '(none)'}")
    logger.info("")

    if not report["issues"]:
        logger.info("[OK] No issues found")
        return

    for name, found in report["issues"].items():
        logger.warning(f"[ISSUE] {name.replace('_', ' ')}: {len(found)}")
        for item in found[:5]:
            logger.warning(f"    {item}")
        if len(found) > 5:
            logger.warning(f"    ... and {len(found) - 5} more")


async def pipeline_command(
    project_name: str,
    wikia_url: Optional[str] = None,
    max_pages: Optional[int] = None,
    max_characters: int = 5,
    skip_crawl: bool = False,
):
    """
    Run the full pipeline from crawl to validation.

    Args:
        project_name: Name of the project
        wikia_url: Starting URL (required unless skip_crawl=True)
        max_pages: Maximum pages to crawl (for both crawling and knowledge building)
        max_characters: DEPRECATED (ignored, kept for backwards compatibility)
        skip_crawl: Skip crawling phase (use existing data)
    """
    from .crawl_commands import crawl_command
    from .processor_commands import discover_command, index_command

    # Setup logging
    setup_logging(project_name, log_level="INFO")
    logger = get_logger("main")

    logger.info("=" * 80)
    logger.info(f"FULL PIPELINE: {project_name}")
    logger.info("=" * 80)
    logger.info("")

    # Phase 1: Crawl (optional)
    if not skip_crawl:
        if not wikia_url:
            logger.error("wikia_url required when not skipping crawl")
            return

        logger.info("[PHASE 1] Crawling...")
        await crawl_command(project_name, wikia_url, max_pages)
        logger.info("")
    else:
        logger.info("[PHASE 1] Skipped (using existing crawled data)")
        logger.info("")

    # Phase 2a: Index
    logger.info("[PHASE 2a] Indexing...")
    index_command(project_name)
    logger.info("")

    # Phase 2b: Build Knowledge Base (unified discovery + relationship extraction)
    logger.info("[PHASE 2b] Building knowledge base (characters + relationships)...")
    discover_command(project_name, max_pages=max_pages)
    logger.info("")

    # Phase 3: Validate
    logger.info("[PHASE 3] Validating results...")
    validate_command(project_name)
    logger.info("")

    logger.info("=" * 80)
    logger.info("FULL PIPELINE COMPLETE")
    logger.info("=" * 80)
    logger.info("")
    logger.info(f"Results saved to: data/projects/{project_name}/")
    logger.info(f"  - Characters: data/projects/{project_name}/characters/")
    logger.info(f"  - Relationships: data/projects/{project_name}/relationships/")
    logger.info(f"  - Logs: data/projects/{project_name}/logs/")
