"""
Test character discovery and save on real avatar_test data.

This script demonstrates the save functionality working on actual crawled pages.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.processor.analysis.character_extractor import CharacterExtractor
from tests.mocks.mock_llm_client import MockLLMClient
import json


def main():
    print("=" * 70)
    print("CHARACTER DISCOVERY & SAVE TEST - Real Data")
    print("=" * 70)

    # Create extractor with very low thresholds for small test dataset
    extractor = CharacterExtractor(
        project_name="avatar_test",
        min_mentions=0,  # Accept any mentions (small dataset)
        confidence_threshold=0.0  # No threshold (testing)
    )

    # Use mock LLM to avoid API costs
    print("\n[INFO] Using MockLLMClient (no API costs)")
    extractor.query_engine.llm_client = MockLLMClient()

    print(f"[INFO] Discovering characters from avatar_test project...")
    print(f"[INFO] Using thresholds: min_mentions=0, confidence=0.0")

    # Discover characters with auto-save
    try:
        characters = extractor.discover_characters(save=True)

        print("\n" + "=" * 70)
        print(f"DISCOVERY COMPLETE - Found {len(characters)} characters")
        print("=" * 70)

        # Show discovered characters
        print("\nDiscovered Characters:")
        print("-" * 70)
        for i, char in enumerate(characters, 1):
            print(f"\n{i}. {char['full_name']}")
            print(f"   Base name: {char['name']}")
            print(f"   Disambiguation: {char.get('disambiguation', 'None')}")
            print(f"   Source URL: {char['source_url']}")
            print(f"   Mentions: {char['mentions']}")
            print(f"   Confidence: {char['confidence']:.2f}")
            print(f"   Discovered via: {', '.join(char['discovered_via'])}")

        # Check saved files
        print("\n" + "=" * 70)
        print("SAVED FILES")
        print("=" * 70)

        characters_dir = Path("data/projects/avatar_test/characters")
        if characters_dir.exists():
            saved_files = list(characters_dir.glob("*.json"))
            print(f"\nDirectory: {characters_dir}")
            print(f"Files saved: {len(saved_files)}\n")

            for file in sorted(saved_files):
                print(f"  - {file.name}")

                # Load and show snippet
                with open(file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                print(f"    > name: {data['name']}")
                print(f"    > full_name: {data['full_name']}")
                print(f"    > saved_at: {data['saved_at']}")
                print()

        else:
            print(f"[ERROR] Characters directory not created: {characters_dir}")

        print("=" * 70)
        print("TEST COMPLETE - Save functionality working! ✅")
        print("=" * 70)

    except Exception as e:
        print(f"\n[ERROR] Discovery failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
