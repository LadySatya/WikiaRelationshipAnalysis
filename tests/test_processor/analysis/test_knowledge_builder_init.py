"""
Unit tests for CharacterKnowledgeBuilder initialization and setup.

Tests verify:
- Initialization with valid project name
- Directory structure creation
- Tool loading and registration
- System prompt loading
- QueryEngine integration
"""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.processor.analysis.knowledge_builder import CharacterKnowledgeBuilder


@pytest.mark.unit
class TestKnowledgeBuilderInitialization:
    """Test CharacterKnowledgeBuilder initialization."""

    @patch("src.processor.analysis.knowledge_builder.QueryEngine")
    @patch("src.processor.analysis.knowledge_builder.load_system_prompt")
    @patch("src.processor.analysis.knowledge_builder.load_tool_schemas")
    def test_init_with_valid_project_name(
        self, mock_load_schemas, mock_load_prompt, mock_qe
    ):
        """Should initialize with valid project name."""
        mock_load_prompt.return_value = "Test system prompt"
        mock_load_schemas.return_value = [
            {"name": "search_characters"},
            {"name": "create_character"},
        ]

        builder = CharacterKnowledgeBuilder(project_name="test_project")

        assert builder.project_name == "test_project"
        assert builder.project_dir.name == "test_project"
        assert builder.save_frequency == 10  # default

    @patch("src.processor.analysis.knowledge_builder.QueryEngine")
    @patch("src.processor.analysis.knowledge_builder.load_system_prompt")
    @patch("src.processor.analysis.knowledge_builder.load_tool_schemas")
    def test_init_with_custom_save_frequency(
        self, mock_load_schemas, mock_load_prompt, mock_qe
    ):
        """Should accept custom save frequency."""
        mock_load_prompt.return_value = "Test system prompt"
        mock_load_schemas.return_value = []

        builder = CharacterKnowledgeBuilder(project_name="test", save_frequency=5)

        assert builder.save_frequency == 5

    @patch("src.processor.analysis.knowledge_builder.QueryEngine")
    @patch("src.processor.analysis.knowledge_builder.load_system_prompt")
    @patch("src.processor.analysis.knowledge_builder.load_tool_schemas")
    def test_init_creates_directory_paths(
        self, mock_load_schemas, mock_load_prompt, mock_qe
    ):
        """Should set up correct directory paths."""
        mock_load_prompt.return_value = "Test system prompt"
        mock_load_schemas.return_value = []

        builder = CharacterKnowledgeBuilder(project_name="test")

        assert builder.characters_dir == builder.project_dir / "characters"
        assert builder.relationships_dir == builder.project_dir / "relationships"

    @patch("src.processor.analysis.knowledge_builder.QueryEngine")
    @patch("src.processor.analysis.knowledge_builder.load_system_prompt")
    @patch("src.processor.analysis.knowledge_builder.load_tool_schemas")
    def test_init_loads_system_prompt(
        self, mock_load_schemas, mock_load_prompt, mock_qe
    ):
        """Should load knowledge building system prompt."""
        mock_load_prompt.return_value = "Test system prompt"
        mock_load_schemas.return_value = []

        builder = CharacterKnowledgeBuilder(project_name="test")

        mock_load_prompt.assert_called_once_with("knowledge_building_system")
        assert builder.system_prompt == "Test system prompt"

    @patch("src.processor.analysis.knowledge_builder.QueryEngine")
    @patch("src.processor.analysis.knowledge_builder.load_system_prompt")
    @patch("src.processor.analysis.knowledge_builder.load_tool_schemas")
    def test_init_loads_tool_schemas(
        self, mock_load_schemas, mock_load_prompt, mock_qe
    ):
        """Should load all tool schemas from knowledge_building directory."""
        mock_load_prompt.return_value = "Test system prompt"
        expected_tools = [
            {"name": "search_characters"},
            {"name": "create_character"},
            {"name": "update_character"},
            {"name": "get_relationship"},
            {"name": "create_relationship"},
            {"name": "add_relationship_claim"},
            {"name": "get_character"},
            {"name": "search_wiki"},
        ]
        mock_load_schemas.return_value = expected_tools

        builder = CharacterKnowledgeBuilder(project_name="test")

        mock_load_schemas.assert_called_once_with("knowledge_building")
        assert len(builder.kb_tools) == 8
        tool_names = [t["name"] for t in builder.kb_tools]
        assert all(
            tool in tool_names
            for tool in [
                "search_characters",
                "create_character",
                "update_character",
                "get_relationship",
                "create_relationship",
                "add_relationship_claim",
                "get_character",
                "search_wiki",
            ]
        )

    @patch("src.processor.analysis.knowledge_builder.QueryEngine")
    @patch("src.processor.analysis.knowledge_builder.load_system_prompt")
    @patch("src.processor.analysis.knowledge_builder.load_tool_schemas")
    def test_init_creates_query_engine(
        self, mock_load_schemas, mock_load_prompt, mock_qe_class
    ):
        """Should create QueryEngine instance."""
        mock_load_prompt.return_value = "Test system prompt"
        mock_load_schemas.return_value = []
        mock_qe = Mock()
        mock_qe_class.return_value = mock_qe

        builder = CharacterKnowledgeBuilder(project_name="test")

        mock_qe_class.assert_called_once_with(project_name="test")
        assert builder.query_engine == mock_qe

    @patch("src.processor.analysis.knowledge_builder.QueryEngine")
    @patch("src.processor.analysis.knowledge_builder.load_system_prompt")
    @patch("src.processor.analysis.knowledge_builder.load_tool_schemas")
    def test_init_creates_empty_knowledge_base(
        self, mock_load_schemas, mock_load_prompt, mock_qe
    ):
        """Should initialize empty knowledge base structure."""
        mock_load_prompt.return_value = "Test system prompt"
        mock_load_schemas.return_value = []

        builder = CharacterKnowledgeBuilder(project_name="test")

        assert "characters" in builder.knowledge_base
        assert "relationships" in builder.knowledge_base
        assert "metadata" in builder.knowledge_base
        assert builder.knowledge_base["characters"] == {}
        assert builder.knowledge_base["relationships"] == {}

    @patch("src.processor.analysis.knowledge_builder.QueryEngine")
    @patch("src.processor.analysis.knowledge_builder.load_system_prompt")
    @patch("src.processor.analysis.knowledge_builder.load_tool_schemas")
    def test_init_sets_page_counter(self, mock_load_schemas, mock_load_prompt, mock_qe):
        """Should initialize page counter to 0 in metadata."""
        mock_load_prompt.return_value = "Test system prompt"
        mock_load_schemas.return_value = []

        builder = CharacterKnowledgeBuilder(project_name="test")

        assert builder.knowledge_base["metadata"]["pages_processed"] == 0
