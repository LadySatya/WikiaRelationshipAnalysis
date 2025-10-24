"""
Pytest configuration and fixtures for WikiaAnalysis tests.

This file automatically patches LLMClient to use MockLLMClient by default,
preventing accidental API calls and enabling cost-free testing.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock
import sys

# Add tests directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from mocks.mock_llm_client import MockLLMClient


# Pytest markers configuration
def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "unit: Unit tests (mocked, no real I/O)")
    config.addinivalue_line("markers", "integration: Integration tests (may use fixtures)")
    config.addinivalue_line("markers", "realapi: Tests that use real Anthropic API (opt-in only)")
    config.addinivalue_line("markers", "expensive: Tests that consume significant API quota")


@pytest.fixture
def mock_llm_client():
    """
    Provide mock LLM client for tests.

    This fixture provides a MockLLMClient instance that returns
    fixture-based or synthetic responses without making real API calls.

    Returns:
        MockLLMClient instance

    Example:
        def test_character_discovery(mock_llm_client):
            # LLMClient is already patched with mock_llm_client
            extractor = CharacterExtractor("test_project")
            characters = extractor.discover_characters()
            assert len(characters) > 0
    """
    fixture_dir = Path(__file__).parent / "fixtures" / "llm_responses"
    return MockLLMClient(
        fixture_dir=fixture_dir,
        use_fixtures=True
    )


@pytest.fixture(autouse=True)
def auto_patch_llm_client(monkeypatch, mock_llm_client, request):
    """
    Automatically patch LLMClient to use MockLLMClient in all tests.

    This fixture runs automatically for every test unless:
    - Test is marked with @pytest.mark.realapi
    - Test explicitly opts out
    - Test is in the LLMClient's own test file (to allow direct unit testing)

    Args:
        monkeypatch: Pytest monkeypatch fixture
        mock_llm_client: MockLLMClient fixture
        request: Pytest request object for accessing markers
    """
    # Check if test wants real API
    if "realapi" in request.keywords:
        # Skip patching for real API tests
        return

    # Skip auto-patching for LLMClient's own unit tests
    # (they manually mock the Anthropic client for direct testing)
    if "test_llm_client.py" in str(request.fspath):
        return

    # Patch LLMClient.__init__ to return our mock
    def mock_init(self, provider=None, model=None, api_key=None):
        """Replace LLMClient init with mock fields."""
        # Copy mock client fields to real instance
        self.provider = mock_llm_client.provider if hasattr(mock_llm_client, 'provider') else "anthropic"
        self.model = mock_llm_client.model
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.call_count = 0
        self._mock_client = mock_llm_client

    # Patch generate method
    def mock_generate(self, prompt, system_prompt=None, **kwargs):
        """Replace LLMClient.generate with mock version."""
        return self._mock_client.generate(prompt, system_prompt, **kwargs)

    # Patch get_usage_stats
    def mock_get_usage_stats(self):
        """Replace LLMClient.get_usage_stats with mock version."""
        return self._mock_client.get_usage_stats()

    # Patch estimate_cost
    def mock_estimate_cost(self, input_tokens, output_tokens):
        """Replace LLMClient.estimate_cost with mock version."""
        return self._mock_client.estimate_cost(input_tokens, output_tokens)

    # Patch reset_usage_stats
    def mock_reset_usage_stats(self):
        """Replace LLMClient.reset_usage_stats with mock version."""
        self._mock_client.reset_usage_stats()

    # Apply patches
    monkeypatch.setattr("src.processor.llm.llm_client.LLMClient.__init__", mock_init)
    monkeypatch.setattr("src.processor.llm.llm_client.LLMClient.generate", mock_generate)
    monkeypatch.setattr("src.processor.llm.llm_client.LLMClient.get_usage_stats", mock_get_usage_stats)
    monkeypatch.setattr("src.processor.llm.llm_client.LLMClient.estimate_cost", mock_estimate_cost)
    monkeypatch.setattr("src.processor.llm.llm_client.LLMClient.reset_usage_stats", mock_reset_usage_stats)


@pytest.fixture
def mock_query_engine(mock_llm_client):
    """
    Provide mock QueryEngine for testing.

    Returns:
        Mock QueryEngine with patched LLM client
    """
    mock_engine = Mock()
    mock_engine.llm_client = mock_llm_client
    mock_engine.query.side_effect = lambda query, **kwargs: mock_llm_client.generate(query)
    mock_engine.get_usage_stats.side_effect = lambda: mock_llm_client.get_usage_stats()
    return mock_engine


# Cleanup fixtures
@pytest.fixture(autouse=True)
def cleanup_test_data(request):
    """
    Clean up test data after tests (if needed).

    This can be extended to clean up test databases, files, etc.
    """
    yield
    # Cleanup code here if needed
