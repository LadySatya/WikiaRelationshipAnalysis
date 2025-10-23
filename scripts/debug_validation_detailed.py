"""
Detailed debug of validation step to see why mentions are 0.
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
    print("DEBUG: VALIDATION STEP DETAILED")
    print("=" * 80)

    extractor = CharacterExtractor(
        project_name="avatar_test",
        min_mentions=0,
        confidence_threshold=0.0
    )

    # Discover characters
    print("\n[INFO] Discovering characters...")
    raw_characters = extractor._execute_discovery_queries()
    merged = extractor._deduplicate_characters(raw_characters)

    # Pick one character to debug
    if merged:
        char = merged[0]  # Debug first character
        print(f"\n[INFO] Debugging validation for: {char['full_name']}")
        print(f"[INFO] Source URL: {char['source_url']}")
        print(f"[INFO] Disambiguation: {char.get('disambiguation')}")

        # Manually run validation logic with debug output
        name = char["name"]
        disambiguation = char.get("disambiguation")
        source_url = char.get("source_url", "")

        # Build query
        if disambiguation:
            query = f"{name} {disambiguation}"
        else:
            query = f"Information about {name}"

        print(f"\n[INFO] RAG query: '{query}'")

        # Query vector store
        chunks = extractor.query_engine.retriever.retrieve(
            query=query,
            k=50
        )

        print(f"[INFO] Retrieved {len(chunks)} chunks from vector store")

        if chunks:
            print("\n[INFO] Sample chunk metadata (first 3):")
            for i, chunk in enumerate(chunks[:3], 1):
                metadata = chunk.get("metadata", {})
                print(f"  Chunk {i}:")
                print(f"    source_url: {metadata.get('source_url', 'MISSING')}")
                print(f"    title: {metadata.get('title', 'MISSING')}")
                print(f"    distance: {chunk.get('distance', 'N/A')}")
                print()

        # Filter by source URL
        url_identifier = source_url.split("/wiki/")[-1] if "/wiki/" in source_url else source_url
        print(f"[INFO] Filtering chunks with URL identifier: '{url_identifier}'")

        url_filtered_chunks = [
            chunk for chunk in chunks
            if url_identifier in chunk.get("metadata", {}).get("source_url", "")
        ]

        print(f"[INFO] After URL filtering: {len(url_filtered_chunks)} chunks")

        if not url_filtered_chunks and chunks:
            print("\n[WARN] No chunks matched URL filter!")
            print("[WARN] This is why mentions = 0")
            print("\n[INFO] Checking first chunk's source_url vs character's source_url:")
            chunk_url = chunks[0].get("metadata", {}).get("source_url", "")
            print(f"  Character source_url: {source_url}")
            print(f"  Chunk source_url:     {chunk_url}")
            print(f"  URL identifier:       {url_identifier}")
            print(f"  Identifier in chunk URL: {url_identifier in chunk_url}")

        # Show usage
        usage = extractor.query_engine.llm_client.get_usage_stats()
        print(f"\n[INFO] LLM cost so far: ${usage['estimated_cost_usd']:.4f}")

    else:
        print("[ERROR] No characters discovered")


if __name__ == "__main__":
    main()
