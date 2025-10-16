"""
EmbeddingGenerator - generates vector embeddings from text chunks.

This module handles converting text into dense vector representations (embeddings)
that can be stored in a vector database for semantic search. Supports both local
models (sentence-transformers) and cloud providers (Voyage AI).
"""
from typing import List, Dict, Any, Optional, Union
import numpy as np
from pathlib import Path
import os

from ..config import get_config


class EmbeddingGenerator:
    """
    Generates vector embeddings from text using configurable providers.

    Supports:
    - Local models via sentence-transformers (no API key needed, runs offline)
    - Voyage AI for production use (requires VOYAGE_API_KEY)

    Args:
        provider: Embedding provider - "local" or "voyage" (default: "local")
        model_name: Model to use for embeddings (default depends on provider)
        api_key: API key for cloud providers (optional, reads from env if not provided)

    Raises:
        ValueError: If provider is not supported
        Exception: If model loading or API initialization fails

    Example:
        >>> generator = EmbeddingGenerator(provider="local")
        >>> embedding = generator.generate_embedding("Aang is the Avatar")
        >>> print(embedding.shape)  # (384,) for all-MiniLM-L6-v2
    """

    SUPPORTED_PROVIDERS = {"local", "voyage"}

    def __init__(
        self,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None
    ) -> None:
        """
        Initialize EmbeddingGenerator with specified provider and model.

        Args:
            provider: Embedding provider - "local" or "voyage" (default: from config)
            model_name: Model to use (default: from config based on provider)
            api_key: API key for cloud providers (default: from VOYAGE_API_KEY env)
        """
        # Load config
        config = get_config()

        # Set provider from config if not specified
        if provider is None:
            provider = config.embedding_provider

        # Validate provider
        if provider not in self.SUPPORTED_PROVIDERS:
            raise ValueError(
                f"provider must be one of {self.SUPPORTED_PROVIDERS}, got '{provider}'"
            )

        self.provider = provider
        self._model = None  # Lazy loading
        self._client = None  # For API-based providers
        self._cached_dimension = None  # Cache dimension after first query

        # Set model name from config if not specified
        if model_name is None:
            if provider == "local":
                model_name = config.local_model
            elif provider == "voyage":
                model_name = config.voyage_model

        self.model_name = model_name
        self.api_key = api_key or os.getenv("VOYAGE_API_KEY")

    def _load_local_model(self) -> None:
        """Load sentence-transformers model for local embedding generation."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)

    def _init_voyage_client(self) -> None:
        """Initialize Voyage AI client for cloud-based embeddings."""
        if self._client is None:
            import voyageai
            self._client = voyageai.Client(api_key=self.api_key)

    def generate_embedding(self, text: str) -> np.ndarray:
        """
        Generate embedding vector for a single text.

        Args:
            text: Input text to embed

        Returns:
            Numpy array containing the embedding vector

        Raises:
            Exception: If model loading or API call fails
        """
        if self.provider == "local":
            self._load_local_model()
            embedding = self._model.encode(text, convert_to_numpy=True)
            return embedding

        elif self.provider == "voyage":
            self._init_voyage_client()
            response = self._client.embed([text], model=self.model_name)
            # Convert to numpy array
            return np.array(response.embeddings[0])

    def generate_embeddings(self, texts: List[str]) -> List[np.ndarray]:
        """
        Generate embeddings for multiple texts in batch.

        Batch processing is more efficient than generating embeddings one at a time.

        Args:
            texts: List of input texts to embed

        Returns:
            List of numpy arrays, one embedding per input text

        Raises:
            Exception: If model loading or API call fails
        """
        if not texts:
            return []

        if self.provider == "local":
            self._load_local_model()
            # Batch encode all texts at once
            embeddings_array = self._model.encode(texts, convert_to_numpy=True)
            # Convert to list of individual numpy arrays
            return [embeddings_array[i] for i in range(len(embeddings_array))]

        elif self.provider == "voyage":
            self._init_voyage_client()
            response = self._client.embed(texts, model=self.model_name)
            # Convert to list of numpy arrays
            return [np.array(emb) for emb in response.embeddings]

    def embed_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Add embeddings to chunked wiki page data.

        Processes chunks in batch for efficiency and adds embedding vector
        to each chunk dictionary.

        Args:
            chunks: List of chunk dictionaries with structure:
                {
                    "text": "chunk text",
                    "metadata": {...}
                }

        Returns:
            List of chunk dictionaries with added "embedding" field:
                {
                    "text": "chunk text",
                    "metadata": {...},
                    "embedding": np.ndarray([...])
                }
        """
        if not chunks:
            return []

        # Extract all texts for batch processing
        texts = [chunk["text"] for chunk in chunks]

        # Generate embeddings in batch
        embeddings = self.generate_embeddings(texts)

        # Add embeddings to chunks
        embedded_chunks = []
        for chunk, embedding in zip(chunks, embeddings):
            embedded_chunk = {
                "text": chunk["text"],
                "metadata": chunk["metadata"],
                "embedding": embedding
            }
            embedded_chunks.append(embedded_chunk)

        return embedded_chunks

    @property
    def embedding_dimension(self) -> int:
        """
        Get the dimensionality of embeddings produced by this generator.

        Returns dimension by querying the actual model/API, not hardcoded values.
        Result is cached after first query for performance.

        Returns:
            Integer dimension of embedding vectors
        """
        # Return cached dimension if available
        if self._cached_dimension is not None:
            return self._cached_dimension

        # For local models, query the model directly
        if self.provider == "local":
            self._load_local_model()
            self._cached_dimension = self._model.get_sentence_embedding_dimension()
            return self._cached_dimension

        # For Voyage AI, generate a test embedding to get dimension
        elif self.provider == "voyage":
            # Generate a minimal test embedding to discover dimension
            test_embedding = self.generate_embedding("test")
            self._cached_dimension = len(test_embedding)
            return self._cached_dimension

        raise ValueError(f"Cannot determine embedding dimension for provider '{self.provider}'")
