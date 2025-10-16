"""
VectorStore - ChromaDB-based vector database for semantic search.

This module handles persistent storage of embeddings in ChromaDB for efficient
semantic similarity search. Each wikia project gets its own isolated collection.
"""
from typing import List, Dict, Any, Optional
import numpy as np
from pathlib import Path
import uuid
import re

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
        # Validate and sanitize project name
        if not project_name or not project_name.strip():
            raise ValueError("project_name cannot be empty")

        project_name = project_name.strip()

        # SECURITY: Prevent path traversal attacks
        # Only allow alphanumeric, underscore, and hyphen characters
        if not re.match(r'^[a-zA-Z0-9_-]+$', project_name):
            raise ValueError(
                f"Invalid project_name '{project_name}'. "
                "Only alphanumeric characters, underscores, and hyphens are allowed."
            )

        # Validate length (ChromaDB collection names: 3-512 chars)
        if len(project_name) < 3:
            raise ValueError("project_name must be at least 3 characters long")

        if len(project_name) > 255:
            raise ValueError("project_name too long (max 255 characters)")

        self.project_name = project_name

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

    def _validate_embedding(
        self, embedding: Any, index: int, expected_dim: Optional[int] = None
    ) -> int:
        """
        Validate embedding is correct type and dimension.

        Args:
            embedding: Embedding to validate
            index: Chunk index (for error messages)
            expected_dim: Expected dimension (for consistency check)

        Returns:
            Dimension of the embedding

        Raises:
            ValueError: If embedding is invalid
        """
        # Convert to numpy if it's a list
        if isinstance(embedding, list):
            embedding = np.array(embedding)

        # Validate type
        if not isinstance(embedding, np.ndarray):
            raise ValueError(
                f"Chunk at index {index}: embedding must be numpy array or list, "
                f"got {type(embedding).__name__}"
            )

        # Validate not empty
        if embedding.size == 0:
            raise ValueError(f"Chunk at index {index}: embedding cannot be empty")

        # Validate 1D array
        if len(embedding.shape) != 1:
            raise ValueError(
                f"Chunk at index {index}: embedding must be 1-dimensional, "
                f"got shape {embedding.shape}"
            )

        # Validate no NaN or Inf
        if not np.isfinite(embedding).all():
            raise ValueError(
                f"Chunk at index {index}: embedding contains NaN or Inf values"
            )

        # Get dimension
        dim = embedding.shape[0]

        # Validate dimension consistency
        if expected_dim is not None and dim != expected_dim:
            raise ValueError(
                f"Chunk at index {index}: embedding dimension mismatch. "
                f"Expected {expected_dim}, got {dim}"
            )

        return dim

    def _validate_metadata(self, metadata: Dict[str, Any], index: int) -> None:
        """
        Validate metadata contains only ChromaDB-compatible types.

        ChromaDB only supports primitive types: str, int, float, bool, None

        Args:
            metadata: Metadata dictionary to validate
            index: Chunk index (for error messages)

        Raises:
            ValueError: If metadata contains invalid types
        """
        allowed_types = (str, int, float, bool, type(None))

        for key, value in metadata.items():
            if not isinstance(value, allowed_types):
                raise ValueError(
                    f"Chunk at index {index}: metadata field '{key}' has invalid type "
                    f"{type(value).__name__}. Only str, int, float, bool, and None are allowed."
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

        # Validate all chunks and extract components
        expected_dim = None
        validated_embeddings = []
        texts = []
        metadatas = []

        for i, chunk in enumerate(chunks):
            # Validate chunk has embedding
            if "embedding" not in chunk:
                raise ValueError(
                    f"Chunk at index {i} missing 'embedding' field"
                )

            # Validate and get embedding dimension
            dim = self._validate_embedding(chunk["embedding"], i, expected_dim)
            if expected_dim is None:
                expected_dim = dim  # First chunk sets expected dimension

            # Convert embedding to list for ChromaDB
            embedding = chunk["embedding"]
            if isinstance(embedding, np.ndarray):
                embedding = embedding.tolist()
            validated_embeddings.append(embedding)

            # Extract text
            texts.append(chunk.get("text", ""))

            # Validate and extract metadata
            metadata = chunk.get("metadata", {})
            self._validate_metadata(metadata, i)
            metadatas.append(metadata)

        # Generate unique IDs for each document
        doc_ids = [str(uuid.uuid4()) for _ in chunks]

        # Add to ChromaDB collection with exception handling
        try:
            self._collection.add(
                ids=doc_ids,
                documents=texts,
                embeddings=validated_embeddings,
                metadatas=metadatas
            )
        except Exception as e:
            raise Exception(
                f"Failed to add documents to ChromaDB collection '{self._collection.name}': {str(e)}"
            ) from e

        return doc_ids

    def similarity_search(
        self,
        query_embedding: np.ndarray,
        k: int = 10,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for documents similar to the query embedding.

        Args:
            query_embedding: Query vector to search for
            k: Number of results to return (default: 10)
            metadata_filter: Optional metadata filter dictionary (e.g., {"namespace": "Character"})

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
        if metadata_filter is not None:
            query_params["where"] = metadata_filter

        # Query ChromaDB with exception handling
        try:
            results = self._collection.query(**query_params)
        except Exception as e:
            raise Exception(
                f"Failed to query ChromaDB collection '{self._collection.name}': {str(e)}"
            ) from e

        # Format results into list of dictionaries
        formatted_results = []

        # ChromaDB returns nested lists for batch queries
        # We only have one query, so extract first element
        ids = results["ids"][0] if results["ids"] else []
        documents = results["documents"][0] if results["documents"] else []
        metadatas = results["metadatas"][0] if results["metadatas"] else []
        distances = results["distances"][0] if results["distances"] else []

        # Validate result arrays have same length
        if not (len(ids) == len(documents) == len(metadatas) == len(distances)):
            raise Exception(
                f"ChromaDB returned mismatched result array lengths: "
                f"ids={len(ids)}, documents={len(documents)}, "
                f"metadatas={len(metadatas)}, distances={len(distances)}"
            )

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

        Raises:
            Exception: If ChromaDB operations fail
        """
        collection_name = self._collection.name
        collection_metadata = self._collection.metadata

        try:
            # Delete the collection
            self._client.delete_collection(name=collection_name)

            # Recreate empty collection
            self._collection = self._client.get_or_create_collection(
                name=collection_name,
                metadata=collection_metadata
            )
        except Exception as e:
            raise Exception(
                f"Failed to clear ChromaDB collection '{collection_name}': {str(e)}"
            ) from e

    def has_documents(self) -> bool:
        """
        Check if the collection has any documents.

        Returns:
            True if collection has at least one document, False otherwise
        """
        return self._collection.count() > 0
