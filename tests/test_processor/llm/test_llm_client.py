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
