"""
Complete end-to-end demonstration of Phase 2 RAG pipeline.

Steps:
1. Index crawled pages into vector store (ChromaDB)
2. Discover characters using RAG validation
3. Save discovered characters to disk

This proves the entire Phase 2 workflow.
"""

import sys
from pathlib import Path
import json

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.processor.core.content_chunker import ContentChunker
from src.processor.rag.embeddings import EmbeddingGenerator
from src.processor.rag.vector_store import VectorStore
from src.processor.analysis.character_extractor import CharacterExtractor
from tests.mocks.mock_llm_client import MockLLMClient


def index_pages(project_name: str):
    """Index all crawled pages into vector store."""
    print("=" * 80)
    print("STEP 1: INDEXING PAGES INTO VECTOR STORE")
    print("=" * 80)

    # Load pages
    processed_dir = Path(f"data/projects/{project_name}/processed")
    pages = []

    print(f"\n[INFO] Loading pages from {processed_dir}")
    for file_path in processed_dir.glob("*.json"):
        with open(file_path, 'r', encoding='utf-8') as f:
            page_wrapper = json.load(f)
            pages.append(page_wrapper)

    print(f"[INFO] Loaded {len(pages)} pages")

    # Initialize components
    print("\n[INFO] Initializing components...")
    print("  - ContentChunker")
    print("  - EmbeddingGenerator (local model: all-MiniLM-L6-v2)")
    print("  - VectorStore (ChromaDB)")

    chunker = ContentChunker()
    embedding_gen = EmbeddingGenerator(provider="local")
    vector_store = VectorStore(
        project_name=project_name,
        persist_directory="data/projects"
    )

    # Chunk and index each page
    print("\n[INFO] Chunking and indexing pages...")
    total_chunks = 0

    for i, page in enumerate(pages, 1):
        # Extract title for display
        title = page.get("content", {}).get("title", "Unknown")
        print(f"  [{i}/{len(pages)}] {title[:60]}...", end=" ")

        # Chunk the page
        chunks = chunker.chunk_page(page)
        print(f"({len(chunks)} chunks)", end=" ")

        if chunks:
            # Generate embeddings
            texts = [chunk["text"] for chunk in chunks]
            embeddings = embedding_gen.generate_embeddings(texts)

            # Add embeddings and metadata to chunks
            for j, chunk in enumerate(chunks):
                chunk["embedding"] = embeddings[j]
                chunk["metadata"]["source_url"] = page.get("url", "")
                chunk["metadata"]["title"] = page.get("content", {}).get("title", "")

            # Store in vector database
            vector_store.add_documents(chunks)
            total_chunks += len(chunks)
            print("[OK]")
        else:
            print("[SKIP - No chunks]")

    print(f"\n[OK] Indexed {len(pages)} pages with {total_chunks} total chunks")
    print(f"[OK] Vector store saved to: data/projects/{project_name}/vector_store/")


def discover_characters(project_name: str):
    """Discover characters using RAG validation."""
    print("\n" + "=" * 80)
    print("STEP 2: DISCOVERING CHARACTERS WITH RAG VALIDATION")
    print("=" * 80)

    # Create extractor with low thresholds (small dataset)
    print("\n[INFO] Creating CharacterExtractor...")
    print(f"  - min_mentions: 1 (at least 1 chunk mention)")
    print(f"  - confidence_threshold: 0.1 (low for testing)")

    extractor = CharacterExtractor(
        project_name=project_name,
        min_mentions=1,
        confidence_threshold=0.1
    )

    # Use mock LLM (no API costs)
    print("\n[INFO] Using MockLLMClient (no API costs)")
    extractor.query_engine.llm_client = MockLLMClient()

    # Run discovery with auto-save
    print("\n[INFO] Running discovery pipeline...")
    characters = extractor.discover_characters(save=True)

    return characters


def show_results(project_name: str, characters: list):
    """Display discovery results."""
    print("\n" + "=" * 80)
    print("STEP 3: RESULTS")
    print("=" * 80)

    print(f"\n[SUMMARY] Discovered {len(characters)} characters")

    if characters:
        print("\nDiscovered Characters:")
        print("-" * 80)
        for i, char in enumerate(characters, 1):
            print(f"\n{i}. {char['full_name']}")
            print(f"   Name: {char['name']}")
            if char.get('disambiguation'):
                print(f"   Disambiguation: {char['disambiguation']}")
            print(f"   Source: {char['source_url'].split('/wiki/')[-1]}")
            print(f"   Mentions: {char['mentions']} chunks")
            print(f"   Confidence: {char['confidence']:.2f}")
            print(f"   Discovered via: {', '.join(char['discovered_via'])}")

    # Show saved files
    characters_dir = Path(f"data/projects/{project_name}/characters")
    if characters_dir.exists():
        saved_files = sorted(characters_dir.glob("*.json"))

        print("\n" + "-" * 80)
        print(f"Saved Files ({len(saved_files)}):")
        print("-" * 80)
        print(f"Location: {characters_dir}\n")

        for file in saved_files:
            print(f"  - {file.name}")


def main():
    print("=" * 80)
    print("COMPLETE END-TO-END PHASE 2 DEMONSTRATION")
    print("=" * 80)

    project_name = "avatar_fresh"

    # Check if pages exist
    processed_dir = Path(f"data/projects/{project_name}/processed")
    if not processed_dir.exists():
        print(f"\n[ERROR] No processed pages found at {processed_dir}")
        print("[ERROR] Please run the crawler first")
        return

    page_count = len(list(processed_dir.glob("*.json")))
    print(f"\nProject: {project_name}")
    print(f"Crawled pages: {page_count}")

    try:
        # Step 1: Index pages
        index_pages(project_name)

        # Step 2: Discover characters
        characters = discover_characters(project_name)

        # Step 3: Show results
        show_results(project_name, characters)

        print("\n" + "=" * 80)
        print("DEMONSTRATION COMPLETE")
        print("=" * 80)
        print("\n[OK] Full Phase 2 pipeline working end-to-end!")
        print(f"[OK] Indexed {page_count} pages")
        print(f"[OK] Discovered {len(characters)} characters")
        print(f"[OK] Characters saved to data/projects/{project_name}/characters/")

    except Exception as e:
        print(f"\n[ERROR] Pipeline failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
