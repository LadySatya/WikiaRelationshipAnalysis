"""
Tests for VectorStore - ChromaDB-based vector database for semantic search.

Following TDD methodology: write tests first, then implement.
This module tests the VectorStore class which handles:
- Persistent storage of embeddings in ChromaDB
- Project-specific collection management
- Similarity search with metadata filtering
- Document addition and retrieval
"""
import pytest
import numpy as np
import tempfile
import shutil
from pathlib import Path
from typing import List, Dict, Any
from unittest.mock import Mock, patch, MagicMock


# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit


class TestVectorStoreInitialization:
    """Test VectorStore initialization and configuration."""

    def test_init_with_project_name(self):
        """VectorStore should initialize with project name and create collection."""
        from src.processor.rag.vector_store import VectorStore

        with patch("chromadb.PersistentClient") as mock_client_class:
            mock_client = MagicMock()
            mock_collection = MagicMock()
            mock_client.get_or_create_collection.return_value = mock_collection
            mock_client_class.return_value = mock_client

            store = VectorStore(project_name="naruto_wiki")

            assert store.project_name == "naruto_wiki"
            mock_client.get_or_create_collection.assert_called_once()

    def test_init_with_custom_persist_directory(self):
        """VectorStore should support custom persistence directory."""
        from src.processor.rag.vector_store import VectorStore

        with patch("chromadb.PersistentClient") as mock_client_class:
            mock_client = MagicMock()
            mock_collection = MagicMock()
            mock_client.get_or_create_collection.return_value = mock_collection
            mock_client_class.return_value = mock_client

            custom_dir = "/custom/path"
            store = VectorStore(project_name="test_project", persist_directory=custom_dir)

            # Should use custom directory for ChromaDB client
            mock_client_class.assert_called_once()
            call_kwargs = mock_client_class.call_args[1]
            # Normalize path for cross-platform compatibility (Windows uses \)
            path_used = str(call_kwargs.get("path", "")).replace("\\", "/")
            assert custom_dir in path_used

    def test_init_uses_config_default_path(self):
        """VectorStore should use config default path when no persist_directory provided."""
        from src.processor.rag.vector_store import VectorStore

        with patch("chromadb.PersistentClient") as mock_client_class:
            mock_client = MagicMock()
            mock_collection = MagicMock()
            mock_client.get_or_create_collection.return_value = mock_collection
            mock_client_class.return_value = mock_client

            store = VectorStore(project_name="test_project")

            # Should use config path (data/vector_stores)
            mock_client_class.assert_called_once()
            call_kwargs = mock_client_class.call_args[1]
            assert "vector_stores" in str(call_kwargs.get("path", ""))

    def test_init_validates_project_name(self):
        """VectorStore should validate project name is not empty."""
        from src.processor.rag.vector_store import VectorStore

        with pytest.raises(ValueError, match="project_name cannot be empty"):
            VectorStore(project_name="")

        with pytest.raises(ValueError, match="project_name cannot be empty"):
            VectorStore(project_name="   ")

    def test_init_creates_persistent_client(self):
        """VectorStore should create PersistentClient for disk storage."""
        from src.processor.rag.vector_store import VectorStore

        with patch("chromadb.PersistentClient") as mock_client_class:
            mock_client = MagicMock()
            mock_collection = MagicMock()
            mock_client.get_or_create_collection.return_value = mock_collection
            mock_client_class.return_value = mock_client

            VectorStore(project_name="test_project")

            # Should use PersistentClient, not Client (ephemeral)
            mock_client_class.assert_called_once()


