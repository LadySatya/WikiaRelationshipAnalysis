"""
Tests for LLMClient - Claude API wrapper for RAG queries.

Following TDD methodology: write tests first, then implement.
This module tests the LLMClient class which handles:
- Claude API integration for text generation
- Token counting and cost estimation
- Error handling and retries
- System prompts and context management
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any


# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit


class TestLLMClientInitialization:
    """Test LLMClient initialization and configuration."""

    def test_init_with_anthropic_provider(self):
        """LLMClient should initialize with Anthropic provider."""
        from src.processor.llm.llm_client import LLMClient

        client = LLMClient(provider="anthropic", model="claude-3-5-haiku-20241022")

        assert client.provider == "anthropic"
        assert client.model == "claude-3-5-haiku-20241022"

    def test_init_with_default_config(self):
        """LLMClient should use config defaults when no parameters provided."""
        from src.processor.llm.llm_client import LLMClient

        client = LLMClient()

        # Should default to anthropic and haiku from config
        assert client.provider == "anthropic"
        assert client.model == "claude-3-5-haiku-20241022"

    def test_init_validates_provider(self):
        """LLMClient should validate provider is supported."""
        from src.processor.llm.llm_client import LLMClient

        with pytest.raises(ValueError, match="provider must be one of"):
            LLMClient(provider="invalid")

    def test_init_reads_api_key_from_env(self):
        """LLMClient should read ANTHROPIC_API_KEY from environment."""
        from src.processor.llm.llm_client import LLMClient

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key-123"}):
            client = LLMClient(provider="anthropic")
            assert client.api_key == "test-key-123"

    def test_init_accepts_api_key_parameter(self):
        """LLMClient should accept API key as parameter."""
        from src.processor.llm.llm_client import LLMClient

        client = LLMClient(provider="anthropic", api_key="custom-key")
        assert client.api_key == "custom-key"

    def test_init_lazy_loading_of_client(self):
        """LLMClient should not initialize Anthropic client until first use."""
        from src.processor.llm.llm_client import LLMClient

        client = LLMClient(provider="anthropic")

        # Client should be None until first API call (lazy loading)
        assert client._client is None


class TestLLMClientTextGeneration:
    """Test text generation with Claude API."""

    def test_generate_simple_prompt(self):
        """LLMClient should generate text from simple prompt."""
        from src.processor.llm.llm_client import LLMClient

        with patch("anthropic.Anthropic") as mock_anthropic_class:
            # Mock Anthropic client
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="Generated response")]
            mock_response.usage = MagicMock(input_tokens=10, output_tokens=5)
            mock_client.messages.create.return_value = mock_response
            mock_anthropic_class.return_value = mock_client

            client = LLMClient(provider="anthropic")
            response = client.generate("What is the capital of France?")

            assert response == "Generated response"
            mock_client.messages.create.assert_called_once()

    def test_generate_with_system_prompt(self):
        """LLMClient should support system prompts for context."""
        from src.processor.llm.llm_client import LLMClient

        with patch("anthropic.Anthropic") as mock_anthropic_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="Response")]
            mock_response.usage = MagicMock(input_tokens=20, output_tokens=10)
            mock_client.messages.create.return_value = mock_response
            mock_anthropic_class.return_value = mock_client

            client = LLMClient(provider="anthropic")
            response = client.generate(
                prompt="Who is Aang?",
                system_prompt="You are a helpful assistant analyzing Avatar: The Last Airbender wiki."
            )

            # Should pass system prompt to API
            call_kwargs = mock_client.messages.create.call_args[1]
            assert call_kwargs["system"] == "You are a helpful assistant analyzing Avatar: The Last Airbender wiki."

    def test_generate_with_temperature(self):
        """LLMClient should support custom temperature setting."""
        from src.processor.llm.llm_client import LLMClient

        with patch("anthropic.Anthropic") as mock_anthropic_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="Response")]
            mock_response.usage = MagicMock(input_tokens=10, output_tokens=5)
            mock_client.messages.create.return_value = mock_response
            mock_anthropic_class.return_value = mock_client

            client = LLMClient(provider="anthropic")
            client.generate("Test", temperature=0.3)

            call_kwargs = mock_client.messages.create.call_args[1]
            assert call_kwargs["temperature"] == 0.3

    def test_generate_with_max_tokens(self):
        """LLMClient should support custom max_tokens setting."""
        from src.processor.llm.llm_client import LLMClient

        with patch("anthropic.Anthropic") as mock_anthropic_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="Response")]
            mock_response.usage = MagicMock(input_tokens=10, output_tokens=5)
            mock_client.messages.create.return_value = mock_response
            mock_anthropic_class.return_value = mock_client

            client = LLMClient(provider="anthropic")
            client.generate("Test", max_tokens=2048)

            call_kwargs = mock_client.messages.create.call_args[1]
            assert call_kwargs["max_tokens"] == 2048

    def test_generate_tracks_token_usage(self):
        """LLMClient should track input and output tokens."""
        from src.processor.llm.llm_client import LLMClient

        with patch("anthropic.Anthropic") as mock_anthropic_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="Response")]
            mock_response.usage = MagicMock(input_tokens=100, output_tokens=50)
            mock_client.messages.create.return_value = mock_response
            mock_anthropic_class.return_value = mock_client

            client = LLMClient(provider="anthropic")
            response = client.generate("Test prompt")

            # Should track tokens
            assert client.total_input_tokens == 100
            assert client.total_output_tokens == 50

    def test_generate_accumulates_token_usage(self):
        """LLMClient should accumulate token usage across multiple calls."""
        from src.processor.llm.llm_client import LLMClient

        with patch("anthropic.Anthropic") as mock_anthropic_class:
            mock_client = MagicMock()
            mock_client.messages.create.side_effect = [
                MagicMock(
                    content=[MagicMock(text="Response 1")],
                    usage=MagicMock(input_tokens=100, output_tokens=50)
                ),
                MagicMock(
                    content=[MagicMock(text="Response 2")],
                    usage=MagicMock(input_tokens=200, output_tokens=75)
                ),
            ]
            mock_anthropic_class.return_value = mock_client

            client = LLMClient(provider="anthropic")
            client.generate("First call")
            client.generate("Second call")

            # Should accumulate across calls
            assert client.total_input_tokens == 300
            assert client.total_output_tokens == 125


class TestLLMClientErrorHandling:
    """Test error handling and edge cases."""

    def test_generate_handles_api_error(self):
        """LLMClient should handle Anthropic API errors gracefully."""
        from src.processor.llm.llm_client import LLMClient

        with patch("anthropic.Anthropic") as mock_anthropic_class:
            mock_client = MagicMock()
            mock_client.messages.create.side_effect = Exception("API Error: Rate limit exceeded")
            mock_anthropic_class.return_value = mock_client

            client = LLMClient(provider="anthropic")

            with pytest.raises(Exception, match="API Error"):
                client.generate("Test")

    def test_generate_validates_empty_prompt(self):
        """LLMClient should validate prompt is not empty."""
        from src.processor.llm.llm_client import LLMClient

        client = LLMClient(provider="anthropic")

        with pytest.raises(ValueError, match="prompt cannot be empty"):
            client.generate("")

        with pytest.raises(ValueError, match="prompt cannot be empty"):
            client.generate("   ")

    def test_generate_validates_temperature_range(self):
        """LLMClient should validate temperature is in valid range."""
        from src.processor.llm.llm_client import LLMClient

        client = LLMClient(provider="anthropic")

        with pytest.raises(ValueError, match="temperature must be between 0 and 1"):
            client.generate("Test", temperature=1.5)

        with pytest.raises(ValueError, match="temperature must be between 0 and 1"):
            client.generate("Test", temperature=-0.1)

    def test_generate_validates_max_tokens(self):
        """LLMClient should validate max_tokens is positive."""
        from src.processor.llm.llm_client import LLMClient

        client = LLMClient(provider="anthropic")

        with pytest.raises(ValueError, match="max_tokens must be positive"):
            client.generate("Test", max_tokens=0)

        with pytest.raises(ValueError, match="max_tokens must be positive"):
            client.generate("Test", max_tokens=-10)


class TestLLMClientCostTracking:
    """Test token counting and cost estimation."""

    def test_get_usage_stats(self):
        """LLMClient should return usage statistics."""
        from src.processor.llm.llm_client import LLMClient

        with patch("anthropic.Anthropic") as mock_anthropic_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="Response")]
            mock_response.usage = MagicMock(input_tokens=1000, output_tokens=500)
            mock_client.messages.create.return_value = mock_response
            mock_anthropic_class.return_value = mock_client

            client = LLMClient(provider="anthropic", model="claude-3-5-haiku-20241022")
            client.generate("Test")

            stats = client.get_usage_stats()

            assert stats["total_input_tokens"] == 1000
            assert stats["total_output_tokens"] == 500
            assert stats["total_tokens"] == 1500
            assert "estimated_cost_usd" in stats
            assert stats["model"] == "claude-3-5-haiku-20241022"

    def test_estimate_cost_for_haiku(self):
        """LLMClient should estimate cost correctly for Claude 3.5 Haiku."""
        from src.processor.llm.llm_client import LLMClient

        client = LLMClient(provider="anthropic", model="claude-3-5-haiku-20241022")

        # Haiku pricing: $1/1M input tokens, $5/1M output tokens
        cost = client.estimate_cost(input_tokens=1_000_000, output_tokens=1_000_000)

        assert cost == pytest.approx(6.0, rel=0.01)  # $1 + $5 = $6

    def test_reset_usage_stats(self):
        """LLMClient should support resetting usage statistics."""
        from src.processor.llm.llm_client import LLMClient

        with patch("anthropic.Anthropic") as mock_anthropic_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="Response")]
            mock_response.usage = MagicMock(input_tokens=100, output_tokens=50)
            mock_client.messages.create.return_value = mock_response
            mock_anthropic_class.return_value = mock_client

            client = LLMClient(provider="anthropic")
            client.generate("Test")

            assert client.total_input_tokens == 100
            assert client.total_output_tokens == 50

            client.reset_usage_stats()

            assert client.total_input_tokens == 0
            assert client.total_output_tokens == 0


class TestLLMClientWithContext:
    """Test multi-turn conversations with context."""

    def test_generate_with_context_list(self):
        """LLMClient should support providing context as list of messages."""
        from src.processor.llm.llm_client import LLMClient

        with patch("anthropic.Anthropic") as mock_anthropic_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="Response")]
            mock_response.usage = MagicMock(input_tokens=50, output_tokens=25)
            mock_client.messages.create.return_value = mock_response
            mock_anthropic_class.return_value = mock_client

            client = LLMClient(provider="anthropic")

            # Provide context from previous conversation
            context = [
                {"role": "user", "content": "What is retrieval augmented generation?"},
                {"role": "assistant", "content": "RAG is a technique that combines retrieval with LLMs..."}
            ]

            response = client.generate(
                prompt="Can you give me an example?",
                context=context
            )

            # Should include context in API call
            call_kwargs = mock_client.messages.create.call_args[1]
            messages = call_kwargs["messages"]

            # Should have 3 messages: context[0], context[1], new prompt
            assert len(messages) == 3
            assert messages[0]["content"] == "What is retrieval augmented generation?"
            assert messages[2]["content"] == "Can you give me an example?"


class TestLLMClientWithCitations:
    """Test citation support for evidence tracking."""

    def test_query_with_citations_builds_document_blocks(self):
        """LLMClient should build document blocks with citations enabled."""
        from src.processor.llm.llm_client import LLMClient

        with patch("anthropic.Anthropic") as mock_anthropic_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_content = MagicMock()
            mock_content.type = "text"
            mock_content.text = "Aang is the Avatar"
            mock_content.citations = []
            mock_response.content = [mock_content]
            mock_response.usage = MagicMock(input_tokens=100, output_tokens=50)
            mock_client.messages.create.return_value = mock_response
            mock_anthropic_class.return_value = mock_client

            client = LLMClient(provider="anthropic")

            documents = ["Document 1 content", "Document 2 content"]
            metadata = [
                {"source_url": "wiki/page1", "page_title": "Page 1"},
                {"source_url": "wiki/page2", "page_title": "Page 2"}
            ]

            result = client.query_with_citations("Who is Aang?", documents, metadata)

            # Should call API with document blocks
            call_kwargs = mock_client.messages.create.call_args[1]
            messages = call_kwargs["messages"]

            # Should have 1 message with multiple content blocks
            assert len(messages) == 1
            content_blocks = messages[0]["content"]

            # Should have 2 documents + 1 text query = 3 blocks
            assert len(content_blocks) == 3

            # First two should be document blocks
            assert content_blocks[0]["type"] == "document"
            assert content_blocks[0]["source"]["data"] == "Document 1 content"
            assert content_blocks[0]["citations"]["enabled"] is True

            assert content_blocks[1]["type"] == "document"
            assert content_blocks[1]["source"]["data"] == "Document 2 content"
            assert content_blocks[1]["citations"]["enabled"] is True

            # Last should be text query
            assert content_blocks[2]["type"] == "text"
            assert content_blocks[2]["text"] == "Who is Aang?"

    def test_query_with_citations_extracts_text_response(self):
        """LLMClient should extract text from citation-enabled response."""
        from src.processor.llm.llm_client import LLMClient

        with patch("anthropic.Anthropic") as mock_anthropic_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_content = MagicMock()
            mock_content.type = "text"
            mock_content.text = "Aang is the last Airbender and Avatar"
            mock_content.citations = []
            mock_response.content = [mock_content]
            mock_response.usage = MagicMock(input_tokens=100, output_tokens=50)
            mock_client.messages.create.return_value = mock_response
            mock_anthropic_class.return_value = mock_client

            client = LLMClient(provider="anthropic")

            result = client.query_with_citations(
                "Who is Aang?",
                ["Document content"],
                [{"source_url": "wiki/aang", "page_title": "Aang"}]
            )

            assert result["text"] == "Aang is the last Airbender and Avatar"
            assert "evidence" in result
            assert isinstance(result["evidence"], list)

    def test_query_with_citations_extracts_citation_evidence(self):
        """LLMClient should extract citations and map to source metadata."""
        from src.processor.llm.llm_client import LLMClient

        with patch("anthropic.Anthropic") as mock_anthropic_class:
            mock_client = MagicMock()
            mock_response = MagicMock()

            # Mock citation objects
            citation1 = MagicMock()
            citation1.document_index = 0
            citation1.cited_text = "Aang is the last Airbender"
            citation1.location = {"start": 0, "end": 27}

            citation2 = MagicMock()
            citation2.document_index = 1
            citation2.cited_text = "He is a master of all four elements"
            citation2.location = {"start": 50, "end": 85}

            mock_content = MagicMock()
            mock_content.type = "text"
            mock_content.text = "Aang is the last Airbender and a master of all elements"
            mock_content.citations = [citation1, citation2]

            mock_response.content = [mock_content]
            mock_response.usage = MagicMock(input_tokens=150, output_tokens=75)
            mock_client.messages.create.return_value = mock_response
            mock_anthropic_class.return_value = mock_client

            client = LLMClient(provider="anthropic")

            documents = ["Document 1", "Document 2"]
            metadata = [
                {"source_url": "wiki/aang", "page_title": "Aang", "chunk_id": "chunk1"},
                {"source_url": "wiki/avatar", "page_title": "Avatar", "chunk_id": "chunk2"}
            ]

            result = client.query_with_citations("Who is Aang?", documents, metadata)

            # Should extract and map citations
            assert len(result["evidence"]) == 2

            # First citation
            assert result["evidence"][0]["cited_text"] == "Aang is the last Airbender"
            assert result["evidence"][0]["source_url"] == "wiki/aang"
            assert result["evidence"][0]["page_title"] == "Aang"
            assert result["evidence"][0]["chunk_id"] == "chunk1"
            assert result["evidence"][0]["document_index"] == 0
            assert result["evidence"][0]["location"] == {"start": 0, "end": 27}

            # Second citation
            assert result["evidence"][1]["cited_text"] == "He is a master of all four elements"
            assert result["evidence"][1]["source_url"] == "wiki/avatar"
            assert result["evidence"][1]["page_title"] == "Avatar"
            assert result["evidence"][1]["chunk_id"] == "chunk2"

    def test_query_with_citations_handles_no_citations(self):
        """LLMClient should handle responses with no citations gracefully."""
        from src.processor.llm.llm_client import LLMClient

        with patch("anthropic.Anthropic") as mock_anthropic_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_content = MagicMock()
            mock_content.type = "text"
            mock_content.text = "No specific information found"
            # No citations attribute
            mock_response.content = [mock_content]
            mock_response.usage = MagicMock(input_tokens=50, output_tokens=20)
            mock_client.messages.create.return_value = mock_response
            mock_anthropic_class.return_value = mock_client

            client = LLMClient(provider="anthropic")

            result = client.query_with_citations(
                "Who is Unknown Character?",
                ["Document"],
                [{"source_url": "wiki/unknown", "page_title": "Unknown"}]
            )

            assert result["text"] == "No specific information found"
            assert result["evidence"] == []

    def test_query_with_citations_tracks_token_usage(self):
        """LLMClient should track token usage for citation queries."""
        from src.processor.llm.llm_client import LLMClient

        with patch("anthropic.Anthropic") as mock_anthropic_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_content = MagicMock()
            mock_content.type = "text"
            mock_content.text = "Response"
            mock_content.citations = []
            mock_response.content = [mock_content]
            mock_response.usage = MagicMock(input_tokens=500, output_tokens=100)
            mock_client.messages.create.return_value = mock_response
            mock_anthropic_class.return_value = mock_client

            client = LLMClient(provider="anthropic")

            client.query_with_citations(
                "Query",
                ["Document"],
                [{"source_url": "wiki/page"}]
            )

            # Should track tokens
            assert client.total_input_tokens == 500
            assert client.total_output_tokens == 100

    def test_query_with_citations_validates_empty_documents(self):
        """LLMClient should validate documents list is not empty."""
        from src.processor.llm.llm_client import LLMClient

        client = LLMClient(provider="anthropic")

        with pytest.raises(ValueError, match="documents cannot be empty"):
            client.query_with_citations("Query", [], [])

    def test_query_with_citations_validates_metadata_match(self):
        """LLMClient should validate documents and metadata have same length."""
        from src.processor.llm.llm_client import LLMClient

        client = LLMClient(provider="anthropic")

        with pytest.raises(ValueError, match="documents and metadata must have same length"):
            client.query_with_citations(
                "Query",
                ["Doc 1", "Doc 2"],
                [{"source_url": "wiki/page1"}]  # Only 1 metadata for 2 docs
            )

    def test_query_with_citations_validates_empty_query(self):
        """LLMClient should validate query is not empty."""
        from src.processor.llm.llm_client import LLMClient

        client = LLMClient(provider="anthropic")

        with pytest.raises(ValueError, match="query cannot be empty"):
            client.query_with_citations(
                "",
                ["Document"],
                [{"source_url": "wiki/page"}]
            )

    def test_query_with_citations_handles_multiple_text_blocks(self):
        """LLMClient should handle responses with multiple text blocks."""
        from src.processor.llm.llm_client import LLMClient

        with patch("anthropic.Anthropic") as mock_anthropic_class:
            mock_client = MagicMock()
            mock_response = MagicMock()

            # Multiple text blocks in response
            block1 = MagicMock()
            block1.type = "text"
            block1.text = "First part. "
            block1.citations = []

            block2 = MagicMock()
            block2.type = "text"
            block2.text = "Second part."
            citation = MagicMock()
            citation.document_index = 0
            citation.cited_text = "Source text"
            citation.location = {"start": 0, "end": 11}
            block2.citations = [citation]

            mock_response.content = [block1, block2]
            mock_response.usage = MagicMock(input_tokens=100, output_tokens=50)
            mock_client.messages.create.return_value = mock_response
            mock_anthropic_class.return_value = mock_client

            client = LLMClient(provider="anthropic")

            result = client.query_with_citations(
                "Query",
                ["Document"],
                [{"source_url": "wiki/page", "page_title": "Page"}]
            )

            # Should concatenate text from all blocks
            assert result["text"] == "First part. Second part."
            # Should extract citations from all blocks
            assert len(result["evidence"]) == 1
            assert result["evidence"][0]["cited_text"] == "Source text"
