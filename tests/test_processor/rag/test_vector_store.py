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

    def test_init_with_project_name(self, tmp_path):
        """VectorStore should initialize with project name and create collection."""
        from src.processor.rag.vector_store import VectorStore

        with patch("chromadb.PersistentClient") as mock_client_class:
            mock_client = MagicMock()
            mock_collection = MagicMock()
            mock_client.get_or_create_collection.return_value = mock_collection
            mock_client_class.return_value = mock_client

            store = VectorStore(
                project_name="naruto_wiki",
                persist_directory=str(tmp_path)
            )

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

    def test_init_uses_config_default_path(self, tmp_path):
        """VectorStore should use config default path when no persist_directory provided."""
        from src.processor.rag.vector_store import VectorStore

        with patch("chromadb.PersistentClient") as mock_client_class:
            mock_client = MagicMock()
            mock_collection = MagicMock()
            mock_client.get_or_create_collection.return_value = mock_collection
            mock_client_class.return_value = mock_client

            # Mock config to return tmp_path
            with patch("src.processor.rag.vector_store.get_config") as mock_config:
                mock_config.return_value.vector_store_path = str(tmp_path)
                store = VectorStore(project_name="test_project")

            # Should use config path
            mock_client_class.assert_called_once()
            call_kwargs = mock_client_class.call_args[1]
            path_used = str(call_kwargs.get("path", ""))
            assert str(tmp_path) in path_used
            assert "test_project" in path_used

    def test_init_validates_project_name(self):
        """VectorStore should validate project name is not empty."""
        from src.processor.rag.vector_store import VectorStore

        with pytest.raises(ValueError, match="project_name cannot be empty"):
            VectorStore(project_name="")

        with pytest.raises(ValueError, match="project_name cannot be empty"):
            VectorStore(project_name="   ")

    def test_init_creates_persistent_client(self, tmp_path):
        """VectorStore should create PersistentClient for disk storage."""
        from src.processor.rag.vector_store import VectorStore

        with patch("chromadb.PersistentClient") as mock_client_class:
            mock_client = MagicMock()
            mock_collection = MagicMock()
            mock_client.get_or_create_collection.return_value = mock_collection
            mock_client_class.return_value = mock_client

            VectorStore(project_name="test_project", persist_directory=str(tmp_path))

            # Should use PersistentClient, not Client (ephemeral)
            mock_client_class.assert_called_once()


class TestVectorStoreDocumentAddition:
    """Test adding documents to vector store."""

    def test_add_documents_with_embeddings(self, tmp_path):
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

            store = VectorStore(project_name="avatar_wiki", persist_directory=str(tmp_path))
            doc_ids = store.add_documents(chunks)

            # Should add documents to collection
            mock_collection.add.assert_called_once()
            assert len(doc_ids) == 2
            assert all(isinstance(doc_id, str) for doc_id in doc_ids)

    def test_add_documents_generates_unique_ids(self, tmp_path):
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

            store = VectorStore(project_name="test_wiki", persist_directory=str(tmp_path))
            doc_ids = store.add_documents(chunks)

            # All IDs should be unique
            assert len(doc_ids) == len(set(doc_ids))

    def test_add_documents_preserves_metadata(self, tmp_path):
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

            store = VectorStore(project_name="test_wiki", persist_directory=str(tmp_path))
            store.add_documents(chunks)

            # Verify metadata was passed to ChromaDB
            call_kwargs = mock_collection.add.call_args[1]
            metadatas = call_kwargs.get("metadatas", [])
            assert len(metadatas) == 1
            assert metadatas[0]["url"] == "https://example.com"
            assert metadatas[0]["page_title"] == "Test Page"

    def test_add_documents_converts_numpy_to_list(self, tmp_path):
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

            store = VectorStore(project_name="test_wiki", persist_directory=str(tmp_path))
            store.add_documents(chunks)

            # ChromaDB expects lists, not numpy arrays
            call_kwargs = mock_collection.add.call_args[1]
            embeddings = call_kwargs.get("embeddings", [])
            assert isinstance(embeddings[0], list)

    def test_add_documents_validates_chunks_have_embeddings(self, tmp_path):
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

            store = VectorStore(project_name="test_wiki", persist_directory=str(tmp_path))

            with pytest.raises(ValueError, match="missing 'embedding' field"):
                store.add_documents(chunks)

    def test_add_documents_empty_list(self, tmp_path):
        """VectorStore should handle empty document list gracefully."""
        from src.processor.rag.vector_store import VectorStore

        with patch("chromadb.PersistentClient") as mock_client_class:
            mock_client = MagicMock()
            mock_collection = MagicMock()
            mock_client.get_or_create_collection.return_value = mock_collection
            mock_client_class.return_value = mock_client

            store = VectorStore(project_name="test_wiki", persist_directory=str(tmp_path))
            doc_ids = store.add_documents([])

            # Should return empty list without calling ChromaDB
            assert doc_ids == []
            mock_collection.add.assert_not_called()