class TestVectorStoreDocumentAddition:
    """Test adding documents to vector store."""

    def test_add_documents_with_embeddings(self):
        """VectorStore should add documents with embeddings and metadata."""
        from src.processor.rag.vector_store import VectorStore

        with patch("chromadb.PersistentClient") as mock_client_class:
            mock_client = MagicMock()
            mock_collection = MagicMock()
            mock_client.get_or_create_collection.return_value = mock_collection
            mock_client_class.return_value = mock_client

            chunks = [
                {
                    "text": "Aang is the Avatar",
                    "embedding": np.array([0.1, 0.2, 0.3]),
                    "metadata": {"url": "https://example.com/aang", "chunk_index": 0}
                },
                {
                    "text": "Katara is a waterbender",
                    "embedding": np.array([0.4, 0.5, 0.6]),
                    "metadata": {"url": "https://example.com/katara", "chunk_index": 1}
                }
            ]

            store = VectorStore(project_name="avatar_wiki")
            doc_ids = store.add_documents(chunks)

            # Should add documents to collection
            mock_collection.add.assert_called_once()
            assert len(doc_ids) == 2
            assert all(isinstance(doc_id, str) for doc_id in doc_ids)

    def test_add_documents_generates_unique_ids(self):
        """VectorStore should generate unique IDs for each document."""
        from src.processor.rag.vector_store import VectorStore

        with patch("chromadb.PersistentClient") as mock_client_class:
            mock_client = MagicMock()
            mock_collection = MagicMock()
            mock_client.get_or_create_collection.return_value = mock_collection
            mock_client_class.return_value = mock_client

            chunks = [
                {
                    "text": f"Document {i}",
                    "embedding": np.random.rand(3),
                    "metadata": {"chunk_index": i}
                }
                for i in range(5)
            ]

            store = VectorStore(project_name="test_wiki")
            doc_ids = store.add_documents(chunks)

            # All IDs should be unique
            assert len(doc_ids) == len(set(doc_ids))

    def test_add_documents_preserves_metadata(self):
        """VectorStore should preserve all metadata fields when adding documents."""
        from src.processor.rag.vector_store import VectorStore

        with patch("chromadb.PersistentClient") as mock_client_class:
            mock_client = MagicMock()
            mock_collection = MagicMock()
            mock_client.get_or_create_collection.return_value = mock_collection
            mock_client_class.return_value = mock_client

            chunks = [
                {
                    "text": "Test text",
                    "embedding": np.array([0.1, 0.2, 0.3]),
                    "metadata": {
                        "url": "https://example.com",
                        "page_title": "Test Page",
                        "chunk_index": 0,
                        "namespace": "Main"
                    }
                }
            ]

            store = VectorStore(project_name="test_wiki")
            store.add_documents(chunks)

            # Verify metadata was passed to ChromaDB
            call_kwargs = mock_collection.add.call_args[1]
            metadatas = call_kwargs.get("metadatas", [])
            assert len(metadatas) == 1
            assert metadatas[0]["url"] == "https://example.com"
            assert metadatas[0]["page_title"] == "Test Page"

    def test_add_documents_converts_numpy_to_list(self):
        """VectorStore should convert numpy arrays to lists for ChromaDB."""
        from src.processor.rag.vector_store import VectorStore

        with patch("chromadb.PersistentClient") as mock_client_class:
            mock_client = MagicMock()
            mock_collection = MagicMock()
            mock_client.get_or_create_collection.return_value = mock_collection
            mock_client_class.return_value = mock_client

            chunks = [
                {
                    "text": "Test",
                    "embedding": np.array([0.1, 0.2, 0.3]),
                    "metadata": {}
                }
            ]

            store = VectorStore(project_name="test_wiki")
            store.add_documents(chunks)

            # ChromaDB expects lists, not numpy arrays
            call_kwargs = mock_collection.add.call_args[1]
            embeddings = call_kwargs.get("embeddings", [])
            assert isinstance(embeddings[0], list)

    def test_add_documents_validates_chunks_have_embeddings(self):
        """VectorStore should validate chunks contain embeddings."""
        from src.processor.rag.vector_store import VectorStore

        with patch("chromadb.PersistentClient") as mock_client_class:
            mock_client = MagicMock()
            mock_collection = MagicMock()
            mock_client.get_or_create_collection.return_value = mock_collection
            mock_client_class.return_value = mock_client

            # Chunk missing embedding field
            chunks = [
                {
                    "text": "Test text",
                    "metadata": {}
                }
            ]

            store = VectorStore(project_name="test_wiki")

            with pytest.raises(ValueError, match="missing 'embedding' field"):
                store.add_documents(chunks)

    def test_add_documents_empty_list(self):
        """VectorStore should handle empty document list gracefully."""
        from src.processor.rag.vector_store import VectorStore

        with patch("chromadb.PersistentClient") as mock_client_class:
            mock_client = MagicMock()
            mock_collection = MagicMock()
            mock_client.get_or_create_collection.return_value = mock_collection
            mock_client_class.return_value = mock_client

            store = VectorStore(project_name="test_wiki")
            doc_ids = store.add_documents([])

            # Should return empty list without calling ChromaDB
            assert doc_ids == []
            mock_collection.add.assert_not_called()


