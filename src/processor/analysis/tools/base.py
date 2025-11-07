"""
Base interface for ProfileBuilder tools.

All tools must extend ToolBase and implement:
- name: Tool identifier
- description: LLM-facing explanation
- input_schema: JSON schema for parameters
- execute(): Tool implementation
"""
from abc import ABC, abstractmethod
from typing import Dict, Any
import logging

from src.utils.logging_config import get_logger

logger = get_logger("llm")


class ToolBase(ABC):
    """
    Abstract base class for all ProfileBuilder tools.

    Each tool represents an action the LLM can take to gather
    information while building character profiles.

    Design principles:
    - Single Responsibility: Each tool does one thing well
    - Self-Documenting: Description is critical for LLM tool selection
    - Type Safe: Input schema validates parameters
    - Testable: Can be tested independently of ProfileBuilder
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Tool name as seen by LLM.

        Should be:
        - snake_case
        - Descriptive (e.g., 'search_wiki', not 'tool1')
        - Unique across all tools

        Returns:
            Tool identifier string
        """
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """
        Tool description for LLM.

        CRITICAL: This is how Claude decides when to use your tool.

        Should clearly explain:
        - What the tool does
        - When to use it
        - What it returns
        - Examples of good use cases

        Format:
        - Start with one-sentence summary
        - Use bullet points for details
        - Include "When to use:" section
        - Include "Returns:" section

        Returns:
            Multi-line description string
        """
        pass

    @property
    @abstractmethod
    def input_schema(self) -> Dict[str, Any]:
        """
        JSON schema defining tool parameters.

        Must follow Anthropic's tool input schema format:
        {
            "type": "object",
            "properties": {
                "param_name": {
                    "type": "string|integer|boolean|...",
                    "description": "What this param does"
                },
                ...
            },
            "required": ["param1", "param2"]
        }

        See: https://docs.anthropic.com/en/docs/build-with-claude/tool-use

        Returns:
            JSON schema dictionary
        """
        pass

    @abstractmethod
    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Execute the tool with given inputs.

        This is called by ToolRegistry when Claude makes a tool call.

        Args:
            **kwargs: Tool parameters matching input_schema

        Returns:
            Dictionary with tool results (structure depends on tool)

        Raises:
            ValueError: If parameters are invalid
            RuntimeError: If execution fails
        """
        pass

    def to_anthropic_format(self) -> Dict[str, Any]:
        """
        Convert tool to Anthropic API format.

        This is used by ToolRegistry to provide tools to the LLM.

        Returns:
            Tool definition dict for Anthropic Messages API:
            {
                "name": "tool_name",
                "description": "...",
                "input_schema": {...}
            }
        """
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema
        }

    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"<{self.__class__.__name__}: {self.name}>"