class TestVectorStoreSimilaritySearch:
    """Test semantic similarity search functionality."""

    def test_similarity_search_basic(self, tmp_path):
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

            store = VectorStore(project_name="test_wiki", persist_directory=str(tmp_path))
            query_embedding = np.array([0.1, 0.2, 0.3])
            results = store.similarity_search(query_embedding, k=2)

            # Should return list of result dictionaries
            assert len(results) == 2
            assert results[0]["text"] == "Text 1"
            assert results[0]["metadata"]["url"] == "url1"
            assert "distance" in results[0]

    def test_similarity_search_with_k_parameter(self, tmp_path):
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

            store = VectorStore(project_name="test_wiki", persist_directory=str(tmp_path))
            query_embedding = np.array([0.1, 0.2, 0.3])
            store.similarity_search(query_embedding, k=5)

            # Should pass k to ChromaDB query
            call_kwargs = mock_collection.query.call_args[1]
            assert call_kwargs["n_results"] == 5

    def test_similarity_search_with_metadata_filter(self, tmp_path):
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

            store = VectorStore(project_name="test_wiki", persist_directory=str(tmp_path))
            query_embedding = np.array([0.1, 0.2, 0.3])

            # Filter to only character pages
            filter_dict = {"namespace": "Character"}
            results = store.similarity_search(query_embedding, k=5, metadata_filter=filter_dict)

            # Should pass filter to ChromaDB
            call_kwargs = mock_collection.query.call_args[1]
            assert call_kwargs.get("where") == filter_dict

    def test_similarity_search_converts_numpy_to_list(self, tmp_path):
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

            store = VectorStore(project_name="test_wiki", persist_directory=str(tmp_path))
            query_embedding = np.array([0.1, 0.2, 0.3])
            store.similarity_search(query_embedding)

            # Should convert numpy to list for ChromaDB
            call_kwargs = mock_collection.query.call_args[1]
            query_embeddings = call_kwargs["query_embeddings"]
            assert isinstance(query_embeddings[0], list)

    def test_similarity_search_no_results(self, tmp_path):
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

            store = VectorStore(project_name="test_wiki", persist_directory=str(tmp_path))
            query_embedding = np.array([0.1, 0.2, 0.3])
            results = store.similarity_search(query_embedding)

            assert results == []