class TestVectorStoreSimilaritySearch:
    """Test semantic similarity search functionality."""

    def test_similarity_search_basic(self):
        """VectorStore should perform similarity search with query embedding."""
        from src.processor.rag.vector_store import VectorStore

        with patch("chromadb.PersistentClient") as mock_client_class:
            mock_client = MagicMock()
            mock_collection = MagicMock()

            # Mock ChromaDB query response
            mock_collection.query.return_value = {
                "ids": [["doc1", "doc2"]],
                "documents": [["Text 1", "Text 2"]],
                "metadatas": [[{"url": "url1"}, {"url": "url2"}]],
                "distances": [[0.1, 0.2]]
            }

            mock_client.get_or_create_collection.return_value = mock_collection
            mock_client_class.return_value = mock_client

            store = VectorStore(project_name="test_wiki")
            query_embedding = np.array([0.1, 0.2, 0.3])
            results = store.similarity_search(query_embedding, k=2)

            # Should return list of result dictionaries
            assert len(results) == 2
            assert results[0]["text"] == "Text 1"
            assert results[0]["metadata"]["url"] == "url1"
            assert "distance" in results[0]

    def test_similarity_search_with_k_parameter(self):
        """VectorStore should respect k parameter for number of results."""
        from src.processor.rag.vector_store import VectorStore

        with patch("chromadb.PersistentClient") as mock_client_class:
            mock_client = MagicMock()
            mock_collection = MagicMock()
            mock_collection.query.return_value = {
                "ids": [["doc1"]],
                "documents": [["Text 1"]],
                "metadatas": [[{"url": "url1"}]],
                "distances": [[0.1]]
            }
            mock_client.get_or_create_collection.return_value = mock_collection
            mock_client_class.return_value = mock_client

            store = VectorStore(project_name="test_wiki")
            query_embedding = np.array([0.1, 0.2, 0.3])
            store.similarity_search(query_embedding, k=5)

            # Should pass k to ChromaDB query
            call_kwargs = mock_collection.query.call_args[1]
            assert call_kwargs["n_results"] == 5

    def test_similarity_search_with_metadata_filter(self):
        """VectorStore should support metadata filtering in searches."""
        from src.processor.rag.vector_store import VectorStore

        with patch("chromadb.PersistentClient") as mock_client_class:
            mock_client = MagicMock()
            mock_collection = MagicMock()
            mock_collection.query.return_value = {
                "ids": [["doc1"]],
                "documents": [["Filtered text"]],
                "metadatas": [[{"url": "url1", "namespace": "Character"}]],
                "distances": [[0.1]]
            }
            mock_client.get_or_create_collection.return_value = mock_collection
            mock_client_class.return_value = mock_client

            store = VectorStore(project_name="test_wiki")
            query_embedding = np.array([0.1, 0.2, 0.3])

            # Filter to only character pages
            filter_dict = {"namespace": "Character"}
            results = store.similarity_search(query_embedding, k=5, filter=filter_dict)

            # Should pass filter to ChromaDB
            call_kwargs = mock_collection.query.call_args[1]
            assert call_kwargs.get("where") == filter_dict

    def test_similarity_search_converts_numpy_to_list(self):
        """VectorStore should convert numpy query embedding to list."""
        from src.processor.rag.vector_store import VectorStore

        with patch("chromadb.PersistentClient") as mock_client_class:
            mock_client = MagicMock()
            mock_collection = MagicMock()
            mock_collection.query.return_value = {
                "ids": [[]],
                "documents": [[]],
                "metadatas": [[]],
                "distances": [[]]
            }
            mock_client.get_or_create_collection.return_value = mock_collection
            mock_client_class.return_value = mock_client

            store = VectorStore(project_name="test_wiki")
            query_embedding = np.array([0.1, 0.2, 0.3])
            store.similarity_search(query_embedding)

            # Should convert numpy to list for ChromaDB
            call_kwargs = mock_collection.query.call_args[1]
            query_embeddings = call_kwargs["query_embeddings"]
            assert isinstance(query_embeddings[0], list)

    def test_similarity_search_no_results(self):
        """VectorStore should handle empty search results gracefully."""
        from src.processor.rag.vector_store import VectorStore

        with patch("chromadb.PersistentClient") as mock_client_class:
            mock_client = MagicMock()
            mock_collection = MagicMock()
            mock_collection.query.return_value = {
                "ids": [[]],
                "documents": [[]],
                "metadatas": [[]],
                "distances": [[]]
            }
            mock_client.get_or_create_collection.return_value = mock_collection
            mock_client_class.return_value = mock_client

            store = VectorStore(project_name="test_wiki")
            query_embedding = np.array([0.1, 0.2, 0.3])
            results = store.similarity_search(query_embedding)

            assert results == []


