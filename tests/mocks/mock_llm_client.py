"""
MockLLMClient - Drop-in replacement for LLMClient that returns fixture-based responses.

This mock allows testing without making real Anthropic API calls, saving costs
and enabling offline development. Responses are loaded from fixture files or
generated based on query patterns.
"""

from typing import Optional, List, Dict, Any
from pathlib import Path
import json
import re


class MockLLMClient:
    """
    Mock LLM client that returns pre-defined responses without API calls.

    Features:
    - Loads responses from fixture files
    - Pattern-based response matching
    - Tracks "mock token usage" for realistic cost estimation
    - Deterministic output for testing

    Args:
        fixture_dir: Directory containing response fixtures (default: tests/fixtures/llm_responses)
        use_fixtures: If True, load from files; if False, use built-in responses

    Example:
        >>> client = MockLLMClient()
        >>> response = client.generate("List all characters")
        >>> print(response)
        "Korra\\nAang\\nMako\\nBolin"
    """

    # Built-in synthetic responses for page classification
    SYNTHETIC_RESPONSES = {
        "single_classification_yes": "yes",
        "single_classification_no": "no",
        "batch_classification": "Unknown: yes",  # Fallback for batch classification
        "default": "Mako: yes"
    }

    # Pricing per 1M tokens (same as real Haiku)
    PRICING = {
        "claude-3-5-haiku-20241022": {
            "input": 1.00,
            "output": 5.00,
        }
    }

    def __init__(
        self,
        fixture_dir: Optional[Path] = None,
        use_fixtures: bool = True,
        model: str = "claude-3-5-haiku-20241022"
    ):
        """
        Initialize mock LLM client.

        Args:
            fixture_dir: Directory with fixture files
            use_fixtures: Whether to load fixtures from files
            model: Model name (for cost calculation)
        """
        self.fixture_dir = fixture_dir or Path("tests/fixtures/llm_responses")
        self.use_fixtures = use_fixtures
        self.model = model

        # Token tracking
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.call_count = 0

        # Load fixtures if enabled
        self.fixtures = {}
        if use_fixtures and self.fixture_dir.exists():
            self._load_fixtures()

    def _load_fixtures(self):
        """Load all fixture files from fixture directory."""
        for fixture_file in self.fixture_dir.rglob("*.json"):
            try:
                with open(fixture_file, 'r', encoding='utf-8') as f:
                    fixture_data = json.load(f)
                    # Store by fixture name
                    fixture_name = fixture_file.stem
                    self.fixtures[fixture_name] = fixture_data
            except Exception as e:
                print(f"[WARN] Failed to load fixture {fixture_file}: {e}")

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        context: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """
        Generate mock response based on prompt.

        Args:
            prompt: User prompt/question
            system_prompt: Optional system prompt
            temperature: Sampling temperature (ignored in mock)
            max_tokens: Maximum tokens (used for token estimation)
            context: Conversation context (ignored in mock)

        Returns:
            Mock response string
        """
        self.call_count += 1

        # Try to find matching fixture
        response = self._get_response(prompt, system_prompt)

        # Estimate token usage
        estimated_input = len(prompt.split()) + (len(system_prompt.split()) if system_prompt else 0)
        estimated_output = len(response.split())

        self.total_input_tokens += estimated_input
        self.total_output_tokens += estimated_output

        return response

    def _get_response(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Get response for a prompt using fixtures or synthetic responses.

        Args:
            prompt: User prompt
            system_prompt: System prompt (used for matching)

        Returns:
            Response string
        """
        prompt_lower = prompt.lower()

        # Try fixture match first
        if self.use_fixtures:
            for fixture_name, fixture_data in self.fixtures.items():
                # Simple substring matching
                if self._matches_fixture(prompt_lower, fixture_data):
                    return fixture_data.get("response", "")

        # Fall back to pattern-based synthetic responses
        return self._get_synthetic_response(prompt_lower)

    def _matches_fixture(self, prompt: str, fixture_data: dict) -> bool:
        """
        Check if prompt matches a fixture.

        Args:
            prompt: Prompt text (lowercase)
            fixture_data: Fixture dictionary

        Returns:
            True if matches
        """
        fixture_query = fixture_data.get("query", "").lower()

        # Check for substring match
        if fixture_query and fixture_query[:50] in prompt:
            return True

        # Check for pattern match
        pattern = fixture_data.get("pattern")
        if pattern and re.search(pattern, prompt, re.IGNORECASE):
            return True

        return False

    def _get_synthetic_response(self, prompt: str) -> str:
        """
        Generate synthetic response based on prompt patterns.

        Args:
            prompt: Prompt text (lowercase)

        Returns:
            Synthetic response string
        """
        # Batch classification queries (page titles list)
        if "page titles:" in prompt.lower():
            return self._generate_batch_classification(prompt)

        # Single page classification
        if "is this wiki page about a character" in prompt.lower():
            # Simple heuristic: if title contains common character words, yes
            if any(word in prompt.lower() for word in ["korra", "aang", "zuko", "mako", "bolin", "toph"]):
                return self.SYNTHETIC_RESPONSES["single_classification_yes"]
            return self.SYNTHETIC_RESPONSES["single_classification_no"]

        # Default response
        return self.SYNTHETIC_RESPONSES["default"]

    def _generate_batch_classification(self, prompt: str) -> str:
        """Generate batch classification response based on prompt titles."""
        # Extract titles from "Page titles:" section
        if "Page titles:" not in prompt:
            return self.SYNTHETIC_RESPONSES["batch_classification"]

        titles_section = prompt.split("Page titles:")[1].split("\n\n")[0]
        titles = [line.strip() for line in titles_section.split("\n") if line.strip()]

        # Simple heuristic: classify based on common patterns
        character_keywords = ["korra", "aang", "zuko", "mako", "bolin", "bumi", "asami", "tenzin", "katara", "sokka", "toph"]
        non_character_keywords = ["city", "state", "nation", "team", "avatar state", "episode"]

        response_lines = []
        for title in titles:
            title_lower = title.lower()

            # Check if it's clearly a non-character
            if any(keyword in title_lower for keyword in non_character_keywords):
                response_lines.append(f"{title}: no")
            # Check if it's clearly a character
            elif any(keyword in title_lower for keyword in character_keywords):
                response_lines.append(f"{title}: yes")
            # Default: assume character (conservative)
            else:
                response_lines.append(f"{title}: yes")

        return "\n".join(response_lines)

    def get_usage_stats(self) -> Dict[str, Any]:
        """
        Get token usage statistics (mock).

        Returns:
            Dictionary with usage stats
        """
        cost = self.estimate_cost(self.total_input_tokens, self.total_output_tokens)

        return {
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "estimated_cost_usd": cost,
            "model": self.model,
            "call_count": self.call_count,
            "mode": "MOCK"
        }

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Estimate cost in USD (same calculation as real client).

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Estimated cost in USD
        """
        pricing = self.PRICING.get(
            self.model,
            self.PRICING["claude-3-5-haiku-20241022"]
        )

        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]

        return input_cost + output_cost

    def reset_usage_stats(self) -> None:
        """Reset token usage statistics to zero."""
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.call_count = 0
