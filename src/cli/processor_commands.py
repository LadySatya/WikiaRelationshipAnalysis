"""
Phase 2 CLI commands: Processing and character analysis.
"""

from pathlib import Path
from typing import Optional
from .utils import validate_project_exists, setup_project_logging


def index_command(project_name: str):
    """
    Build vector database index from crawled pages.

    Args:
        project_name: Name of the project to index
    """
    from processor.core.content_chunker import ContentChunker
    from processor.rag.embeddings import EmbeddingGenerator
    from processor.rag.vector_store import VectorStore
    from processor.config import ProcessorConfig
    import json

    # Validate project exists with crawled data
    project_path = validate_project_exists(project_name, require_crawled=True)

    # Setup logging
    logger = setup_project_logging(project_name, "PHASE 2: INDEXING")

    processed_dir = project_path / "processed"
    page_files = list(processed_dir.glob("*.json"))

    logger.info(f"Loaded {len(page_files)} crawled pages")

    # Load all pages
    pages = []
    for file_path in page_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Keep full structure - chunker expects nested content field
            pages.append(data)

    logger.info("Chunking pages...")

    # Chunk pages
    config = ProcessorConfig()
    chunker = ContentChunker(
        chunk_size=config.get("processor", "rag", "chunk_size", default=500),
        chunk_overlap=config.get("processor", "rag", "chunk_overlap", default=50)
    )

    all_chunks = []
    for page in pages:
        chunks = chunker.chunk_page(page)
        all_chunks.extend(chunks)

    logger.info(f"Created {len(all_chunks)} chunks total")

    # Generate embeddings
    logger.info("Indexing into ChromaDB...")
    logger.info("Generating embeddings...")

    embedding_generator = EmbeddingGenerator()
    texts = [chunk["text"] for chunk in all_chunks]

    embeddings = embedding_generator.generate_embeddings(texts)
    logger.info(f"Generated {len(embeddings)} embeddings")

    # Combine texts, embeddings, and metadata into chunk format
    chunks_with_embeddings = []
    for i, chunk in enumerate(all_chunks):
        chunks_with_embeddings.append({
            "text": chunk["text"],
            "embedding": embeddings[i],
            "metadata": chunk["metadata"]
        })

    # Store in ChromaDB
    vector_store = VectorStore(project_name=project_name)

    # Add to vector store in batches (ChromaDB has max batch size limit)
    batch_size = 5000
    total_chunks = len(chunks_with_embeddings)
    for i in range(0, total_chunks, batch_size):
        batch = chunks_with_embeddings[i:i + batch_size]
        logger.info(f"Adding batch {i//batch_size + 1}/{(total_chunks + batch_size - 1)//batch_size} ({len(batch)} chunks)")
        vector_store.add_documents(batch)

    logger.info(f"Indexed {len(all_chunks)} chunks into ChromaDB")
    logger.info(f"Collection: {project_name}_collection")

    # Test retrieval
    logger.info("\nTesting retrieval...")
    from processor.rag.retriever import RAGRetriever

    retriever = RAGRetriever(project_name=project_name)
    test_query = "Who is Aang?"
    results = retriever.retrieve(test_query, k=3)

    logger.info(f"Query: '{test_query}'")
    for i, result in enumerate(results, 1):
        preview = result["text"][:100] + "..." if len(result["text"]) > 100 else result["text"]
        logger.info(f"  {i}. {preview}")

    logger.info("")
    logger.info("=" * 80)
    logger.info("INDEXING COMPLETE")
    logger.info("=" * 80)
    logger.info("")
    logger.info(f"[INFO] Next step: python main.py discover {project_name}")


def discover_command(
    project_name: str,
    max_pages: Optional[int] = None,
    save_frequency: int = 10
):
    """
    Build knowledge base (characters + relationships) from indexed data.

    This unified command replaces the old discover + build pipeline.
    The LLM processes pages sequentially and builds a knowledge base
    of all characters and their relationships.

    Args:
        project_name: Name of the project
        max_pages: Maximum number of pages to process (None = all)
        save_frequency: Save KB every N pages (default: 10)
    """
    from processor.analysis.knowledge_builder import CharacterKnowledgeBuilder
    import time

    # Validate project exists with crawled data
    validate_project_exists(project_name, require_crawled=True)

    # Setup logging
    logger = setup_project_logging(project_name, "PHASE 3: KNOWLEDGE BUILDING")

    logger.info("Starting unified knowledge building...")
    logger.info("LLM will extract characters and relationships from all pages")
    logger.info("")

    # Create knowledge builder
    builder = CharacterKnowledgeBuilder(
        project_name=project_name,
        save_frequency=save_frequency
    )

    # Build knowledge base
    start_time = time.time()
    kb = builder.build_knowledge_base(max_pages=max_pages)
    duration = time.time() - start_time

    # Calculate statistics
    num_characters = len(kb["characters"])
    num_relationships = len(kb["relationships"])

    total_claims = sum(
        len(rel.get("claims", []))
        for rel in kb["relationships"].values()
    )

    avg_claims = total_claims / num_relationships if num_relationships else 0

    logger.info("")
    logger.info("=" * 80)
    logger.info("KNOWLEDGE BUILDING COMPLETE - SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Characters discovered: {num_characters}")
    logger.info(f"Relationships found: {num_relationships}")
    logger.info(f"Total relationship claims: {total_claims}")
    logger.info(f"Avg claims per relationship: {avg_claims:.1f}")
    logger.info(f"Time: {duration:.1f}s")

    # Show top characters by source count
    logger.info("")
    logger.info("Top characters by sources:")
    top_chars = sorted(
        kb["characters"].items(),
        key=lambda x: len(x[1].get("source_urls", [])),
        reverse=True
    )[:10]

    for i, (name, char_data) in enumerate(top_chars, 1):
        sources = len(char_data.get("source_urls", []))
        aliases = len(char_data.get("aliases", []))
        logger.info(f"   {i:2d}. {name:30s} : {sources:3d} sources, {aliases} aliases")

    # Show sample relationship
    if kb["relationships"]:
        logger.info("")
        logger.info("Sample relationship:")
        sample_key = list(kb["relationships"].keys())[0]
        sample_rel = kb["relationships"][sample_key]
        char_a, char_b = sample_key

        logger.info(f"  {char_a} <-> {char_b}")
        logger.info(f"  Type: {sample_rel.get('type', 'Unknown')}")
        logger.info(f"  Summary: {sample_rel.get('summary', 'No summary')}")
        logger.info(f"  Claims: {len(sample_rel.get('claims', []))}")

        if sample_rel.get("claims"):
            first_claim = sample_rel["claims"][0]
            logger.info(f"    - \"{first_claim.get('claim', 'No claim text')}\"")
            evidence_list = first_claim.get("evidence", [])
            if evidence_list:
                logger.info(f"      Evidence ({len(evidence_list)} sources):")
                for i, evidence in enumerate(evidence_list[:2], 1):  # Show first 2
                    logger.info(f"        {i}. {evidence.get('evidence_url', 'No URL')}")
            else:
                logger.info(f"      Evidence: None")

    # Show usage stats
    usage = builder.query_engine.get_usage_stats()
    logger.info("")
    logger.info("LLM Usage:")
    logger.info(f"  Input tokens:  {usage['total_input_tokens']:,}")
    logger.info(f"  Output tokens: {usage['total_output_tokens']:,}")
    logger.info(f"  Total cost:    ${usage['estimated_cost_usd']:.4f}")

    logger.info("")
    logger.info("=" * 80)
    logger.info("")
    logger.info(f"[INFO] Next step: python main.py validate {project_name}")
