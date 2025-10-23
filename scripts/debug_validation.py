"""
Debug script to see what's happening during character validation.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.processor.analysis.character_extractor import CharacterExtractor
from tests.mocks.mock_llm_client import MockLLMClient


def main():
    print("=" * 80)
    print("DEBUG: CHARACTER VALIDATION")
    print("=" * 80)

    # Create extractor with ZERO thresholds
    extractor = CharacterExtractor(
        project_name="avatar_fresh",
        min_mentions=0,  # Accept everything
        confidence_threshold=0.0  # No threshold
    )

    # Use mock LLM
    extractor.query_engine.llm_client = MockLLMClient()

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
        print("  - RAG retrieval not finding enough mentions")
        print("  - URL filtering too strict")
        print("  - Mock LLM classification issues")


if __name__ == "__main__":
    main()
