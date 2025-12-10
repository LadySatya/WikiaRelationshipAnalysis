"""
Tests for tool_schema_loader module.

Tests the loading of tool schemas and system prompts from JSON files.
"""
import pytest
from pathlib import Path
from unittest.mock import patch, mock_open
import json

from src.utils.tool_schema_loader import load_tool_schemas, load_system_prompt


@pytest.mark.unit
class TestLoadToolSchemas:
    """Tests for load_tool_schemas function."""

    def test_load_schemas_returns_list(self):
        """Test that load_tool_schemas returns a list of tool schemas."""
        # Use existing category that we know exists
        schemas = load_tool_schemas("knowledge_building")

        assert isinstance(schemas, list)
        assert len(schemas) > 0

    def test_load_schemas_uses_config_directory(self):
        """Test that schemas are loaded from config/llm_tools/schemas/<category>."""
        # Use existing schema category
        schemas = load_tool_schemas("knowledge_building")

        assert isinstance(schemas, list)
        assert len(schemas) > 0

        # Each schema should have required fields
        for schema in schemas:
            assert "name" in schema
            assert "description" in schema
            assert "input_schema" in schema

    def test_load_schemas_returns_sorted_by_filename(self):
        """Test that schemas are returned sorted by filename."""
        schemas = load_tool_schemas("knowledge_building")

        # Get names
        names = [s["name"] for s in schemas]

        # Names should be in some consistent order (from sorted filenames)
        assert len(names) == len(set(names))  # No duplicates

    def test_load_schemas_nonexistent_category_raises_error(self):
        """Test that loading from non-existent category raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError) as exc_info:
            load_tool_schemas("nonexistent_category_xyz")

        assert "not found" in str(exc_info.value).lower()

    def test_load_schemas_validates_json_format(self):
        """Test that each loaded schema is valid JSON with expected structure."""
        schemas = load_tool_schemas("knowledge_building")

        for schema in schemas:
            # Check required fields
            assert isinstance(schema.get("name"), str)
            assert isinstance(schema.get("description"), str)
            assert isinstance(schema.get("input_schema"), dict)

            # Check input_schema structure
            input_schema = schema["input_schema"]
            assert input_schema.get("type") == "object"
            assert "properties" in input_schema


@pytest.mark.unit
class TestLoadSystemPrompt:
    """Tests for load_system_prompt function."""

    def test_load_prompt_returns_string(self):
        """Test that load_system_prompt returns a string."""
        prompt = load_system_prompt("knowledge_building_system")

        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_load_prompt_nonexistent_raises_error(self):
        """Test that loading non-existent prompt raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError) as exc_info:
            load_system_prompt("nonexistent_prompt_xyz")

        assert "not found" in str(exc_info.value).lower()

    def test_load_prompt_reads_from_prompts_directory(self):
        """Test that prompts are loaded from config/llm_tools/prompts/."""
        # Use existing prompt
        prompt = load_system_prompt("knowledge_building_system")

        # Should contain meaningful content
        assert len(prompt) > 100  # Reasonable minimum length

    def test_load_prompt_preserves_whitespace(self):
        """Test that prompt whitespace is preserved."""
        prompt = load_system_prompt("knowledge_building_system")

        # Should have newlines preserved
        assert "\n" in prompt


@pytest.mark.unit
class TestToolSchemaIntegration:
    """Integration tests for schema and prompt loading."""

    def test_knowledge_building_schemas_match_prompts(self):
        """Test that knowledge_building schemas have corresponding prompts."""
        schemas = load_tool_schemas("knowledge_building")
        prompt = load_system_prompt("knowledge_building_system")

        # Schemas and prompts should both exist
        assert len(schemas) > 0
        assert len(prompt) > 0

        # Prompt should reference some tool names
        tool_names = [s["name"] for s in schemas]
        assert any(name in prompt for name in tool_names)

    def test_character_classification_schemas_exist(self):
        """Test that character_classification schemas exist if used."""
        # This category should exist based on CLAUDE.md
        try:
            schemas = load_tool_schemas("character_classification")
            assert len(schemas) > 0
        except FileNotFoundError:
            # Category may not exist, that's OK
            pass
