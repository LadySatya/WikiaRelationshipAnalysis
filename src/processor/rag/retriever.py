"""
RAGRetriever - Semantic search for RAG queries.

This module provides semantic search functionality by combining EmbeddingGenerator
and VectorStore. It retrieves relevant document chunks for RAG queries and formats
them for LLM consumption.
"""
from typing import List, Dict, Any, Optional

from .embeddings import EmbeddingGenerator
from .vector_store import VectorStore
from ..config import get_config


class RAGRetriever:
    """
    Retriever for semantic search in RAG workflows.

    Combines embedding generation and vector search to find relevant chunks
    for user queries. Provides formatted context for LLM prompts.

    Args:
        project_name: Name of the wikia project
        vector_store_path: Custom path for vector store (default: from config)

    Example:
        >>> retriever = RAGRetriever(project_name="avatar_wiki")
        >>>
        >>> # Retrieve relevant chunks
        >>> results = retriever.retrieve("Who is Aang?", k=5)
        >>>
        >>> # Build formatted context for LLM
        >>> context = retriever.build_context(results)
        >>> print(context)
    """

    def __init__(
        self,
        project_name: str,
        vector_store_path: Optional[str] = None
    ) -> None:
        """
        Initialize RAGRetriever with project-specific components.

        Args:
            project_name: Name of the wikia project
            vector_store_path: Custom path for vector store (default: from config)
        """
        self.project_name = project_name

        # Load config
        config = get_config()

        # Initialize embedding generator
        self.embedding_generator = EmbeddingGenerator()

        # Initialize vector store for this project
        if vector_store_path:
            self.vector_store = VectorStore(
                project_name=project_name,
                persist_directory=vector_store_path
            )
        else:
            self.vector_store = VectorStore(project_name=project_name)

    def retrieve(
        self,
        query: str,
        k: int = 10,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant chunks for a query using semantic search.

        Args:
            query: User query text
            k: Number of results to return (default: 10)
            metadata_filter: Optional metadata filter (e.g., {"namespace": "Character"})

        Returns:
            List of result dictionaries with structure:
                {
                    "id": "chunk_id",
                    "text": "chunk text",
                    "metadata": {...},
                    "distance": 0.123
                }

        Raises:
            ValueError: If query is empty
        """
        # Validate query
        if not query or not query.strip():
            raise ValueError("query cannot be empty")

        # Generate embedding for query
        query_embedding = self.embedding_generator.generate_embedding(query.strip())

        # Search vector store
        results = self.vector_store.similarity_search(
            query_embedding=query_embedding,
            k=k,
            metadata_filter=metadata_filter
        )

        return results

    def build_context(self, chunks: List[Dict[str, Any]]) -> str:
        """
        Build formatted context string from retrieved chunks for LLM prompts.

        Args:
            chunks: List of retrieved chunk dictionaries

        Returns:
            Formatted context string with chunks and sources

        Example output:
            ```
            Retrieved Information:

            [Chunk 1]
            Aang is the Avatar and last airbender.
            Source: https://example.com/aang

            [Chunk 2]
            He was found frozen in an iceberg.
            Source: https://example.com/aang
            ```
        """
        if not chunks:
            return "No relevant information found."

        context_parts = ["Retrieved Information:\n"]

        for i, chunk in enumerate(chunks, 1):
            text = chunk.get("text", "")
            metadata = chunk.get("metadata", {})
            url = metadata.get("url", "Unknown source")

            context_parts.append(f"[Chunk {i}]")
            context_parts.append(text)
            context_parts.append(f"Source: {url}")
            context_parts.append("")  # Empty line for spacing

        return "\n".join(context_parts)