class TestVectorStoreCollectionManagement:
    """Test collection management operations."""

    def test_get_collection_stats(self):
        """VectorStore should return collection statistics."""
        from src.processor.rag.vector_store import VectorStore

        with patch("chromadb.PersistentClient") as mock_client_class:
            mock_client = MagicMock()
            mock_collection = MagicMock()
            mock_collection.count.return_value = 42
            mock_collection.name = "test_wiki_collection"
            mock_client.get_or_create_collection.return_value = mock_collection
            mock_client_class.return_value = mock_client

            store = VectorStore(project_name="test_wiki")
            stats = store.get_collection_stats()

            assert stats["count"] == 42
            assert stats["name"] == "test_wiki_collection"

    def test_clear_collection(self):
        """VectorStore should clear all documents from collection."""
        from src.processor.rag.vector_store import VectorStore

        with patch("chromadb.PersistentClient") as mock_client_class:
            mock_client = MagicMock()
            mock_collection = MagicMock()
            mock_client.get_or_create_collection.return_value = mock_collection
            mock_client.delete_collection = MagicMock()
            mock_client_class.return_value = mock_client

            store = VectorStore(project_name="test_wiki")
            store.clear()

            # Should delete and recreate collection
            mock_client.delete_collection.assert_called_once()

    def test_collection_exists_true(self):
        """VectorStore should detect if collection exists and has documents."""
        from src.processor.rag.vector_store import VectorStore

        with patch("chromadb.PersistentClient") as mock_client_class:
            mock_client = MagicMock()
            mock_collection = MagicMock()
            mock_collection.count.return_value = 10
            mock_client.get_or_create_collection.return_value = mock_collection
            mock_client_class.return_value = mock_client

            store = VectorStore(project_name="test_wiki")

            assert store.collection_exists() is True

    def test_collection_exists_false_empty(self):
        """VectorStore should return False for empty collections."""
        from src.processor.rag.vector_store import VectorStore

        with patch("chromadb.PersistentClient") as mock_client_class:
            mock_client = MagicMock()
            mock_collection = MagicMock()
            mock_collection.count.return_value = 0
            mock_client.get_or_create_collection.return_value = mock_collection
            mock_client_class.return_value = mock_client

            store = VectorStore(project_name="test_wiki")

            assert store.collection_exists() is False


class TestVectorStoreEdgeCases:
    """Test edge cases and error handling."""

    def test_add_documents_with_special_characters_in_metadata(self):
        """VectorStore should handle special characters in metadata."""
        from src.processor.rag.vector_store import VectorStore

        with patch("chromadb.PersistentClient") as mock_client_class:
            mock_client = MagicMock()
            mock_collection = MagicMock()
            mock_client.get_or_create_collection.return_value = mock_collection
            mock_client_class.return_value = mock_client

            chunks = [
                {
                    "text": "Test with unicode: 気水火土",
                    "embedding": np.array([0.1, 0.2, 0.3]),
                    "metadata": {
                        "url": "https://example.com/氣",
                        "title": "Avatar: The Last Airbender™"
                    }
                }
            ]

            store = VectorStore(project_name="test_wiki")
            doc_ids = store.add_documents(chunks)

            assert len(doc_ids) == 1
            mock_collection.add.assert_called_once()

    def test_similarity_search_with_zero_k(self):
        """VectorStore should handle k=0 gracefully."""
        from src.processor.rag.vector_store import VectorStore

        with patch("chromadb.PersistentClient") as mock_client_class:
            mock_client = MagicMock()
            mock_collection = MagicMock()
            mock_collection.query.return_value = {
                "ids": [[]],
                "documents": [[]],
                "metadatas": [[]],
                "distances": [[]]
            }
            mock_client.get_or_create_collection.return_value = mock_collection
            mock_client_class.return_value = mock_client

            store = VectorStore(project_name="test_wiki")
            query_embedding = np.array([0.1, 0.2, 0.3])

            with pytest.raises(ValueError, match="k must be greater than 0"):
                store.similarity_search(query_embedding, k=0)

    def test_add_documents_with_mismatched_embedding_dimensions(self):
        """VectorStore should detect mismatched embedding dimensions."""
        from src.processor.rag.vector_store import VectorStore

        with patch("chromadb.PersistentClient") as mock_client_class:
            mock_client = MagicMock()
            mock_collection = MagicMock()
            # Simulate ChromaDB dimension error
            mock_collection.add.side_effect = Exception("Embedding dimension mismatch")
            mock_client.get_or_create_collection.return_value = mock_collection
            mock_client_class.return_value = mock_client

            chunks = [
                {
                    "text": "First doc",
                    "embedding": np.array([0.1, 0.2, 0.3]),
                    "metadata": {}
                },
                {
                    "text": "Second doc",
                    "embedding": np.array([0.1, 0.2]),  # Different dimension!
                    "metadata": {}
                }
            ]

            store = VectorStore(project_name="test_wiki")

            with pytest.raises(Exception, match="dimension mismatch"):
                store.add_documents(chunks)

    def test_chromadb_initialization_error(self):
        """VectorStore should handle ChromaDB initialization errors."""
        from src.processor.rag.vector_store import VectorStore

        with patch("chromadb.PersistentClient") as mock_client_class:
            mock_client_class.side_effect = Exception("Failed to initialize ChromaDB")

            with pytest.raises(Exception, match="Failed to initialize ChromaDB"):
                VectorStore(project_name="test_wiki")
