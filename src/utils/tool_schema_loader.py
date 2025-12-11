"""
Tool schema loader - Load tool definitions from JSON schema files.

This module provides utilities to load tool definitions following
Anthropic's recommended pattern of separating tool definitions from code.

Usage:
    >>> from src.utils.tool_schema_loader import load_tool_schemas, load_system_prompt
    >>>
    >>> # Load tool schemas
    >>> tools = load_tool_schemas("character_classification")
    >>> # Returns: [{"name": "get_infobox_fields", "description": "...", "input_schema": {...}}, ...]
    >>>
    >>> # Load system prompt
    >>> prompt = load_system_prompt("character_classification_system")
    >>> # Returns: "You are a character classifier..."
"""

import json
from pathlib import Path
from typing import Any, Dict, List


def load_tool_schemas(category: str) -> List[Dict[str, Any]]:
    """
    Load all tool schemas for a given category.

    Args:
        category: Tool category (e.g., "character_classification", "relationship_extraction")

    Returns:
        List of tool definition dicts in Anthropic format:
        [
            {
                "name": "tool_name",
                "description": "Tool description",
                "input_schema": {...}
            },
            ...
        ]

    Raises:
        FileNotFoundError: If category directory doesn't exist
        ValueError: If no tool schemas found in category

    Example:
        >>> tools = load_tool_schemas("character_classification")
        >>> # Returns tools from config/llm_tools/schemas/character_classification/*.json
    """
    # Get schema directory
    schema_dir = Path("config/llm_tools/schemas") / category

    if not schema_dir.exists():
        raise FileNotFoundError(
            f"Tool schema directory not found: {schema_dir}\n"
            f"Expected to find tool schemas in: {schema_dir.absolute()}"
        )

    # Load all JSON files in the directory
    tool_schemas = []
    for schema_file in sorted(schema_dir.glob("*.json")):
        with open(schema_file, "r", encoding="utf-8") as f:
            schema = json.load(f)
            tool_schemas.append(schema)

    if not tool_schemas:
        raise ValueError(
            f"No tool schemas found in {schema_dir}\n"
            f"Expected to find *.json files in: {schema_dir.absolute()}"
        )

    return tool_schemas


def load_system_prompt(prompt_name: str) -> str:
    """
    Load system prompt from text file.

    Args:
        prompt_name: Name of prompt file (without .txt extension)

    Returns:
        System prompt text

    Raises:
        FileNotFoundError: If prompt file doesn't exist

    Example:
        >>> prompt = load_system_prompt("character_classification_system")
        >>> # Returns content from config/llm_tools/prompts/character_classification_system.txt
    """
    prompt_file = Path("config/llm_tools/prompts") / f"{prompt_name}.txt"

    if not prompt_file.exists():
        raise FileNotFoundError(
            f"System prompt file not found: {prompt_file}\n"
            f"Expected to find prompt at: {prompt_file.absolute()}"
        )

    with open(prompt_file, "r", encoding="utf-8") as f:
        return f.read()
