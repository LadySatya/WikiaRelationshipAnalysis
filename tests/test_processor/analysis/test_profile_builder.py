"""
Tests for ProfileBuilder - Character profile building with tool-enabled LLM.

Tests the current tool-based architecture where Claude autonomously uses tools
to gather relationship information.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch, mock_open
from pathlib import Path
import json


# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit


class TestProfileBuilderInitialization:
    """Test ProfileBuilder initialization."""

    @patch("src.processor.analysis.profile_builder.QueryEngine")
    @patch("src.processor.analysis.profile_builder.ToolRegistry")
    def test_init_with_project_name(self, mock_registry, mock_qe):
        """ProfileBuilder should initialize with project name."""
        from src.processor.analysis.profile_builder import ProfileBuilder

        builder = ProfileBuilder(project_name="avatar_wiki")

        assert builder.project_name == "avatar_wiki"

    @patch("src.processor.analysis.profile_builder.QueryEngine")
    @patch("src.processor.analysis.profile_builder.ToolRegistry")
    def test_init_creates_query_engine(self, mock_registry, mock_qe_class):
        """ProfileBuilder should create QueryEngine for project."""
        from src.processor.analysis.profile_builder import ProfileBuilder

        builder = ProfileBuilder(project_name="test_wiki")

        # Should create query engine with project name
        mock_qe_class.assert_called_once_with(project_name="test_wiki")
        assert builder.query_engine is not None

    @patch("src.processor.analysis.profile_builder.QueryEngine")
    @patch("src.processor.analysis.profile_builder.ToolRegistry")
    def test_init_creates_tool_registry(self, mock_registry_class, mock_qe):
        """ProfileBuilder should create ToolRegistry."""
        from src.processor.analysis.profile_builder import ProfileBuilder

        mock_qe_instance = Mock()
        mock_qe.return_value = mock_qe_instance

        builder = ProfileBuilder(project_name="test_wiki")

        # Should create tool registry with query engine
        mock_registry_class.assert_called_once_with(mock_qe_instance)
        assert builder.tools is not None

    @patch("src.processor.analysis.profile_builder.QueryEngine")
    @patch("src.processor.analysis.profile_builder.ToolRegistry")
    def test_init_with_custom_parameters(self, mock_registry, mock_qe):
        """ProfileBuilder should accept custom parameters."""
        from src.processor.analysis.profile_builder import ProfileBuilder

        builder = ProfileBuilder(
            project_name="test_wiki",
            min_evidence_count=2,
            relationship_confidence_threshold=0.8
        )

        assert builder.min_evidence_count == 2
        assert builder.confidence_threshold == 0.8

    @patch("src.processor.analysis.profile_builder.QueryEngine")
    @patch("src.processor.analysis.profile_builder.ToolRegistry")
    def test_init_default_parameters(self, mock_registry, mock_qe):
        """ProfileBuilder should use default parameters when not specified."""
        from src.processor.analysis.profile_builder import ProfileBuilder

        builder = ProfileBuilder(project_name="test_wiki")

        assert builder.min_evidence_count == 1
        assert builder.confidence_threshold == 0.6

    @patch("src.processor.analysis.profile_builder.QueryEngine")
    @patch("src.processor.analysis.profile_builder.ToolRegistry")
    def test_init_sets_up_paths(self, mock_registry, mock_qe):
        """ProfileBuilder should set up project paths."""
        from src.processor.analysis.profile_builder import ProfileBuilder

        builder = ProfileBuilder(project_name="test_wiki")

        assert builder.project_dir == Path("data/projects/test_wiki")
        assert builder.characters_dir == Path("data/projects/test_wiki/characters")
        assert builder.relationships_dir == Path("data/projects/test_wiki/relationships")


# Removed weak TestSystemPromptGeneration class - tests were just keyword checking
# System prompt is tested indirectly through integration tests


class TestTaskPromptGeneration:
    """Test task prompt generation for specific characters."""

    @patch("src.processor.analysis.profile_builder.QueryEngine")
    @patch("src.processor.analysis.profile_builder.ToolRegistry")
    def test_build_task_prompt_includes_character_name(self, mock_registry, mock_qe):
        """Task prompt should include character name."""
        from src.processor.analysis.profile_builder import ProfileBuilder

        builder = ProfileBuilder(project_name="test_wiki")
        character = {
            "name": "Aang",
            "full_name": "Avatar Aang",
            "source_url": "https://avatar.fandom.com/wiki/Aang"
        }

        prompt = builder._build_task_prompt(character)

        assert "Aang" in prompt

    @patch("src.processor.analysis.profile_builder.QueryEngine")
    @patch("src.processor.analysis.profile_builder.ToolRegistry")
    def test_build_task_prompt_includes_full_name(self, mock_registry, mock_qe):
        """Task prompt should include character full name."""
        from src.processor.analysis.profile_builder import ProfileBuilder

        builder = ProfileBuilder(project_name="test_wiki")
        character = {
            "name": "Aang",
            "full_name": "Avatar Aang",
            "source_url": "https://avatar.fandom.com/wiki/Aang"
        }

        prompt = builder._build_task_prompt(character)

        assert character["full_name"] in prompt

    @patch("src.processor.analysis.profile_builder.QueryEngine")
    @patch("src.processor.analysis.profile_builder.ToolRegistry")
    def test_build_task_prompt_handles_disambiguation(self, mock_registry, mock_qe):
        """Task prompt should handle character with disambiguation."""
        from src.processor.analysis.profile_builder import ProfileBuilder

        builder = ProfileBuilder(project_name="test_wiki")
        character = {
            "name": "Bumi",
            "full_name": "Bumi (King of Omashu)",
            "disambiguation": "King of Omashu",
            "source_url": "https://avatar.fandom.com/wiki/Bumi_(King_of_Omashu)"
        }

        prompt = builder._build_task_prompt(character)

        assert "Bumi" in prompt
        assert "King of Omashu" in prompt or "(King of Omashu)" in prompt


class TestProfileResultParsing:
    """Test parsing LLM results into structured profiles."""

    @patch("src.processor.analysis.profile_builder.QueryEngine")
    @patch("src.processor.analysis.profile_builder.ToolRegistry")
    def test_parse_profile_result_basic_structure(self, mock_registry, mock_qe):
        """Should parse LLM result into profile structure."""
        from src.processor.analysis.profile_builder import ProfileBuilder

        builder = ProfileBuilder(project_name="test_wiki")
        character = {"name": "Aang", "source_url": "wiki/Aang"}

        llm_result = {
            "final_response": json.dumps({
                "relationships": [
                    {
                        "target": "Katara",
                        "type": "romantic",
                        "summary": "Love interest",
                        "claims": ["They are in love"],
                        "confidence": 0.9,
                        "evidence_count": 5
                    }
                ]
            }),
            "tool_calls": [],
            "usage": {
                "iterations": 1,
                "input_tokens": 100,
                "output_tokens": 50,
                "estimated_cost_usd": 0.01
            }
        }

        profile = builder._parse_profile_result(character, llm_result, verbose=False)

        # Should have basic structure
        assert "name" in profile
        assert "profile" in profile
        assert "relationships" in profile["profile"]

    @patch("src.processor.analysis.profile_builder.QueryEngine")
    @patch("src.processor.analysis.profile_builder.ToolRegistry")
    def test_parse_profile_result_includes_metadata(self, mock_registry, mock_qe):
        """Should include metadata in parsed profile."""
        from src.processor.analysis.profile_builder import ProfileBuilder

        builder = ProfileBuilder(project_name="test_wiki")
        character = {"name": "Aang", "source_url": "wiki/Aang"}

        llm_result = {
            "final_response": json.dumps({"relationships": []}),
            "tool_calls": [{"tool": "search_wiki", "input": {}, "result": {}}],
            "usage": {
                "iterations": 2,
                "input_tokens": 100,
                "output_tokens": 50,
                "estimated_cost_usd": 0.01
            }
        }

        profile = builder._parse_profile_result(character, llm_result, verbose=False)

        # Should have metadata
        assert "profile" in profile
        assert "total_relationships" in profile["profile"]
        assert "tool_calls_made" in profile["profile"]
        assert "profile_built_at" in profile["profile"]

    @patch("src.processor.analysis.profile_builder.QueryEngine")
    @patch("src.processor.analysis.profile_builder.ToolRegistry")
    def test_parse_profile_result_handles_invalid_json(self, mock_registry, mock_qe):
        """Should handle LLM returning invalid JSON gracefully."""
        from src.processor.analysis.profile_builder import ProfileBuilder

        builder = ProfileBuilder(project_name="test_wiki")
        character = {"name": "Aang", "source_url": "wiki/Aang"}

        llm_result = {
            "final_response": "Not valid JSON at all",
            "tool_calls": [],
            "usage": {
                "iterations": 1,
                "input_tokens": 100,
                "output_tokens": 50,
                "estimated_cost_usd": 0.01
            }
        }

        # Should not crash
        profile = builder._parse_profile_result(character, llm_result, verbose=False)

        # Should have basic structure even if parsing failed
        assert "name" in profile
        assert "profile" in profile


class TestGraphGeneration:
    """Test relationship graph generation."""

    @patch("src.processor.analysis.profile_builder.QueryEngine")
    @patch("src.processor.analysis.profile_builder.ToolRegistry")
    def test_build_relationship_graph_structure(self, mock_registry, mock_qe):
        """Relationship graph should have correct structure."""
        from src.processor.analysis.profile_builder import ProfileBuilder

        builder = ProfileBuilder(project_name="test_wiki")

        profiles = {
            "Aang": {
                "name": "Aang",
                "full_name": "Avatar Aang",
                "source_url": "wiki/Aang",
                "disambiguation": None,
                "profile": {
                    "total_relationships": 1,
                    "relationships": [
                        {
                            "target": "Katara",
                            "type": "romantic",
                            "summary": "Love interest",
                            "confidence": 0.9,
                            "evidence_count": 5
                        }
                    ]
                }
            }
        }

        graph = builder._build_relationship_graph(profiles)

        # Should have required structure
        assert "nodes" in graph
        assert "edges" in graph
        assert "metadata" in graph

    @patch("src.processor.analysis.profile_builder.QueryEngine")
    @patch("src.processor.analysis.profile_builder.ToolRegistry")
    def test_build_relationship_graph_nodes(self, mock_registry, mock_qe):
        """Graph nodes should contain character information."""
        from src.processor.analysis.profile_builder import ProfileBuilder

        builder = ProfileBuilder(project_name="test_wiki")

        profiles = {
            "Aang": {
                "name": "Aang",
                "full_name": "Avatar Aang",
                "source_url": "wiki/Aang",
                "disambiguation": None,
                "profile": {"total_relationships": 0, "relationships": []}
            }
        }

        graph = builder._build_relationship_graph(profiles)

        assert len(graph["nodes"]) == 1
        assert graph["nodes"][0]["id"] == "Aang"
        assert graph["nodes"][0]["full_name"] == "Avatar Aang"
        assert graph["nodes"][0]["source_url"] == "wiki/Aang"

    @patch("src.processor.analysis.profile_builder.QueryEngine")
    @patch("src.processor.analysis.profile_builder.ToolRegistry")
    def test_build_relationship_graph_edges(self, mock_registry, mock_qe):
        """Graph edges should contain relationship information."""
        from src.processor.analysis.profile_builder import ProfileBuilder

        builder = ProfileBuilder(project_name="test_wiki")

        profiles = {
            "Aang": {
                "name": "Aang",
                "full_name": "Avatar Aang",
                "source_url": "wiki/Aang",
                "disambiguation": None,
                "profile": {
                    "total_relationships": 1,
                    "relationships": [
                        {
                            "target": "Katara",
                            "type": "romantic",
                            "summary": "Love interest",
                            "confidence": 0.9,
                            "evidence_count": 5
                        }
                    ]
                }
            }
        }

        graph = builder._build_relationship_graph(profiles)

        assert len(graph["edges"]) == 1
        edge = graph["edges"][0]
        assert edge["from"] == "Aang"
        assert edge["to"] == "Katara"
        assert edge["type"] == "romantic"
        assert edge["confidence"] == 0.9

    @patch("src.processor.analysis.profile_builder.QueryEngine")
    @patch("src.processor.analysis.profile_builder.ToolRegistry")
    def test_build_relationship_graph_metadata(self, mock_registry, mock_qe):
        """Graph metadata should contain project statistics."""
        from src.processor.analysis.profile_builder import ProfileBuilder

        builder = ProfileBuilder(project_name="test_wiki")

        profiles = {
            "Aang": {
                "name": "Aang",
                "full_name": "Avatar Aang",
                "source_url": "wiki/Aang",
                "disambiguation": None,
                "profile": {
                    "total_relationships": 1,
                    "relationships": [
                        {"target": "Katara", "type": "romantic", "summary": "Love", "confidence": 0.9, "evidence_count": 5}
                    ]
                }
            }
        }

        graph = builder._build_relationship_graph(profiles)

        metadata = graph["metadata"]
        assert metadata["project_name"] == "test_wiki"
        assert metadata["total_characters"] == 1
        assert metadata["total_relationships"] == 1
        assert "built_at" in metadata
