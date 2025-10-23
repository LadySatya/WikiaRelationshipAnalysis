"""
Debug script to see what happens during real LLM character discovery.
Shows which characters were found and why they failed validation.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from src.processor.analysis.character_extractor import CharacterExtractor


def main():
    print("=" * 80)
    print("DEBUG: REAL LLM CHARACTER DISCOVERY")
    print("=" * 80)

    # Create extractor with ZERO thresholds to see everything
    extractor = CharacterExtractor(
        project_name="avatar_test",
        min_mentions=0,  # Accept everything
        confidence_threshold=0.0  # No threshold
    )

    # NOTE: Using REAL LLM (not MockLLM)
    print("\n[INFO] Using REAL LLMClient (Claude API)")

    # Manually run just the discovery part (no validation)
    print("\n[INFO] Loading pages...")
    raw_characters = extractor._execute_discovery_queries()

    print(f"\n[INFO] Found {len(raw_characters)} raw character mentions")

    # Deduplicate
    merged = extractor._deduplicate_characters(raw_characters)
    print(f"[INFO] After dedup: {len(merged)} unique characters\n")

    # Show what was discovered BEFORE validation
    print("Characters discovered (before validation):")
    print("-" * 80)
    for i, char in enumerate(merged, 1):
        print(f"{i}. {char['full_name']}")
        print(f"   Source: {char['source_url']}")
        print(f"   Discovered via: {', '.join(char['discovered_via'])}")
        print()

    # Now run validation with debug
    print("\n" + "=" * 80)
    print("VALIDATION STEP")
    print("=" * 80)

    validated = extractor._validate_characters(merged)

    print(f"\n[INFO] After validation: {len(validated)} characters passed\n")

    if validated:
        print("Characters that passed validation:")
        print("-" * 80)
        for i, char in enumerate(validated, 1):
            print(f"{i}. {char['full_name']}")
            print(f"   Mentions: {char['mentions']}")
            print(f"   Confidence: {char['confidence']:.2f}")
            print()
    else:
        print("[WARN] No characters passed validation")
        print("\nLikely reasons:")
        print("  - RAG retrieval not finding character names in chunks")
        print("  - Character names don't match how they appear in text")
        print("  - Chunks use pronouns instead of names")

    # Show LLM usage
    print("\n" + "=" * 80)
    print("LLM USAGE")
    print("=" * 80)
    usage = extractor.query_engine.llm_client.get_usage_stats()
    print(f"\nModel: {usage['model']}")
    print(f"Total tokens: {usage['total_tokens']:,}")
    print(f"Cost: ${usage['estimated_cost_usd']:.4f}")


if __name__ == "__main__":
    main()
