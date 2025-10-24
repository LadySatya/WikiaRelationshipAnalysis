"""
PoC Script: Build Relationship Profiles

Extracts detailed relationships for discovered characters using RAG with citations.
"""
import sys
from pathlib import Path
import json
import time

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

from src.utils.logging_config import setup_project_logger
from src.processor.analysis.profile_builder import ProfileBuilder


def load_discovered_characters(project_name: str):
    """Load previously discovered characters."""
    char_dir = Path("data") / "projects" / project_name / "characters"

    if not char_dir.exists():
        return []

    characters = []
    for file in char_dir.glob("*.json"):
        with open(file, encoding="utf-8") as f:
            characters.append(json.load(f))

    return characters


def main():
    project_name = "avatar_poc"

    # Setup logging
    logger, log_file = setup_project_logger(project_name)

    logger.info("="*80)
    logger.info("AVATAR WIKI POC - PHASE 4: RELATIONSHIP EXTRACTION")
    logger.info("="*80)

    # Load discovered characters
    characters = load_discovered_characters(project_name)

    if not characters:
        logger.error("No characters found! Run poc_discover_characters.py first")
        return {}

    logger.info(f"Loaded {len(characters)} discovered characters")

    # Build profiles for top 5 characters (for PoC)
    sorted_chars = sorted(characters, key=lambda c: c.get('mentions', 0), reverse=True)
    top_chars = sorted_chars[:5]  # Start with top 5

    logger.info(f"\nBuilding profiles for top {len(top_chars)} characters:")
    for char in top_chars:
        logger.info(f"  - {char['full_name']}")

    # Initialize builder
    builder = ProfileBuilder(
        project_name=project_name,
        min_evidence_count=1,
        relationship_confidence_threshold=0.5  # Lower for PoC
    )

    # Build profiles
    logger.info("\nBuilding profiles (this may take 10-20 minutes)...")
    start_time = time.time()

    profiles = builder.build_all_profiles(top_chars, save=True)

    elapsed = time.time() - start_time

    # Analyze results
    total_relationships = sum(
        p["profile"]["total_relationships"]
        for p in profiles.values()
    )

    logger.info(f"\n{'='*80}")
    logger.info("RELATIONSHIP EXTRACTION COMPLETE - SUMMARY")
    logger.info(f"{'='*80}")
    logger.info(f"Characters profiled: {len(profiles)}")
    logger.info(f"Total relationships: {total_relationships}")
    logger.info(f"Avg relationships/character: {total_relationships/len(profiles):.1f}")
    logger.info(f"Time: {elapsed:.1f}s ({elapsed/len(profiles):.1f}s per character)")

    # Show sample relationship
    for char_name, profile in profiles.items():
        if profile["profile"]["relationships"]:
            rel = profile["profile"]["relationships"][0]
            logger.info(f"\nSample relationship: {char_name} -> {rel['target']}")
            logger.info(f"  Type: {rel['type']}")
            logger.info(f"  Summary: {rel['summary']}")
            logger.info(f"  Evidence: {rel['total_evidence_count']} citations")
            logger.info(f"  Confidence: {rel['overall_confidence']:.2f}")

            # Show first claim
            if rel['narrative']['claims_with_evidence']:
                claim = rel['narrative']['claims_with_evidence'][0]
                logger.info(f"\n  First claim: \"{claim['claim']}\"")
                logger.info(f"  Evidence: {len(claim['evidence'])} citations, confidence {claim['confidence']:.2f}")

                if claim['evidence']:
                    ev = claim['evidence'][0]
                    logger.info(f"    Source: {ev.get('page_title', 'Unknown')}")
                    logger.info(f"    Cited: \"{ev['cited_text'][:80]}...\"")
            break

    # LLM usage
    usage = builder.query_engine.get_usage_stats()
    logger.info(f"\nLLM Usage:")
    logger.info(f"  Input tokens:  {usage['total_input_tokens']:,}")
    logger.info(f"  Output tokens: {usage['total_output_tokens']:,}")
    logger.info(f"  Total cost:    ${usage['estimated_cost_usd']:.4f}")

    logger.info(f"\n{'='*80}")

    return {
        "characters_profiled": len(profiles),
        "total_relationships": total_relationships,
        "llm_cost": usage['estimated_cost_usd']
    }


if __name__ == "__main__":
    main()
