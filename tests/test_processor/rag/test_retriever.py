"""
Tests for RAGRetriever - semantic search for RAG queries.

Following TDD methodology: write tests first, then implement.
This module tests the RAGRetriever class which handles:
- Semantic search using embeddings
- Integration with VectorStore and EmbeddingGenerator
- Metadata filtering and result ranking
- Context retrieval for LLM queries
"""
import pytest
import numpy as np
from unittest.mock import Mock, MagicMock, patch


# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit


class TestRAGRetrieverInitialization:
    """Test RAGRetriever initialization."""

    def test_init_with_project_name(self):
        """RAGRetriever should initialize with project name."""
        from src.processor.rag.retriever import RAGRetriever

        with patch("src.processor.rag.retriever.VectorStore"), \
             patch("src.processor.rag.retriever.EmbeddingGenerator"):

            retriever = RAGRetriever(project_name="naruto_wiki")

            assert retriever.project_name == "naruto_wiki"

    def test_init_creates_vector_store(self):
        """RAGRetriever should create VectorStore for project."""
        from src.processor.rag.retriever import RAGRetriever

        with patch("src.processor.rag.retriever.VectorStore") as mock_vs_class, \
             patch("src.processor.rag.retriever.EmbeddingGenerator"):

            retriever = RAGRetriever(project_name="test_wiki")

            # Should create VectorStore with project name
            mock_vs_class.assert_called_once_with(project_name="test_wiki")

    def test_init_creates_embedding_generator(self):
        """RAGRetriever should create EmbeddingGenerator."""
        from src.processor.rag.retriever import RAGRetriever

        with patch("src.processor.rag.retriever.VectorStore"), \
             patch("src.processor.rag.retriever.EmbeddingGenerator") as mock_eg_class:

            retriever = RAGRetriever(project_name="test_wiki")

            # Should create EmbeddingGenerator
            mock_eg_class.assert_called_once()


class TestRAGRetrieverSearch:
    """Test semantic search functionality."""

    def test_retrieve_basic_query(self):
        """RAGRetriever should retrieve relevant chunks for query."""
        from src.processor.rag.retriever import RAGRetriever

        with patch("src.processor.rag.retriever.VectorStore") as mock_vs_class, \
             patch("src.processor.rag.retriever.EmbeddingGenerator") as mock_eg_class:

            # Mock embedding generator
            mock_eg = MagicMock()
            mock_eg.generate_embedding.return_value = np.array([0.1, 0.2, 0.3])
            mock_eg_class.return_value = mock_eg

            # Mock vector store
            mock_vs = MagicMock()
            mock_vs.similarity_search.return_value = [
                {
                    "id": "doc1",
                    "text": "Naruto is a ninja",
                    "metadata": {"url": "https://example.com/naruto"},
                    "distance": 0.1
                }
            ]
            mock_vs_class.return_value = mock_vs

            retriever = RAGRetriever(project_name="test_wiki")
            results = retriever.retrieve("Who is Naruto?")

            # Should generate embedding from query
            mock_eg.generate_embedding.assert_called_once_with("Who is Naruto?")

            # Should search vector store
            mock_vs.similarity_search.assert_called_once()

            # Should return results
            assert len(results) == 1
            assert results[0]["text"] == "Naruto is a ninja"

    def test_retrieve_with_custom_k(self):
        """RAGRetriever should support custom k parameter."""
        from src.processor.rag.retriever import RAGRetriever

        with patch("src.processor.rag.retriever.VectorStore") as mock_vs_class, \
             patch("src.processor.rag.retriever.EmbeddingGenerator") as mock_eg_class:

            mock_eg = MagicMock()
            mock_eg.generate_embedding.return_value = np.array([0.1, 0.2, 0.3])
            mock_eg_class.return_value = mock_eg

            mock_vs = MagicMock()
            mock_vs.similarity_search.return_value = []
            mock_vs_class.return_value = mock_vs

            retriever = RAGRetriever(project_name="test_wiki")
            retriever.retrieve("Test query", k=20)

            # Should pass k to vector store
            call_kwargs = mock_vs.similarity_search.call_args[1]
            assert call_kwargs["k"] == 20

    def test_retrieve_with_metadata_filter(self):
        """RAGRetriever should support metadata filtering."""
        from src.processor.rag.retriever import RAGRetriever

        with patch("src.processor.rag.retriever.VectorStore") as mock_vs_class, \
             patch("src.processor.rag.retriever.EmbeddingGenerator") as mock_eg_class:

            mock_eg = MagicMock()
            mock_eg.generate_embedding.return_value = np.array([0.1, 0.2, 0.3])
            mock_eg_class.return_value = mock_eg

            mock_vs = MagicMock()
            mock_vs.similarity_search.return_value = []
            mock_vs_class.return_value = mock_vs

            retriever = RAGRetriever(project_name="test_wiki")
            filter_dict = {"namespace": "Character"}
            retriever.retrieve("Test query", metadata_filter=filter_dict)

            # Should pass filter to vector store
            call_kwargs = mock_vs.similarity_search.call_args[1]
            assert call_kwargs["metadata_filter"] == filter_dict

    def test_retrieve_formats_results(self):
        """RAGRetriever should format results with chunks and metadata."""
        from src.processor.rag.retriever import RAGRetriever

        with patch("src.processor.rag.retriever.VectorStore") as mock_vs_class, \
             patch("src.processor.rag.retriever.EmbeddingGenerator") as mock_eg_class:

            mock_eg = MagicMock()
            mock_eg.generate_embedding.return_value = np.array([0.1, 0.2, 0.3])
            mock_eg_class.return_value = mock_eg

            mock_vs = MagicMock()
            mock_vs.similarity_search.return_value = [
                {
                    "id": "chunk1",
                    "text": "Aang is the Avatar",
                    "metadata": {
                        "url": "https://example.com/aang",
                        "chunk_index": 0,
                        "page_title": "Aang"
                    },
                    "distance": 0.05
                },
                {
                    "id": "chunk2",
                    "text": "Katara is a waterbender",
                    "metadata": {
                        "url": "https://example.com/katara",
                        "chunk_index": 1,
                        "page_title": "Katara"
                    },
                    "distance": 0.10
                }
            ]
            mock_vs_class.return_value = mock_vs

            retriever = RAGRetriever(project_name="test_wiki")
            results = retriever.retrieve("Who is Aang?")

            # Should have 2 results
            assert len(results) == 2

            # Should preserve all fields
            assert results[0]["text"] == "Aang is the Avatar"
            assert results[0]["metadata"]["page_title"] == "Aang"
            assert results[0]["distance"] == 0.05