class TestVectorStoreCollectionManagement:
    """Test collection management operations."""

    def test_get_collection_stats(self, tmp_path):
        """VectorStore should return collection statistics."""
        from src.processor.rag.vector_store import VectorStore

        with patch("chromadb.PersistentClient") as mock_client_class:
            mock_client = MagicMock()
            mock_collection = MagicMock()
            mock_collection.count.return_value = 42
            mock_collection.name = "test_wiki_collection"
            mock_client.get_or_create_collection.return_value = mock_collection
            mock_client_class.return_value = mock_client

            store = VectorStore(project_name="test_wiki", persist_directory=str(tmp_path))
            stats = store.get_collection_stats()

            assert stats["count"] == 42
            assert stats["name"] == "test_wiki_collection"

    def test_clear_collection(self, tmp_path):
        """VectorStore should clear all documents from collection."""
        from src.processor.rag.vector_store import VectorStore

        with patch("chromadb.PersistentClient") as mock_client_class:
            mock_client = MagicMock()
            mock_collection = MagicMock()
            mock_client.get_or_create_collection.return_value = mock_collection
            mock_client.delete_collection = MagicMock()
            mock_client_class.return_value = mock_client

            store = VectorStore(project_name="test_wiki", persist_directory=str(tmp_path))
            store.clear()

            # Should delete and recreate collection
            mock_client.delete_collection.assert_called_once()

    def test_has_documents_true(self, tmp_path):
        """VectorStore should detect if collection has documents."""
        from src.processor.rag.vector_store import VectorStore

        with patch("chromadb.PersistentClient") as mock_client_class:
            mock_client = MagicMock()
            mock_collection = MagicMock()
            mock_collection.count.return_value = 10
            mock_client.get_or_create_collection.return_value = mock_collection
            mock_client_class.return_value = mock_client

            store = VectorStore(project_name="test_wiki", persist_directory=str(tmp_path))

            assert store.has_documents() is True

    def test_has_documents_false_empty(self, tmp_path):
        """VectorStore should return False for empty collections."""
        from src.processor.rag.vector_store import VectorStore

        with patch("chromadb.PersistentClient") as mock_client_class:
            mock_client = MagicMock()
            mock_collection = MagicMock()
            mock_collection.count.return_value = 0
            mock_client.get_or_create_collection.return_value = mock_collection
            mock_client_class.return_value = mock_client

            store = VectorStore(project_name="test_wiki", persist_directory=str(tmp_path))

            assert store.has_documents() is False


class TestVectorStoreEdgeCases:
    """Test edge cases and error handling."""

    def test_add_documents_with_special_characters_in_metadata(self, tmp_path):
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

            store = VectorStore(project_name="test_wiki", persist_directory=str(tmp_path))
            doc_ids = store.add_documents(chunks)

            assert len(doc_ids) == 1
            mock_collection.add.assert_called_once()

    def test_similarity_search_with_zero_k(self, tmp_path):
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

            store = VectorStore(project_name="test_wiki", persist_directory=str(tmp_path))
            query_embedding = np.array([0.1, 0.2, 0.3])

            with pytest.raises(ValueError, match="k must be greater than 0"):
                store.similarity_search(query_embedding, k=0)

    def test_add_documents_with_mismatched_embedding_dimensions(self, tmp_path):
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

            store = VectorStore(project_name="test_wiki", persist_directory=str(tmp_path))

            with pytest.raises(Exception, match="dimension mismatch"):
                store.add_documents(chunks)

    def test_chromadb_initialization_error(self):
        """VectorStore should handle ChromaDB initialization errors."""
        from src.processor.rag.vector_store import VectorStore

        with patch("chromadb.PersistentClient") as mock_client_class:
            mock_client_class.side_effect = Exception("Failed to initialize ChromaDB")

            with pytest.raises(Exception, match="Failed to initialize ChromaDB"):
                VectorStore(project_name="test_wiki")


