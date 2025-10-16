"""
VectorStore - ChromaDB-based vector database for semantic search.

This module handles persistent storage of embeddings in ChromaDB for efficient
semantic similarity search. Each wikia project gets its own isolated collection.
"""
from typing import List, Dict, Any, Optional
import numpy as np
from pathlib import Path
import uuid

import chromadb
from chromadb.config import Settings

from ..config import get_config


class VectorStore:
    """
    Persistent vector database for storing and querying embeddings.

    Uses ChromaDB as the underlying vector database with project-specific
    collections for isolation. Supports metadata filtering and semantic
    similarity search.

    Args:
        project_name: Name of the wikia project (used for collection naming)
        persist_directory: Custom persistence directory (default: from config)

    Raises:
        ValueError: If project_name is empty or invalid
        Exception: If ChromaDB initialization fails

    Example:
        >>> store = VectorStore(project_name="naruto_wiki")
        >>> chunks = [
        ...     {
        ...         "text": "Naruto is a ninja",
        ...         "embedding": np.array([0.1, 0.2, 0.3]),
        ...         "metadata": {"url": "https://example.com", "chunk_index": 0}
        ...     }
        ... ]
        >>> doc_ids = store.add_documents(chunks)
        >>> query_embedding = np.array([0.1, 0.2, 0.3])
        >>> results = store.similarity_search(query_embedding, k=5)
    """

    def __init__(
        self,
        project_name: str,
        persist_directory: Optional[str] = None
    ) -> None:
        """
        Initialize VectorStore with project-specific collection.

        Args:
            project_name: Name of the wikia project
            persist_directory: Custom persistence directory (default: from config)
        """
        # Validate project name
        if not project_name or not project_name.strip():
            raise ValueError("project_name cannot be empty")

        self.project_name = project_name.strip()

        # Load config for default settings
        config = get_config()

        # Determine persistence directory
        if persist_directory is None:
            # Use config default path
            persist_directory = config.vector_store_path

        # Ensure path is absolute and includes project name
        persist_path = Path(persist_directory) / self.project_name
        persist_path.mkdir(parents=True, exist_ok=True)

        # Initialize ChromaDB persistent client
        self._client = chromadb.PersistentClient(
            path=str(persist_path),
            settings=Settings(anonymized_telemetry=False)
        )

        # Create or get project-specific collection
        # Collection name is based on project name
        collection_name = f"{self.project_name}_collection"
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"project": self.project_name}
        )

    def add_documents(self, chunks: List[Dict[str, Any]]) -> List[str]:
        """
        Add documents with embeddings to the vector store.

        Args:
            chunks: List of chunk dictionaries with structure:
                {
                    "text": "chunk text",
                    "embedding": np.ndarray([...]),
                    "metadata": {"url": "...", "chunk_index": 0, ...}
                }

        Returns:
            List of generated document IDs

        Raises:
            ValueError: If chunks are missing required fields
            Exception: If ChromaDB add operation fails
        """
        if not chunks:
            return []

        # Validate all chunks have embeddings
        for i, chunk in enumerate(chunks):
            if "embedding" not in chunk:
                raise ValueError(
                    f"Chunk at index {i} missing 'embedding' field"
                )

        # Generate unique IDs for each document
        doc_ids = [str(uuid.uuid4()) for _ in chunks]

        # Extract components for ChromaDB
        texts = [chunk.get("text", "") for chunk in chunks]
        embeddings = [
            chunk["embedding"].tolist()
            if isinstance(chunk["embedding"], np.ndarray)
            else chunk["embedding"]
            for chunk in chunks
        ]
        metadatas = [chunk.get("metadata", {}) for chunk in chunks]

        # Add to ChromaDB collection
        self._collection.add(
            ids=doc_ids,
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas
        )

        return doc_ids

    def similarity_search(
        self,
        query_embedding: np.ndarray,
        k: int = 10,
        filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for documents similar to the query embedding.

        Args:
            query_embedding: Query vector to search for
            k: Number of results to return (default: 10)
            filter: Optional metadata filter dictionary (e.g., {"namespace": "Character"})

        Returns:
            List of result dictionaries with structure:
                {
                    "id": "doc_id",
                    "text": "document text",
                    "metadata": {...},
                    "distance": 0.123
                }

        Raises:
            ValueError: If k <= 0
            Exception: If ChromaDB query fails
        """
        if k <= 0:
            raise ValueError("k must be greater than 0")

        # Convert numpy array to list for ChromaDB
        if isinstance(query_embedding, np.ndarray):
            query_embedding = query_embedding.tolist()

        # Build query parameters
        query_params = {
            "query_embeddings": [query_embedding],
            "n_results": k
        }

        # Add metadata filter if provided
        if filter is not None:
            query_params["where"] = filter

        # Query ChromaDB
        results = self._collection.query(**query_params)

        # Format results into list of dictionaries
        formatted_results = []

        # ChromaDB returns nested lists for batch queries
        # We only have one query, so extract first element
        ids = results["ids"][0] if results["ids"] else []
        documents = results["documents"][0] if results["documents"] else []
        metadatas = results["metadatas"][0] if results["metadatas"] else []
        distances = results["distances"][0] if results["distances"] else []

        for doc_id, text, metadata, distance in zip(ids, documents, metadatas, distances):
            formatted_results.append({
                "id": doc_id,
                "text": text,
                "metadata": metadata,
                "distance": distance
            })

        return formatted_results

    def get_collection_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the collection.

        Returns:
            Dictionary with collection statistics:
                {
                    "name": "collection_name",
                    "count": 42,
                    "metadata": {...}
                }
        """
        return {
            "name": self._collection.name,
            "count": self._collection.count(),
            "metadata": self._collection.metadata
        }

    def clear(self) -> None:
        """
        Clear all documents from the collection.

        This deletes and recreates the collection, removing all documents.
        """
        collection_name = self._collection.name
        collection_metadata = self._collection.metadata

        # Delete the collection
        self._client.delete_collection(name=collection_name)

        # Recreate empty collection
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata=collection_metadata
        )

    def collection_exists(self) -> bool:
        """
        Check if the collection exists and has documents.

        Returns:
            True if collection has at least one document, False otherwise
        """
        return self._collection.count() > 0
