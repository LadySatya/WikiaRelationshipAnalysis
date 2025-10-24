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
            # Extract content from wrapper
            if "content" in data:
                pages.append(data["content"])
            else:
                pages.append(data)

    logger.info("Chunking pages...")

    # Chunk pages
    config = ProcessorConfig()
    chunker = ContentChunker(
        chunk_size=config.get("processor.rag.chunk_size", 500),
        chunk_overlap=config.get("processor.rag.chunk_overlap", 50)
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
    metadatas = [chunk["metadata"] for chunk in all_chunks]

    embeddings = embedding_generator.generate_batch(texts)
    logger.info(f"Generated {len(embeddings)} embeddings")

    # Store in ChromaDB
    vector_store = VectorStore(
        project_name=project_name,
        collection_name=f"{project_name}_collection"
    )

    # Add to vector store
    vector_store.add_documents(
        texts=texts,
        embeddings=embeddings,
        metadatas=metadatas
    )

    logger.info(f"Indexed {len(all_chunks)} chunks into ChromaDB")
    logger.info(f"Collection: {project_name}_collection")

    # Test retrieval
    logger.info("\nTesting retrieval...")
    test_query = "Who is Aang?"
    results = vector_store.query(test_query, k=3)

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
    min_mentions: int = 3,
    confidence_threshold: float = 0.7
):
    """
    Discover characters from indexed data.

    Args:
        project_name: Name of the project
        min_mentions: Minimum mentions required to consider a character
        confidence_threshold: Minimum confidence score (0.0-1.0)
    """
    from processor.analysis.character_extractor import CharacterExtractor

    # Validate project exists with crawled data
    validate_project_exists(project_name, require_crawled=True)

    # Setup logging
    logger = setup_project_logging(project_name, "PHASE 3: CHARACTER DISCOVERY")

    logger.info("Starting character discovery...")

    # Create extractor
    extractor = CharacterExtractor(
        project_name=project_name,
        min_mentions=min_mentions,
        confidence_threshold=confidence_threshold
    )

    # Discover characters with auto-save
    characters = extractor.discover_characters(save=True)

    logger.info("")
    logger.info(f"Discovered {len(characters)} characters")
    logger.info("")
    logger.info("Top characters by mentions:")

    for i, char in enumerate(characters[:10], 1):
        name = char.get('full_name', char['name'])
        mentions = char.get('mentions', 0)
        confidence = char.get('confidence', 0.0)
        logger.info(f"   {i:2d}. {name:30s} : {mentions:3d} mentions, confidence {confidence:.2f}")

    logger.info("")
    logger.info("=" * 80)
    logger.info("CHARACTER DISCOVERY COMPLETE")
    logger.info("=" * 80)
    logger.info("")
    logger.info(f"[INFO] Next step: python main.py build {project_name}")


def build_command(project_name: str, max_characters: Optional[int] = 5):
    """
    Build relationship profiles for discovered characters.

    Args:
        project_name: Name of the project
        max_characters: Maximum number of characters to profile (default: 5)
    """
    from processor.analysis.profile_builder import ProfileBuilder
    from processor.analysis.character_extractor import CharacterExtractor
    import time

    # Validate project exists with crawled data
    validate_project_exists(project_name, require_crawled=True)

    # Setup logging
    logger = setup_project_logging(project_name, "PHASE 4: RELATIONSHIP EXTRACTION")

    # Load discovered characters
    characters = CharacterExtractor.load_discovered_characters(project_name)
    all_characters = characters["characters"]

    logger.info(f"Loaded {len(all_characters)} discovered characters")

    # Limit to top N by mentions
    top_characters = sorted(
        all_characters,
        key=lambda c: c.get("mentions", 0),
        reverse=True
    )[:max_characters]

    logger.info("")
    logger.info(f"Building profiles for top {len(top_characters)} characters:")
    for char in top_characters:
        logger.info(f"  - {char.get('full_name', char['name'])}")

    logger.info("")
    logger.info("Building profiles (this may take 10-20 minutes)...")

    # Build profiles
    builder = ProfileBuilder(project_name=project_name)

    start_time = time.time()
    profiles = builder.build_profiles(top_characters, save=True)
    duration = time.time() - start_time

    # Calculate statistics
    total_relationships = sum(
        len(profile.get("relationships", []))
        for profile in profiles.values()
    )

    avg_relationships = total_relationships / len(profiles) if profiles else 0

    logger.info("")
    logger.info("=" * 80)
    logger.info("RELATIONSHIP EXTRACTION COMPLETE - SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Characters profiled: {len(profiles)}")
    logger.info(f"Total relationships: {total_relationships}")
    logger.info(f"Avg relationships/character: {avg_relationships:.1f}")
    logger.info(f"Time: {duration:.1f}s ({duration/len(profiles):.1f}s per character)")

    # Show sample relationship
    if profiles:
        first_char = list(profiles.keys())[0]
        first_profile = profiles[first_char]
        if first_profile.get("relationships"):
            rel = first_profile["relationships"][0]
            logger.info("")
            logger.info(f"Sample relationship: {first_char} -> {rel['target']}")
            logger.info(f"  Type: {rel['type']}")
            logger.info(f"  Summary: {rel['summary'][:100]}...")
            logger.info(f"  Evidence: {rel.get('total_evidence_count', 0)} citations")
            logger.info(f"  Confidence: {rel.get('overall_confidence', 0.0):.2f}")

            # Show first claim
            if rel.get("narrative", {}).get("claims_with_evidence"):
                claims = rel["narrative"]["claims_with_evidence"]
                claim = claims[0]
                logger.info("")
                logger.info(f"  First claim: \"{claim['claim']}\"")
                logger.info(f"    Evidence: {len(claim.get('evidence', []))} citations, confidence {claim.get('confidence', 0.0):.2f}")
                if claim.get('evidence'):
                    evidence = claim['evidence'][0]
                    cited_preview = evidence['cited_text'][:80] + "..." if len(evidence['cited_text']) > 80 else evidence['cited_text']
                    logger.info(f"    Source: {evidence.get('title', 'Unknown')}")
                    logger.info(f"    Cited: {cited_preview}")

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
