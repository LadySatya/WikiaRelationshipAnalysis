"""
Integration tests for VectorStore - tests with real ChromaDB (no mocks).

These tests verify end-to-end functionality with actual ChromaDB persistence,
embedding storage, and semantic similarity search. They are slower than unit
tests but provide high confidence in real-world behavior.
"""
import pytest
import numpy as np
import tempfile
import shutil
from pathlib import Path

from src.processor.rag.vector_store import VectorStore
from src.processor.rag.embeddings import EmbeddingGenerator


# Mark all tests in this file as integration tests
pytestmark = pytest.mark.integration


@pytest.fixture
def temp_vector_store_dir():
    """Create a temporary directory for vector store data."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    # Cleanup after test
    shutil.rmtree(temp_dir, ignore_errors=True)


class TestVectorStoreIntegrationBasic:
    """Test basic VectorStore operations with real ChromaDB."""

    def test_create_and_persist_vector_store(self, temp_vector_store_dir):
        """VectorStore should persist data to disk and reload it."""
        project_name = "test_integration_project"

        # Create store and add documents
        store1 = VectorStore(
            project_name=project_name,
            persist_directory=temp_vector_store_dir
        )

        chunks = [
            {
                "text": "Aang is the Avatar and last airbender",
                "embedding": np.random.rand(384).astype(np.float32),
                "metadata": {"url": "https://example.com/aang", "namespace": "Character"}
            },
            {
                "text": "Katara is a waterbender from the Southern Water Tribe",
                "embedding": np.random.rand(384).astype(np.float32),
                "metadata": {"url": "https://example.com/katara", "namespace": "Character"}
            }
        ]

        doc_ids = store1.add_documents(chunks)
        assert len(doc_ids) == 2

        # Create new store instance pointing to same directory
        store2 = VectorStore(
            project_name=project_name,
            persist_directory=temp_vector_store_dir
        )

        # Should have persisted data
        stats = store2.get_collection_stats()
        assert stats["count"] == 2

    def test_add_and_search_documents(self, temp_vector_store_dir):
        """VectorStore should add documents and retrieve them via similarity search."""
        store = VectorStore(
            project_name="test_search",
            persist_directory=temp_vector_store_dir
        )

        # Create embeddings that are similar
        base_embedding = np.array([0.5] * 384, dtype=np.float32)
        similar_embedding = base_embedding + np.random.rand(384).astype(np.float32) * 0.1

        chunks = [
            {
                "text": "Fire is hot and burns",
                "embedding": base_embedding,
                "metadata": {"topic": "fire"}
            },
            {
                "text": "Flames are a form of fire",
                "embedding": similar_embedding,
                "metadata": {"topic": "fire"}
            },
            {
                "text": "Water is cold and wet",
                "embedding": np.random.rand(384).astype(np.float32),
                "metadata": {"topic": "water"}
            }
        ]

        store.add_documents(chunks)

        # Search with base embedding should return similar documents
        results = store.similarity_search(base_embedding, k=2)

        assert len(results) == 2
        # First result should be exact match (distance ~0)
        assert results[0]["text"] == "Fire is hot and burns"
        assert results[0]["distance"] < 0.01  # Very close to 0

    def test_metadata_filtering(self, temp_vector_store_dir):
        """VectorStore should filter search results by metadata."""
        store = VectorStore(
            project_name="test_filtering",
            persist_directory=temp_vector_store_dir
        )

        chunks = [
            {
                "text": "Character page about Aang",
                "embedding": np.random.rand(384).astype(np.float32),
                "metadata": {"namespace": "Character", "url": "https://example.com/aang"}
            },
            {
                "text": "Location page about Ba Sing Se",
                "embedding": np.random.rand(384).astype(np.float32),
                "metadata": {"namespace": "Location", "url": "https://example.com/ba_sing_se"}
            },
            {
                "text": "Character page about Katara",
                "embedding": np.random.rand(384).astype(np.float32),
                "metadata": {"namespace": "Character", "url": "https://example.com/katara"}
            }
        ]

        store.add_documents(chunks)

        # Search with namespace filter
        query_embedding = np.random.rand(384).astype(np.float32)
        results = store.similarity_search(
            query_embedding,
            k=10,
            filter={"namespace": "Character"}
        )

        # Should only return Character pages
        assert len(results) == 2
        assert all(r["metadata"]["namespace"] == "Character" for r in results)

    def test_clear_collection(self, temp_vector_store_dir):
        """VectorStore should clear all documents from collection."""
        store = VectorStore(
            project_name="test_clear",
            persist_directory=temp_vector_store_dir
        )

        # Add documents
        chunks = [
            {
                "text": f"Document {i}",
                "embedding": np.random.rand(384).astype(np.float32),
                "metadata": {"index": i}
            }
            for i in range(5)
        ]

        store.add_documents(chunks)
        assert store.collection_exists() is True
        assert store.get_collection_stats()["count"] == 5

        # Clear collection
        store.clear()
        assert store.collection_exists() is False
        assert store.get_collection_stats()["count"] == 0


class TestVectorStoreIntegrationWithEmbeddings:
    """Test VectorStore integration with EmbeddingGenerator."""

    def test_end_to_end_embedding_and_storage(self, temp_vector_store_dir):
        """Test complete pipeline: chunk text → embed → store → search."""
        # Initialize components
        generator = EmbeddingGenerator(provider="local")
        store = VectorStore(
            project_name="test_pipeline",
            persist_directory=temp_vector_store_dir
        )

        # Create text chunks
        raw_chunks = [
            {
                "text": "The Avatar is the bridge between the spirit world and human world.",
                "metadata": {"source": "Avatar Lore", "chunk_index": 0}
            },
            {
                "text": "Waterbending is the art of manipulating water.",
                "metadata": {"source": "Bending Arts", "chunk_index": 0}
            },
            {
                "text": "The Fire Nation attacked and started the war.",
                "metadata": {"source": "History", "chunk_index": 0}
            }
        ]

        # Generate embeddings
        embedded_chunks = generator.embed_chunks(raw_chunks)

        # Store in vector database
        doc_ids = store.add_documents(embedded_chunks)
        assert len(doc_ids) == 3

        # Query with new text
        query_text = "Tell me about the Avatar"
        query_embedding = generator.generate_embedding(query_text)

        # Search for similar documents
        results = store.similarity_search(query_embedding, k=2)

        assert len(results) == 2
        # First result should be about Avatar (most semantically similar)
        assert "Avatar" in results[0]["text"]
        assert results[0]["metadata"]["source"] == "Avatar Lore"

    def test_multiple_projects_isolated(self, temp_vector_store_dir):
        """VectorStore should isolate different projects in separate collections."""
        # Create two separate projects
        store_naruto = VectorStore(
            project_name="naruto_wiki",
            persist_directory=temp_vector_store_dir
        )

        store_avatar = VectorStore(
            project_name="avatar_wiki",
            persist_directory=temp_vector_store_dir
        )

        # Add different documents to each
        naruto_chunks = [
            {
                "text": "Naruto Uzumaki is a ninja",
                "embedding": np.random.rand(384).astype(np.float32),
                "metadata": {"series": "Naruto"}
            }
        ]

        avatar_chunks = [
            {
                "text": "Aang is the Avatar",
                "embedding": np.random.rand(384).astype(np.float32),
                "metadata": {"series": "Avatar"}
            }
        ]

        store_naruto.add_documents(naruto_chunks)
        store_avatar.add_documents(avatar_chunks)

        # Each should only see its own documents
        assert store_naruto.get_collection_stats()["count"] == 1
        assert store_avatar.get_collection_stats()["count"] == 1

        # Search in naruto should only return naruto docs
        results = store_naruto.similarity_search(
            np.random.rand(384).astype(np.float32),
            k=10
        )
        assert len(results) == 1
        assert "Naruto" in results[0]["text"]


class TestVectorStoreIntegrationEdgeCases:
    """Test edge cases with real ChromaDB."""

    def test_large_batch_addition(self, temp_vector_store_dir):
        """VectorStore should handle large batches of documents efficiently."""
        store = VectorStore(
            project_name="test_large_batch",
            persist_directory=temp_vector_store_dir
        )

        # Create 100 documents
        chunks = [
            {
                "text": f"Document number {i} with some content",
                "embedding": np.random.rand(384).astype(np.float32),
                "metadata": {"index": i, "batch": "large"}
            }
            for i in range(100)
        ]

        doc_ids = store.add_documents(chunks)

        assert len(doc_ids) == 100
        assert len(set(doc_ids)) == 100  # All unique
        assert store.get_collection_stats()["count"] == 100

    def test_unicode_and_special_characters(self, temp_vector_store_dir):
        """VectorStore should handle Unicode and special characters correctly."""
        store = VectorStore(
            project_name="test_unicode",
            persist_directory=temp_vector_store_dir
        )

        chunks = [
            {
                "text": "Aang uses 气 (air) bending. The Avatar controls 水火土气.",
                "embedding": np.random.rand(384).astype(np.float32),
                "metadata": {
                    "title": "Avatar™: The Last Airbender®",
                    "url": "https://example.com/氣"
                }
            }
        ]

        doc_ids = store.add_documents(chunks)
        assert len(doc_ids) == 1

        # Should be able to retrieve and preserve Unicode
        results = store.similarity_search(
            np.random.rand(384).astype(np.float32),
            k=1
        )

        assert len(results) == 1
        assert "氣" in results[0]["metadata"]["url"] or "气" in results[0]["text"]

    def test_empty_collection_search(self, temp_vector_store_dir):
        """VectorStore should handle search on empty collection gracefully."""
        store = VectorStore(
            project_name="test_empty",
            persist_directory=temp_vector_store_dir
        )

        # Search on empty collection
        results = store.similarity_search(
            np.random.rand(384).astype(np.float32),
            k=10
        )

        assert results == []
        assert store.collection_exists() is False