class TestVectorStoreSecurityValidation:
    """Test security vulnerabilities and input validation (path traversal, injection attacks)."""

    def test_path_traversal_attack_parent_directory(self):
        """VectorStore should reject path traversal attempts with ../"""
        from src.processor.rag.vector_store import VectorStore

        malicious_names = [
            "../etc/passwd",
            "../../sensitive",
            "../../../system",
            "normal/../../../etc",
        ]

        for name in malicious_names:
            with pytest.raises(ValueError, match="Invalid project_name.*Only alphanumeric"):
                VectorStore(project_name=name)

    def test_path_traversal_attack_absolute_paths(self):
        """VectorStore should reject absolute path attempts."""
        from src.processor.rag.vector_store import VectorStore

        malicious_names = [
            "/etc/passwd",
            "C:\\Windows\\System32",
            "\\\\network\\share",
        ]

        for name in malicious_names:
            with pytest.raises(ValueError, match="Invalid project_name.*Only alphanumeric"):
                VectorStore(project_name=name)

    def test_special_characters_in_project_name(self):
        """VectorStore should reject special characters in project names."""
        from src.processor.rag.vector_store import VectorStore

        invalid_names = [
            "test/wiki",  # forward slash
            "test\\wiki",  # backslash
            "test..",  # consecutive periods
            "test@wiki",  # at symbol
            "test wiki",  # space
            "test;rm -rf",  # semicolon (command injection attempt)
            "test$(whoami)",  # command substitution
            "test`whoami`",  # backticks
        ]

        for name in invalid_names:
            with pytest.raises(ValueError, match="Invalid project_name.*Only alphanumeric"):
                VectorStore(project_name=name)

    def test_project_name_too_short(self):
        """VectorStore should reject project names shorter than 3 characters."""
        from src.processor.rag.vector_store import VectorStore

        with pytest.raises(ValueError, match="must be at least 3 characters"):
            VectorStore(project_name="ab")

        with pytest.raises(ValueError, match="must be at least 3 characters"):
            VectorStore(project_name="x")

    def test_project_name_too_long(self):
        """VectorStore should reject project names longer than 255 characters."""
        from src.processor.rag.vector_store import VectorStore

        long_name = "a" * 256

        with pytest.raises(ValueError, match="too long.*max 255"):
            VectorStore(project_name=long_name)

    def test_invalid_embedding_type_string(self, tmp_path):
        """VectorStore should reject non-array embeddings (string)."""
        from src.processor.rag.vector_store import VectorStore

        with patch("chromadb.PersistentClient") as mock_client_class:
            mock_client = MagicMock()
            mock_collection = MagicMock()
            mock_client.get_or_create_collection.return_value = mock_collection
            mock_client_class.return_value = mock_client

            store = VectorStore(project_name="test_wiki", persist_directory=str(tmp_path))

            chunks = [
                {
                    "text": "test",
                    "embedding": "not an array!",  # Invalid type
                    "metadata": {}
                }
            ]

            with pytest.raises(ValueError, match="embedding must be numpy array or list"):
                store.add_documents(chunks)

    def test_invalid_embedding_type_dict(self, tmp_path):
        """VectorStore should reject non-array embeddings (dict)."""
        from src.processor.rag.vector_store import VectorStore

        with patch("chromadb.PersistentClient") as mock_client_class:
            mock_client = MagicMock()
            mock_collection = MagicMock()
            mock_client.get_or_create_collection.return_value = mock_collection
            mock_client_class.return_value = mock_client

            store = VectorStore(project_name="test_wiki", persist_directory=str(tmp_path))

            chunks = [
                {
                    "text": "test",
                    "embedding": {"dim1": 0.1, "dim2": 0.2},  # Dict instead of array
                    "metadata": {}
                }
            ]

            with pytest.raises(ValueError, match="embedding must be numpy array or list"):
                store.add_documents(chunks)

    def test_embedding_with_nan_values(self, tmp_path):
        """VectorStore should reject embeddings containing NaN."""
        from src.processor.rag.vector_store import VectorStore

        with patch("chromadb.PersistentClient") as mock_client_class:
            mock_client = MagicMock()
            mock_collection = MagicMock()
            mock_client.get_or_create_collection.return_value = mock_collection
            mock_client_class.return_value = mock_client

            store = VectorStore(project_name="test_wiki", persist_directory=str(tmp_path))

            chunks = [
                {
                    "text": "test",
                    "embedding": np.array([0.1, 0.2, float('nan')]),  # Contains NaN
                    "metadata": {}
                }
            ]

            with pytest.raises(ValueError, match="contains NaN or Inf"):
                store.add_documents(chunks)

    def test_embedding_with_inf_values(self, tmp_path):
        """VectorStore should reject embeddings containing Inf."""
        from src.processor.rag.vector_store import VectorStore

        with patch("chromadb.PersistentClient") as mock_client_class:
            mock_client = MagicMock()
            mock_collection = MagicMock()
            mock_client.get_or_create_collection.return_value = mock_collection
            mock_client_class.return_value = mock_client

            store = VectorStore(project_name="test_wiki", persist_directory=str(tmp_path))

            chunks = [
                {
                    "text": "test",
                    "embedding": np.array([0.1, float('inf'), 0.3]),  # Contains Inf
                    "metadata": {}
                }
            ]

            with pytest.raises(ValueError, match="contains NaN or Inf"):
                store.add_documents(chunks)

    def test_embedding_dimension_mismatch(self, tmp_path):
        """VectorStore should reject embeddings with inconsistent dimensions."""
        from src.processor.rag.vector_store import VectorStore

        with patch("chromadb.PersistentClient") as mock_client_class:
            mock_client = MagicMock()
            mock_collection = MagicMock()
            mock_client.get_or_create_collection.return_value = mock_collection
            mock_client_class.return_value = mock_client

            store = VectorStore(project_name="test_wiki", persist_directory=str(tmp_path))

            chunks = [
                {
                    "text": "First doc",
                    "embedding": np.array([0.1, 0.2, 0.3]),  # 3 dimensions
                    "metadata": {}
                },
                {
                    "text": "Second doc",
                    "embedding": np.array([0.1, 0.2, 0.3, 0.4]),  # 4 dimensions - mismatch!
                    "metadata": {}
                }
            ]

            with pytest.raises(ValueError, match="dimension mismatch.*Expected 3, got 4"):
                store.add_documents(chunks)

    def test_empty_embedding_array(self, tmp_path):
        """VectorStore should reject empty embeddings."""
        from src.processor.rag.vector_store import VectorStore

        with patch("chromadb.PersistentClient") as mock_client_class:
            mock_client = MagicMock()
            mock_collection = MagicMock()
            mock_client.get_or_create_collection.return_value = mock_collection
            mock_client_class.return_value = mock_client

            store = VectorStore(project_name="test_wiki", persist_directory=str(tmp_path))

            chunks = [
                {
                    "text": "test",
                    "embedding": np.array([]),  # Empty array
                    "metadata": {}
                }
            ]

            with pytest.raises(ValueError, match="embedding cannot be empty"):
                store.add_documents(chunks)

    def test_invalid_metadata_type_numpy_array(self, tmp_path):
        """VectorStore should reject numpy arrays in metadata."""
        from src.processor.rag.vector_store import VectorStore

        with patch("chromadb.PersistentClient") as mock_client_class:
            mock_client = MagicMock()
            mock_collection = MagicMock()
            mock_client.get_or_create_collection.return_value = mock_collection
            mock_client_class.return_value = mock_client

            store = VectorStore(project_name="test_wiki", persist_directory=str(tmp_path))

            chunks = [
                {
                    "text": "test",
                    "embedding": np.array([0.1, 0.2, 0.3]),
                    "metadata": {
                        "array_field": np.array([1, 2, 3])  # Not allowed!
                    }
                }
            ]

            with pytest.raises(ValueError, match="invalid type.*ndarray.*Only str, int, float, bool"):
                store.add_documents(chunks)

    def test_invalid_metadata_type_datetime(self, tmp_path):
        """VectorStore should reject datetime objects in metadata."""
        from src.processor.rag.vector_store import VectorStore
        from datetime import datetime

        with patch("chromadb.PersistentClient") as mock_client_class:
            mock_client = MagicMock()
            mock_collection = MagicMock()
            mock_client.get_or_create_collection.return_value = mock_collection
            mock_client_class.return_value = mock_client

            store = VectorStore(project_name="test_wiki", persist_directory=str(tmp_path))

            chunks = [
                {
                    "text": "test",
                    "embedding": np.array([0.1, 0.2, 0.3]),
                    "metadata": {
                        "timestamp": datetime.now()  # Not allowed!
                    }
                }
            ]

            with pytest.raises(ValueError, match="invalid type.*datetime.*Only str, int, float, bool"):
                store.add_documents(chunks)

    def test_valid_primitive_metadata_types(self, tmp_path):
        """VectorStore should accept valid primitive types in metadata."""
        from src.processor.rag.vector_store import VectorStore

        with patch("chromadb.PersistentClient") as mock_client_class:
            mock_client = MagicMock()
            mock_collection = MagicMock()
            mock_client.get_or_create_collection.return_value = mock_collection
            mock_client_class.return_value = mock_client

            store = VectorStore(project_name="test_wiki", persist_directory=str(tmp_path))

            # All primitive types should work
            chunks = [
                {
                    "text": "test",
                    "embedding": np.array([0.1, 0.2, 0.3]),
                    "metadata": {
                        "string_field": "value",
                        "int_field": 42,
                        "float_field": 3.14,
                        "bool_field": True,
                        "none_field": None
                    }
                }
            ]

            # Should not raise
            doc_ids = store.add_documents(chunks)
            assert len(doc_ids) == 1
