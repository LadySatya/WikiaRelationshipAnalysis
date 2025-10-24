"""
Pipeline and validation commands.
"""

from pathlib import Path
from typing import Optional
from .utils import validate_project_exists, setup_project_logging


def validate_command(project_name: str):
    """
    Validate and show statistics for a completed pipeline.

    Args:
        project_name: Name of the project to validate
    """
    import json

    # Validate project exists
    project_path = validate_project_exists(project_name, require_crawled=False)

    # Setup logging
    logger = setup_project_logging(project_name, "PHASE 5: VALIDATION")

    # Load relationship graph
    graph_path = project_path / "relationships" / "graph.json"
    if not graph_path.exists():
        logger.error("No relationship graph found")
        logger.error(f"Run 'python main.py build {project_name}' first")
        return

    with open(graph_path, 'r', encoding='utf-8') as f:
        graph = json.load(f)

    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    metadata = graph.get("metadata", {})

    logger.info("")
    logger.info("Graph Statistics:")
    logger.info(f"  Nodes (characters): {len(nodes)}")
    logger.info(f"  Edges (relationships): {len(edges)}")
    if nodes:
        avg_connections = len(edges) / len(nodes)
        logger.info(f"  Avg connections: {avg_connections:.1f}")

    # Confidence distribution
    if edges:
        logger.info("")
        logger.info("Confidence Distribution:")

        high_conf = sum(1 for e in edges if e.get("confidence", 0) >= 0.8)
        med_conf = sum(1 for e in edges if 0.5 <= e.get("confidence", 0) < 0.8)
        low_conf = sum(1 for e in edges if e.get("confidence", 0) < 0.5)

        logger.info(f"  High (>=0.8):    {high_conf:3d} ({high_conf/len(edges)*100:5.1f}%)")
        logger.info(f"  Medium (0.5-0.8):   {med_conf:3d} ({med_conf/len(edges)*100:5.1f}%)")
        logger.info(f"  Low (<0.5):        {low_conf:3d} ({low_conf/len(edges)*100:5.1f}%)")

    # Evidence statistics
    if edges:
        evidence_counts = [e.get("evidence_count", 0) for e in edges]
        avg_evidence = sum(evidence_counts) / len(evidence_counts)
        min_evidence = min(evidence_counts)
        max_evidence = max(evidence_counts)

        logger.info("")
        logger.info("Evidence Statistics:")
        logger.info(f"  Avg citations/relationship: {avg_evidence:.1f}")
        logger.info(f"  Min: {min_evidence}")
        logger.info(f"  Max: {max_evidence}")

    # Show top relationships
    high_conf_edges = sorted(
        [e for e in edges if e.get("confidence", 0) >= 0.8],
        key=lambda e: e.get("confidence", 0),
        reverse=True
    )[:3]

    if high_conf_edges:
        logger.info("")
        logger.info("Top High-Confidence Relationships:")
        logger.info("")

        for i, edge in enumerate(high_conf_edges, 1):
            logger.info(f"{i}. {edge['from']} -> {edge['to']}")
            logger.info(f"   Type: {edge['type']}")
            logger.info(f"   Summary: {edge['summary'][:100]}...")
            logger.info(f"   Confidence: {edge.get('confidence', 0.0):.2f}")
            logger.info(f"   Evidence: {edge.get('evidence_count', 0)} citations")
            logger.info("")

    # Show detailed profile sample
    characters_dir = project_path / "characters"
    if characters_dir.exists() and nodes:
        # Load first character's full profile
        first_node = nodes[0]
        char_file = characters_dir / f"{first_node['id'].replace(' ', '_')}.json"

        if char_file.exists():
            with open(char_file, 'r', encoding='utf-8') as f:
                profile = json.load(f)

            logger.info("=" * 80)
            logger.info(f"Detailed Profile Sample: {first_node['id']}")
            logger.info("=" * 80)

            if profile.get("profile", {}).get("relationships"):
                # Show first relationship in detail
                rel = profile["profile"]["relationships"][0]
                logger.info("")
                logger.info(f"Relationship: {first_node['id']} -> {rel['target']}")
                logger.info(f"Type: {rel['type']}")

                claims = rel.get("narrative", {}).get("claims_with_evidence", [])
                if claims:
                    logger.info("")
                    logger.info(f"Claims ({len(claims)} total):")
                    logger.info("")

                    # Show first 3 claims
                    for i, claim in enumerate(claims[:3], 1):
                        logger.info(f"  {i}. \"{claim['claim']}\"")
                        logger.info(f"     Confidence: {claim.get('confidence', 0.0):.2f}, Evidence: {len(claim.get('evidence', []))} citations")
                        if claim.get('evidence'):
                            evidence = claim['evidence'][0]
                            cited_preview = evidence['cited_text'][:80] + "..." if len(evidence['cited_text']) > 80 else evidence['cited_text']
                            logger.info(f"     Source: {evidence.get('title', 'Unknown')}")
                            logger.info(f"     Cited: {cited_preview}")
                        logger.info("")

    logger.info("=" * 80)
    logger.info("VALIDATION COMPLETE")
    logger.info("=" * 80)
    logger.info("")


async def pipeline_command(
    project_name: str,
    wikia_url: Optional[str] = None,
    max_pages: Optional[int] = None,
    max_characters: int = 5,
    skip_crawl: bool = False
):
    """
    Run the full pipeline from crawl to validation.

    Args:
        project_name: Name of the project
        wikia_url: Starting URL (required unless skip_crawl=True)
        max_pages: Maximum pages to crawl
        max_characters: Maximum characters to profile (default: 5)
        skip_crawl: Skip crawling phase (use existing data)
    """
    from .crawl_commands import crawl_command
    from .processor_commands import index_command, discover_command, build_command

    print("=" * 80)
    print(f"FULL PIPELINE: {project_name}")
    print("=" * 80)
    print("")

    # Phase 1: Crawl (optional)
    if not skip_crawl:
        if not wikia_url:
            print("[ERROR] wikia_url required when not skipping crawl")
            return

        print("[PHASE 1] Crawling...")
        await crawl_command(project_name, wikia_url, max_pages)
        print("")
    else:
        print("[PHASE 1] Skipped (using existing crawled data)")
        print("")

    # Phase 2a: Index
    print("[PHASE 2a] Indexing...")
    index_command(project_name)
    print("")

    # Phase 2b: Discover
    print("[PHASE 2b] Discovering characters...")
    discover_command(project_name, min_mentions=3, confidence_threshold=0.7)
    print("")

    # Phase 2c: Build profiles
    print("[PHASE 2c] Building relationship profiles...")
    build_command(project_name, max_characters=max_characters)
    print("")

    # Phase 3: Validate
    print("[PHASE 3] Validating results...")
    validate_command(project_name)
    print("")

    print("=" * 80)
    print("FULL PIPELINE COMPLETE")
    print("=" * 80)
    print("")
    print(f"Results saved to: data/projects/{project_name}/")
    print(f"  - Characters: data/projects/{project_name}/characters/")
    print(f"  - Relationships: data/projects/{project_name}/relationships/graph.json")
    print(f"  - Logs: data/projects/{project_name}/logs/")
