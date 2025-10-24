"""
PoC Script: Index Avatar Wiki Content

Indexes crawled pages into ChromaDB for RAG queries.
"""
import sys
from pathlib import Path
import json

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.logging_config import setup_project_logger
from src.processor.rag.vector_store import VectorStore
from src.processor.core.content_chunker import ContentChunker


def main():
    project_name = "avatar_poc"

    # Setup logging
    logger, log_file = setup_project_logger(project_name)

    logger.info("="*80)
    logger.info("AVATAR WIKI POC - PHASE 2: INDEXING")
    logger.info("="*80)

    # Load crawled pages from processed directory
    processed_dir = Path("data") / "projects" / project_name / "processed"

    if not processed_dir.exists():
        logger.error(f"Processed data directory not found: {processed_dir}")
        logger.error("Run poc_crawl_avatar.py first!")
        return {}

    pages = []
    for file in processed_dir.glob("*.json"):
        with open(file, encoding="utf-8") as f:
            saved_data = json.load(f)
            # ContentSaver wraps the extracted content in a structure like:
            # {"url": "...", "saved_at": "...", "content": {...}}
            # But chunk_page expects: {"url": "...", "content": {...}}
            # So we need to restructure
            if "content" in saved_data:
                pages.append({
                    "url": saved_data.get("url", ""),
                    "content": saved_data["content"]
                })
            else:
                # Fallback for old format without wrapper
                pages.append(saved_data)

    logger.info(f"Loaded {len(pages)} crawled pages")

    # Chunk content
    logger.info("Chunking pages...")
    chunker = ContentChunker(chunk_size=500, chunk_overlap=50)
    all_chunks = []

    for page in pages:
        chunks = chunker.chunk_page(page)
        all_chunks.extend(chunks)
        logger.debug(f"  {page.get('title', 'Unknown')}: {len(chunks)} chunks")

    logger.info(f"Created {len(all_chunks)} chunks total")

    # Index into ChromaDB
    logger.info("Indexing into ChromaDB...")

    # Note: VectorStore expects chunks with embeddings already computed
    # We need to add embeddings to the chunks first
    from src.processor.rag.embeddings import EmbeddingGenerator

    logger.info("Generating embeddings...")
    embedding_gen = EmbeddingGenerator()

    # Add embeddings to chunks
    texts = [chunk["text"] for chunk in all_chunks]
    embeddings = embedding_gen.generate_embeddings(texts)

    for chunk, embedding in zip(all_chunks, embeddings):
        chunk["embedding"] = embedding

    logger.info(f"Generated {len(embeddings)} embeddings")

    # Now add to vector store
    vector_store = VectorStore(project_name=project_name)
    doc_ids = vector_store.add_documents(all_chunks)

    logger.info(f"Indexed {len(doc_ids)} chunks into ChromaDB")
    logger.info(f"Collection: {project_name}_collection")

    # Test retrieval
    logger.info("\nTesting retrieval...")
    from src.processor.rag.retriever import RAGRetriever

    # RAGRetriever creates its own vector_store and embedding_gen instances
    retriever = RAGRetriever(project_name=project_name)
    test_query = "Who is Aang?"
    results = retriever.retrieve(test_query, k=3)

    logger.info(f"Query: '{test_query}'")
    for i, result in enumerate(results[:3], 1):
        logger.info(f"  {i}. {result['text'][:100]}...")

    logger.info("\n" + "="*80)
    logger.info("INDEXING COMPLETE")
    logger.info("="*80)

    return {"total_chunks": len(all_chunks)}


if __name__ == "__main__":
    main()
