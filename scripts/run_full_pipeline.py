"""
Run the full character discovery pipeline on fresh crawled data.

This demonstrates the complete flow:
1. Load crawled pages
2. Classify as characters (3-tier system)
3. Validate with RAG
4. Save to disk

Using MockLLM to avoid API costs.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.processor.analysis.character_extractor import CharacterExtractor
from tests.mocks.mock_llm_client import MockLLMClient
import json


def main():
    print("=" * 80)
    print("FULL CHARACTER DISCOVERY PIPELINE")
    print("=" * 80)

    project_name = "avatar_fresh"

    # Check crawled pages
    processed_dir = Path(f"data/projects/{project_name}/processed")
    page_count = len(list(processed_dir.glob("*.json")))

    print(f"\nProject: {project_name}")
    print(f"Crawled pages: {page_count}")

    # Create extractor with reasonable thresholds
    print("\n[INFO] Creating CharacterExtractor...")
    print(f"  - min_mentions: 1")
    print(f"  - confidence_threshold: 0.1")

    extractor = CharacterExtractor(
        project_name=project_name,
        min_mentions=1,
        confidence_threshold=0.1
    )

    # Use mock LLM (no API costs)
    print("\n[INFO] Using MockLLMClient (no API costs)")
    extractor.query_engine.llm_client = MockLLMClient()

    # Run discovery with auto-save
    print("\n" + "=" * 80)
    print("RUNNING CHARACTER DISCOVERY")
    print("=" * 80)

    characters = extractor.discover_characters(save=True)

    # Show results
    print("\n" + "=" * 80)
    print(f"DISCOVERY COMPLETE - Found {len(characters)} characters")
    print("=" * 80)

    if characters:
        print("\nDiscovered Characters:")
        print("-" * 80)
        for i, char in enumerate(characters, 1):
            print(f"\n{i}. {char['full_name']}")
            print(f"   Name: {char['name']}")
            if char.get('disambiguation'):
                print(f"   Disambiguation: {char['disambiguation']}")
            print(f"   URL: {char['source_url']}")
            print(f"   Mentions: {char['mentions']}")
            print(f"   Confidence: {char['confidence']:.2f}")
            print(f"   Discovered via: {', '.join(char['discovered_via'])}")
    else:
        print("\n[WARN] No characters discovered")

    # Show saved files
    print("\n" + "=" * 80)
    print("SAVED CHARACTER FILES")
    print("=" * 80)

    characters_dir = Path(f"data/projects/{project_name}/characters")
    if characters_dir.exists():
        saved_files = sorted(characters_dir.glob("*.json"))
        print(f"\nLocation: {characters_dir}")
        print(f"Files: {len(saved_files)}\n")

        for file in saved_files:
            # Load file to show key info
            with open(file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            print(f"  {file.name}")
            print(f"    > Name: {data['name']}")
            print(f"    > Source: {data['source_url'].split('/wiki/')[-1]}")
            print(f"    > Saved: {data['saved_at']}")
            print()
    else:
        print(f"[ERROR] No characters directory found: {characters_dir}")

    print("=" * 80)
    print("PIPELINE COMPLETE")
    print("=" * 80)

    # Summary
    print(f"\n[SUMMARY]")
    print(f"  Crawled pages: {page_count}")
    print(f"  Characters discovered: {len(characters)}")
    print(f"  Characters saved: {len(list(characters_dir.glob('*.json'))) if characters_dir.exists() else 0}")
    print(f"  Save location: {characters_dir}")


if __name__ == "__main__":
    main()
