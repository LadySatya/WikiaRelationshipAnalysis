"""
PoC Script: Discover Characters

Discovers characters from indexed wiki content using page-based classification.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

from src.utils.logging_config import setup_project_logger
from src.processor.analysis.character_extractor import CharacterExtractor


def main():
    project_name = "avatar_poc"

    # Setup logging
    logger, log_file = setup_project_logger(project_name)

    logger.info("="*80)
    logger.info("AVATAR WIKI POC - PHASE 3: CHARACTER DISCOVERY")
    logger.info("="*80)

    # Initialize extractor
    extractor = CharacterExtractor(
        project_name=project_name,
        min_mentions=2,  # Lower threshold for PoC
        confidence_threshold=0.6
    )

    # Discover characters
    logger.info("Starting character discovery...")
    characters = extractor.discover_characters(save=True)

    logger.info(f"\nDiscovered {len(characters)} characters")

    # Show top 15 by mentions
    logger.info("\nTop characters by mentions:")
    sorted_chars = sorted(characters, key=lambda c: c.get('mentions', 0), reverse=True)

    for i, char in enumerate(sorted_chars[:15], 1):
        logger.info(
            f"  {i:2d}. {char['full_name']:30s}: "
            f"{char['mentions']:3d} mentions, "
            f"confidence {char['confidence']:.2f}"
        )

    # Show LLM usage if available
    if hasattr(extractor, 'llm_client') and extractor.llm_client:
        usage = extractor.llm_client.get_usage_stats()
        logger.info(f"\nLLM Usage:")
        logger.info(f"  Input tokens:  {usage['total_input_tokens']:,}")
        logger.info(f"  Output tokens: {usage['total_output_tokens']:,}")
        logger.info(f"  Total cost:    ${usage['estimated_cost_usd']:.4f}")
        cost = usage['estimated_cost_usd']
    else:
        cost = 0.0

    logger.info("\n" + "="*80)
    logger.info("CHARACTER DISCOVERY COMPLETE")
    logger.info("="*80)

    return {
        "total_characters": len(characters),
        "llm_cost": cost
    }


if __name__ == "__main__":
    main()