class TestRAGRetrieverContextBuilding:
    """Test building context for LLM queries."""

    def test_build_context_from_chunks(self):
        """RAGRetriever should build formatted context from retrieved chunks."""
        from src.processor.rag.retriever import RAGRetriever

        with patch("src.processor.rag.retriever.VectorStore"), \
             patch("src.processor.rag.retriever.EmbeddingGenerator"):

            retriever = RAGRetriever(project_name="test_wiki")

            chunks = [
                {
                    "id": "chunk1",
                    "text": "Aang is the Avatar and last airbender.",
                    "metadata": {"url": "https://example.com/aang", "chunk_index": 0},
                    "distance": 0.05
                },
                {
                    "id": "chunk2",
                    "text": "He was found frozen in an iceberg.",
                    "metadata": {"url": "https://example.com/aang", "chunk_index": 1},
                    "distance": 0.08
                }
            ]

            context = retriever.build_context(chunks)

            # Should format as text with sources
            assert isinstance(context, str)
            assert "Aang is the Avatar" in context
            assert "frozen in an iceberg" in context

    def test_build_context_includes_sources(self):
        """RAGRetriever should include source URLs in context."""
        from src.processor.rag.retriever import RAGRetriever

        with patch("src.processor.rag.retriever.VectorStore"), \
             patch("src.processor.rag.retriever.EmbeddingGenerator"):

            retriever = RAGRetriever(project_name="test_wiki")

            chunks = [
                {
                    "id": "chunk1",
                    "text": "Test content",
                    "metadata": {"url": "https://example.com/page1"},
                    "distance": 0.1
                }
            ]

            context = retriever.build_context(chunks)

            # Should include source URL
            assert "https://example.com/page1" in context or "Source" in context


class TestRAGRetrieverEdgeCases:
    """Test edge cases and error handling."""

    def test_retrieve_empty_query(self):
        """RAGRetriever should handle empty queries."""
        from src.processor.rag.retriever import RAGRetriever

        with patch("src.processor.rag.retriever.VectorStore"), \
             patch("src.processor.rag.retriever.EmbeddingGenerator"):

            retriever = RAGRetriever(project_name="test_wiki")

            with pytest.raises(ValueError, match="query cannot be empty"):
                retriever.retrieve("")

    def test_retrieve_no_results(self):
        """RAGRetriever should handle no results gracefully."""
        from src.processor.rag.retriever import RAGRetriever

        with patch("src.processor.rag.retriever.VectorStore") as mock_vs_class, \
             patch("src.processor.rag.retriever.EmbeddingGenerator") as mock_eg_class:

            mock_eg = MagicMock()
            mock_eg.generate_embedding.return_value = np.array([0.1, 0.2, 0.3])
            mock_eg_class.return_value = mock_eg

            mock_vs = MagicMock()
            mock_vs.similarity_search.return_value = []
            mock_vs_class.return_value = mock_vs

            retriever = RAGRetriever(project_name="test_wiki")
            results = retriever.retrieve("Unknown topic")

            assert results == []

    def test_build_context_empty_chunks(self):
        """RAGRetriever should handle empty chunk list."""
        from src.processor.rag.retriever import RAGRetriever

        with patch("src.processor.rag.retriever.VectorStore"), \
             patch("src.processor.rag.retriever.EmbeddingGenerator"):

            retriever = RAGRetriever(project_name="test_wiki")
            context = retriever.build_context([])

            # Should return empty or minimal context
            assert context is not None
            assert isinstance(context, str)
