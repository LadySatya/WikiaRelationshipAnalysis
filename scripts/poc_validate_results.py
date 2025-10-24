"""
PoC Script: Validate Results

Analyzes the relationship graph and validates output quality.
"""
import sys
from pathlib import Path
import json

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.logging_config import setup_project_logger


def main():
    project_name = "avatar_poc"

    # Setup logging
    logger, log_file = setup_project_logger(project_name)

    logger.info("="*80)
    logger.info("AVATAR WIKI POC - PHASE 5: VALIDATION")
    logger.info("="*80)

    # Load relationship graph
    graph_file = Path("data") / "projects" / project_name / "relationships" / "graph.json"

    if not graph_file.exists():
        logger.error(f"Graph file not found: {graph_file}")
        logger.error("Run poc_build_relationships.py first!")
        return

    with open(graph_file, encoding="utf-8") as f:
        graph = json.load(f)

    # Analyze graph
    nodes = graph["nodes"]
    edges = graph["edges"]
    metadata = graph["metadata"]

    logger.info(f"\nGraph Statistics:")
    logger.info(f"  Nodes (characters): {len(nodes)}")
    logger.info(f"  Edges (relationships): {len(edges)}")
    logger.info(f"  Avg connections: {len(edges)/len(nodes):.1f}")

    # Confidence distribution
    confidences = [e["confidence"] for e in edges]
    high_conf = len([c for c in confidences if c >= 0.8])
    med_conf = len([c for c in confidences if 0.5 <= c < 0.8])
    low_conf = len([c for c in confidences if c < 0.5])

    logger.info(f"\nConfidence Distribution:")
    logger.info(f"  High (>=0.8):    {high_conf:3d} ({high_conf/len(edges)*100:5.1f}%)")
    logger.info(f"  Medium (0.5-0.8): {med_conf:3d} ({med_conf/len(edges)*100:5.1f}%)")
    logger.info(f"  Low (<0.5):      {low_conf:3d} ({low_conf/len(edges)*100:5.1f}%)")

    # Evidence distribution
    evidence_counts = [e["evidence_count"] for e in edges]
    avg_evidence = sum(evidence_counts) / len(evidence_counts)

    logger.info(f"\nEvidence Statistics:")
    logger.info(f"  Avg citations/relationship: {avg_evidence:.1f}")
    logger.info(f"  Min: {min(evidence_counts)}")
    logger.info(f"  Max: {max(evidence_counts)}")

    # Show top 3 high-confidence relationships
    logger.info(f"\nTop High-Confidence Relationships:")

    sorted_edges = sorted(edges, key=lambda e: e["confidence"], reverse=True)

    for i, edge in enumerate(sorted_edges[:3], 1):
        logger.info(f"\n{i}. {edge['from']} -> {edge['to']}")
        logger.info(f"   Type: {edge['type']}")
        logger.info(f"   Summary: {edge['summary']}")
        logger.info(f"   Confidence: {edge['confidence']:.2f}")
        logger.info(f"   Evidence: {edge['evidence_count']} citations")

    # Load one full profile for detailed inspection
    char_file = Path("data") / "projects" / project_name / "characters" / f"{nodes[0]['full_name']}.json"

    if char_file.exists():
        with open(char_file, encoding="utf-8") as f:
            profile = json.load(f)

        logger.info(f"\n{'='*80}")
        logger.info(f"Detailed Profile Sample: {profile['full_name']}")
        logger.info(f"{'='*80}")

        if profile["profile"]["relationships"]:
            rel = profile["profile"]["relationships"][0]
            claims = rel["narrative"]["claims_with_evidence"]

            logger.info(f"\nRelationship: {profile['name']} -> {rel['target']}")
            logger.info(f"Type: {rel['type']}")
            logger.info(f"\nClaims ({len(claims)} total):")

            for i, claim in enumerate(claims[:3], 1):
                logger.info(f"\n  {i}. \"{claim['claim']}\"")
                logger.info(f"     Confidence: {claim['confidence']:.2f}, Evidence: {len(claim['evidence'])} citations")

                for ev in claim['evidence'][:1]:  # Show first citation
                    logger.info(f"     Source: {ev.get('page_title', 'Unknown')}")
                    logger.info(f"     Cited: \"{ev['cited_text'][:80]}...\"")

    logger.info(f"\n{'='*80}")
    logger.info("VALIDATION COMPLETE")
    logger.info(f"{'='*80}")


if __name__ == "__main__":
    main()
