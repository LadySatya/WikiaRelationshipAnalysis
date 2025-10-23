"""
Test character discovery using REAL Claude API calls.

This script:
1. Loads ANTHROPIC_API_KEY from .env
2. Indexes 20 crawled pages into ChromaDB
3. Runs character discovery with real LLM classification
4. Shows results and cost statistics
"""

import sys
from pathlib import Path
import json

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load .env file BEFORE importing our modules
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("[OK] Loaded .env file")
except ImportError:
    print("[WARN] python-dotenv not installed, using system environment")

import os

# Verify API key
api_key = os.getenv("ANTHROPIC_API_KEY")
if not api_key:
    print("[ERROR] ANTHROPIC_API_KEY not found in environment")
    print("[ERROR] Please set it in your .env file")
    sys.exit(1)

print(f"[OK] ANTHROPIC_API_KEY loaded (length: {len(api_key)})")

# Now import our modules
from src.processor.core.content_chunker import ContentChunker
from src.processor.rag.embeddings import EmbeddingGenerator
from src.processor.rag.vector_store import VectorStore
from src.processor.analysis.character_extractor import CharacterExtractor


def index_pages(project_name: str):
    """Index all crawled pages into vector store."""
    print("\n" + "=" * 80)
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

    print(f"[OK] Loaded {len(pages)} pages")

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
    """Discover characters using REAL Claude API."""
    print("\n" + "=" * 80)
    print("STEP 2: DISCOVERING CHARACTERS WITH REAL CLAUDE API")
    print("=" * 80)

    # Create extractor with low thresholds (small dataset)
    print("\n[INFO] Creating CharacterExtractor...")
    print("  - min_mentions: 1 (at least 1 chunk mention)")
    print("  - confidence_threshold: 0.1 (low for testing)")

    extractor = CharacterExtractor(
        project_name=project_name,
        min_mentions=1,
        confidence_threshold=0.1
    )

    # NOTE: We are NOT setting MockLLM - using real LLM client!
    print("\n[INFO] Using REAL LLMClient (Claude API)")
    print("[INFO] This will incur API costs (estimated: $0.03-0.10)")

    # Run discovery with auto-save
    print("\n[INFO] Running discovery pipeline...")
    print("[INFO] This may take 30-60 seconds...")

    characters = extractor.discover_characters(save=True)

    return characters, extractor


def show_results(project_name: str, characters: list, extractor: CharacterExtractor):
    """Display discovery results and cost stats."""
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

    # Show cost statistics
    print("\n" + "=" * 80)
    print("LLM USAGE STATISTICS")
    print("=" * 80)

    usage = extractor.query_engine.llm_client.get_usage_stats()

    print(f"\nModel: {usage['model']}")
    print(f"Input tokens: {usage['total_input_tokens']:,}")
    print(f"Output tokens: {usage['total_output_tokens']:,}")
    print(f"Total tokens: {usage['total_tokens']:,}")
    print(f"\nEstimated cost: ${usage['estimated_cost_usd']:.4f}")

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
    print("CHARACTER DISCOVERY WITH REAL CLAUDE API")
    print("=" * 80)

    project_name = "avatar_test"

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

        # Step 2: Discover characters with REAL LLM
        characters, extractor = discover_characters(project_name)

        # Step 3: Show results
        show_results(project_name, characters, extractor)

        print("\n" + "=" * 80)
        print("DISCOVERY COMPLETE")
        print("=" * 80)
        print("\n[OK] Character discovery with real LLM working!")
        print(f"[OK] Indexed {page_count} pages")
        print(f"[OK] Discovered {len(characters)} characters")
        print(f"[OK] Characters saved to data/projects/{project_name}/characters/")

    except Exception as e:
        print(f"\n[ERROR] Pipeline failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
