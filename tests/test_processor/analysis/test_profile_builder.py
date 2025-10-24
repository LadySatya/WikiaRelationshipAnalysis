"""
Tests for ProfileBuilder - Character profile building with relationship extraction.

Following TDD methodology: write tests first, then implement.
This module tests the ProfileBuilder class which handles:
- Relationship discovery via RAG queries
- Relationship detail extraction with citation evidence
- Claim-based evidence mapping
- Profile building and persistence
"""
import pytest
from unittest.mock import Mock, MagicMock, patch, mock_open
from pathlib import Path
import json


# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit


class TestProfileBuilderInitialization:
    """Test ProfileBuilder initialization."""

    def test_init_with_project_name(self):
        """ProfileBuilder should initialize with project name."""
        from src.processor.analysis.profile_builder import ProfileBuilder

        with patch("src.processor.analysis.profile_builder.QueryEngine"):
            builder = ProfileBuilder(project_name="avatar_wiki")

            assert builder.project_name == "avatar_wiki"

    def test_init_creates_query_engine(self):
        """ProfileBuilder should create QueryEngine for project."""
        from src.processor.analysis.profile_builder import ProfileBuilder

        with patch("src.processor.analysis.profile_builder.QueryEngine") as mock_qe_class:
            builder = ProfileBuilder(project_name="test_wiki")

            # Should create query engine with project name
            mock_qe_class.assert_called_once_with(project_name="test_wiki")
            assert builder.query_engine is not None

    def test_init_with_custom_min_evidence_count(self):
        """ProfileBuilder should accept custom minimum evidence count."""
        from src.processor.analysis.profile_builder import ProfileBuilder

        with patch("src.processor.analysis.profile_builder.QueryEngine"):
            builder = ProfileBuilder(project_name="test_wiki", min_evidence_count=2)

            assert builder.min_evidence_count == 2

    def test_init_with_custom_confidence_threshold(self):
        """ProfileBuilder should accept custom confidence threshold."""
        from src.processor.analysis.profile_builder import ProfileBuilder

        with patch("src.processor.analysis.profile_builder.QueryEngine"):
            builder = ProfileBuilder(
                project_name="test_wiki",
                relationship_confidence_threshold=0.8
            )

            assert builder.confidence_threshold == 0.8

    def test_init_default_parameters(self):
        """ProfileBuilder should use default parameters when not specified."""
        from src.processor.analysis.profile_builder import ProfileBuilder

        with patch("src.processor.analysis.profile_builder.QueryEngine"):
            builder = ProfileBuilder(project_name="test_wiki")

            assert builder.min_evidence_count == 1
            assert builder.confidence_threshold == 0.6


class TestRelationshipDiscovery:
    """Test relationship discovery via RAG queries."""

    def test_discover_relationships_queries_rag(self):
        """ProfileBuilder should query RAG to discover relationships."""
        from src.processor.analysis.profile_builder import ProfileBuilder

        with patch("src.processor.analysis.profile_builder.QueryEngine") as mock_qe_class:
            mock_qe = MagicMock()
            mock_qe.query_with_citations.return_value = {
                "text": "Katara - friend\nZuko - enemy turned friend",
                "evidence": []
            }
            mock_qe_class.return_value = mock_qe

            builder = ProfileBuilder(project_name="test_wiki")
            relationships = builder._discover_relationships(
                character_name="Aang",
                character_url="wiki/Aang"
            )

            # Should query with character name
            mock_qe.query_with_citations.assert_called_once()
            call_args = mock_qe.query_with_citations.call_args
            assert "Aang" in call_args[1]["query"]

    def test_discover_relationships_parses_response(self):
        """ProfileBuilder should parse relationship list from RAG response."""
        from src.processor.analysis.profile_builder import ProfileBuilder

        with patch("src.processor.analysis.profile_builder.QueryEngine") as mock_qe_class:
            mock_qe = MagicMock()
            mock_qe.query_with_citations.return_value = {
                "text": """1. Katara - romantic partner, close friend
2. Zuko - former enemy, later became friend and ally
3. Sokka - close friend and companion""",
                "evidence": []
            }
            mock_qe_class.return_value = mock_qe

            builder = ProfileBuilder(project_name="test_wiki")
            relationships = builder._discover_relationships("Aang", "wiki/Aang")

            # Should extract relationship candidates
            assert len(relationships) >= 2
            # Should extract character names
            names = [r["target_character"] for r in relationships]
            assert "Katara" in names or "Zuko" in names

    def test_discover_relationships_extracts_types(self):
        """ProfileBuilder should extract relationship types from description."""
        from src.processor.analysis.profile_builder import ProfileBuilder

        with patch("src.processor.analysis.profile_builder.QueryEngine") as mock_qe_class:
            mock_qe = MagicMock()
            mock_qe.query_with_citations.return_value = {
                "text": "Katara - romantic partner\nZuko - enemy turned friend",
                "evidence": []
            }
            mock_qe_class.return_value = mock_qe

            builder = ProfileBuilder(project_name="test_wiki")
            relationships = builder._discover_relationships("Aang", "wiki/Aang")

            # Should extract types
            for rel in relationships:
                assert "relationship_type" in rel


class TestRelationshipDetails:
    """Test detailed relationship building with citations."""

    def test_build_relationship_details_queries_rag(self):
        """ProfileBuilder should query RAG for relationship details."""
        from src.processor.analysis.profile_builder import ProfileBuilder

        with patch("src.processor.analysis.profile_builder.QueryEngine") as mock_qe_class:
            mock_qe = MagicMock()
            mock_qe.query_with_citations.return_value = {
                "text": "They are friends.",
                "evidence": []
            }
            mock_qe_class.return_value = mock_qe

            builder = ProfileBuilder(project_name="test_wiki")
            details = builder._build_relationship_details("Aang", "Zuko", "friendship")

            # Should query with both character names
            mock_qe.query_with_citations.assert_called_once()
            call_args = mock_qe.query_with_citations.call_args
            query = call_args[1]["query"]
            assert "Aang" in query
            assert "Zuko" in query

    def test_build_relationship_details_returns_structure(self):
        """ProfileBuilder should return structured relationship details."""
        from src.processor.analysis.profile_builder import ProfileBuilder

        with patch("src.processor.analysis.profile_builder.QueryEngine") as mock_qe_class:
            mock_qe = MagicMock()
            mock_qe.query_with_citations.return_value = {
                "text": "Aang and Zuko were enemies. Later they became friends.",
                "evidence": [
                    {
                        "cited_text": "Zuko hunted Aang",
                        "source_url": "wiki/Zuko",
                        "page_title": "Zuko",
                        "location": {"start": 0, "end": 20}
                    }
                ]
            }
            mock_qe_class.return_value = mock_qe

            builder = ProfileBuilder(project_name="test_wiki")
            details = builder._build_relationship_details("Aang", "Zuko", "friendship")

            # Should have required fields
            assert "from" in details
            assert "to" in details
            assert "type" in details
            assert "narrative" in details
            assert "overall_confidence" in details
            assert "total_evidence_count" in details

    def test_build_relationship_details_maps_evidence_to_claims(self):
        """ProfileBuilder should map evidence to specific claims."""
        from src.processor.analysis.profile_builder import ProfileBuilder

        with patch("src.processor.analysis.profile_builder.QueryEngine") as mock_qe_class:
            mock_qe = MagicMock()
            mock_qe.query_with_citations.return_value = {
                "text": "They were enemies. They became friends.",
                "evidence": [
                    {
                        "cited_text": "Zuko hunted Aang",
                        "source_url": "wiki/Zuko",
                        "location": {"start": 0, "end": 18}  # Maps to first sentence
                    },
                    {
                        "cited_text": "Zuko joined Team Avatar",
                        "source_url": "wiki/Team",
                        "location": {"start": 20, "end": 42}  # Maps to second sentence
                    }
                ]
            }
            mock_qe_class.return_value = mock_qe

            builder = ProfileBuilder(project_name="test_wiki")
            details = builder._build_relationship_details("Aang", "Zuko", "friendship")

            # Should have claims with evidence
            assert "claims_with_evidence" in details["narrative"]
            claims = details["narrative"]["claims_with_evidence"]

            # Each claim should have evidence
            for claim in claims:
                assert "claim" in claim
                assert "evidence" in claim
                assert isinstance(claim["evidence"], list)

    def test_build_relationship_details_calculates_confidence_per_claim(self):
        """ProfileBuilder should calculate confidence for each claim based on evidence."""
        from src.processor.analysis.profile_builder import ProfileBuilder

        with patch("src.processor.analysis.profile_builder.QueryEngine") as mock_qe_class:
            mock_qe = MagicMock()
            mock_qe.query_with_citations.return_value = {
                "text": "Claim with evidence. Claim without evidence.",
                "evidence": [
                    {
                        "cited_text": "Evidence for first claim",
                        "source_url": "wiki/page",
                        "location": {"start": 0, "end": 20}
                    }
                ]
            }
            mock_qe_class.return_value = mock_qe

            builder = ProfileBuilder(project_name="test_wiki")
            details = builder._build_relationship_details("Aang", "Zuko", "friendship")

            claims = details["narrative"]["claims_with_evidence"]

            # Claims should have confidence scores
            for claim in claims:
                assert "confidence" in claim
                assert 0 <= claim["confidence"] <= 1


class TestNarrativeParsing:
    """Test parsing narrative into claims with evidence."""

    def test_parse_narrative_splits_into_sentences(self):
        """ProfileBuilder should split narrative into sentences."""
        from src.processor.analysis.profile_builder import ProfileBuilder

        with patch("src.processor.analysis.profile_builder.QueryEngine"):
            builder = ProfileBuilder(project_name="test_wiki")

            rag_result = {
                "text": "First sentence. Second sentence. Third sentence.",
                "evidence": []
            }

            parsed = builder._parse_narrative_into_claims(rag_result)

            # Should have text and claims
            assert "text" in parsed["narrative"]
            assert "claims_with_evidence" in parsed["narrative"]

    def test_parse_narrative_maps_evidence_by_location(self):
        """ProfileBuilder should map evidence to claims by character position."""
        from src.processor.analysis.profile_builder import ProfileBuilder

        with patch("src.processor.analysis.profile_builder.QueryEngine"):
            builder = ProfileBuilder(project_name="test_wiki")

            rag_result = {
                "text": "Zuko hunted Aang. Zuko joined Team Avatar.",
                "evidence": [
                    {
                        "cited_text": "Evidence 1",
                        "source_url": "wiki/1",
                        "location": {"start": 0, "end": 17}  # First sentence
                    },
                    {
                        "cited_text": "Evidence 2",
                        "source_url": "wiki/2",
                        "location": {"start": 18, "end": 43}  # Second sentence
                    }
                ]
            }

            parsed = builder._parse_narrative_into_claims(rag_result)
            claims = parsed["narrative"]["claims_with_evidence"]

            # Should have 2 claims with evidence mapped correctly
            assert len(claims) == 2
            assert len(claims[0]["evidence"]) == 1
            assert claims[0]["evidence"][0]["source_url"] == "wiki/1"
            assert len(claims[1]["evidence"]) == 1
            assert claims[1]["evidence"][0]["source_url"] == "wiki/2"

    def test_parse_narrative_handles_overlapping_evidence(self):
        """ProfileBuilder should handle evidence that spans multiple sentences."""
        from src.processor.analysis.profile_builder import ProfileBuilder

        with patch("src.processor.analysis.profile_builder.QueryEngine"):
            builder = ProfileBuilder(project_name="test_wiki")

            rag_result = {
                "text": "First claim. Second claim.",
                "evidence": [
                    {
                        "cited_text": "Evidence spanning both",
                        "source_url": "wiki/page",
                        "location": {"start": 0, "end": 26}  # Spans both sentences
                    }
                ]
            }

            parsed = builder._parse_narrative_into_claims(rag_result)
            claims = parsed["narrative"]["claims_with_evidence"]

            # Evidence should be mapped to the claim it overlaps with most
            assert len(claims) >= 1

    def test_parse_narrative_excludes_claims_without_evidence(self):
        """ProfileBuilder should only include claims that have supporting evidence."""
        from src.processor.analysis.profile_builder import ProfileBuilder

        with patch("src.processor.analysis.profile_builder.QueryEngine"):
            builder = ProfileBuilder(project_name="test_wiki")

            rag_result = {
                "text": "Claim with evidence. Claim without evidence. Another with evidence.",
                "evidence": [
                    {
                        "cited_text": "Evidence 1",
                        "source_url": "wiki/1",
                        "location": {"start": 0, "end": 20}
                    },
                    {
                        "cited_text": "Evidence 2",
                        "source_url": "wiki/2",
                        "location": {"start": 45, "end": 68}
                    }
                ]
            }

            parsed = builder._parse_narrative_into_claims(rag_result)
            claims = parsed["narrative"]["claims_with_evidence"]

            # Should only have claims with evidence (not the middle one)
            for claim in claims:
                assert len(claim["evidence"]) > 0

    def test_parse_narrative_calculates_overall_confidence(self):
        """ProfileBuilder should calculate overall confidence from claim confidences."""
        from src.processor.analysis.profile_builder import ProfileBuilder

        with patch("src.processor.analysis.profile_builder.QueryEngine"):
            builder = ProfileBuilder(project_name="test_wiki")

            rag_result = {
                "text": "First. Second.",
                "evidence": [
                    {"cited_text": "E1", "source_url": "u1", "location": {"start": 0, "end": 6}},
                    {"cited_text": "E2", "source_url": "u2", "location": {"start": 7, "end": 14}}
                ]
            }

            parsed = builder._parse_narrative_into_claims(rag_result)

            assert "overall_confidence" in parsed
            assert 0 <= parsed["overall_confidence"] <= 1


class TestProfileBuilding:
    """Test building complete character profiles."""

    def test_build_profile_for_single_character(self):
        """ProfileBuilder should build profile for a single character."""
        from src.processor.analysis.profile_builder import ProfileBuilder

        with patch("src.processor.analysis.profile_builder.QueryEngine") as mock_qe_class:
            mock_qe = MagicMock()
            # Mock discovery
            mock_qe.query_with_citations.side_effect = [
                {"text": "Katara - friend", "evidence": []},  # Discovery
                {"text": "They are friends.", "evidence": []}  # Details
            ]
            mock_qe_class.return_value = mock_qe

            builder = ProfileBuilder(project_name="test_wiki")

            character = {
                "name": "Aang",
                "source_url": "wiki/Aang",
                "full_name": "Avatar Aang"
            }

            profile = builder.build_profile(character)

            # Should return enhanced profile
            assert "name" in profile
            assert "profile" in profile
            assert "relationships" in profile["profile"]

    def test_build_profile_discovers_and_details_relationships(self):
        """ProfileBuilder should discover relationships and build details for each."""
        from src.processor.analysis.profile_builder import ProfileBuilder

        with patch("src.processor.analysis.profile_builder.QueryEngine") as mock_qe_class:
            mock_qe = MagicMock()
            mock_qe.query_with_citations.side_effect = [
                # Discovery query
                {"text": "Katara - romantic\nZuko - friendship", "evidence": []},
                # Details for Katara
                {"text": "Aang loves Katara.", "evidence": [
                    {"cited_text": "Aang has feelings", "source_url": "wiki/aang", "location": {"start": 0, "end": 18}}
                ]},
                # Details for Zuko
                {"text": "Aang befriended Zuko.", "evidence": [
                    {"cited_text": "They became friends", "source_url": "wiki/zuko", "location": {"start": 0, "end": 21}}
                ]}
            ]
            mock_qe_class.return_value = mock_qe

            builder = ProfileBuilder(project_name="test_wiki")
            character = {"name": "Aang", "source_url": "wiki/Aang"}

            profile = builder.build_profile(character)

            # Should have multiple relationships
            relationships = profile["profile"]["relationships"]
            assert len(relationships) >= 2

    def test_build_profile_includes_metadata(self):
        """ProfileBuilder should include metadata in built profile."""
        from src.processor.analysis.profile_builder import ProfileBuilder

        with patch("src.processor.analysis.profile_builder.QueryEngine") as mock_qe_class:
            mock_qe = MagicMock()
            mock_qe.query_with_citations.return_value = {"text": "No relationships", "evidence": []}
            mock_qe_class.return_value = mock_qe

            builder = ProfileBuilder(project_name="test_wiki")
            character = {"name": "Aang", "source_url": "wiki/Aang"}

            profile = builder.build_profile(character)

            # Should include metadata
            assert "total_relationships" in profile["profile"]
            assert "profile_built_at" in profile["profile"]


class TestBatchProcessing:
    """Test building profiles for multiple characters."""

    def test_build_all_profiles_processes_all_characters(self):
        """ProfileBuilder should build profiles for all provided characters."""
        from src.processor.analysis.profile_builder import ProfileBuilder

        with patch("src.processor.analysis.profile_builder.QueryEngine") as mock_qe_class:
            mock_qe = MagicMock()
            mock_qe.query_with_citations.return_value = {"text": "None", "evidence": []}
            mock_qe_class.return_value = mock_qe

            builder = ProfileBuilder(project_name="test_wiki")

            characters = [
                {"name": "Aang", "source_url": "wiki/Aang"},
                {"name": "Katara", "source_url": "wiki/Katara"},
                {"name": "Zuko", "source_url": "wiki/Zuko"}
            ]

            profiles = builder.build_all_profiles(characters, save=False)

            # Should return profiles for all characters
            assert len(profiles) == 3
            assert "Aang" in profiles
            assert "Katara" in profiles
            assert "Zuko" in profiles

    def test_build_all_profiles_with_save(self):
        """ProfileBuilder should save profiles when save=True."""
        from src.processor.analysis.profile_builder import ProfileBuilder

        with patch("src.processor.analysis.profile_builder.QueryEngine") as mock_qe_class, \
             patch.object(ProfileBuilder, "save_profiles") as mock_save:

            mock_qe = MagicMock()
            mock_qe.query_with_citations.return_value = {"text": "None", "evidence": []}
            mock_qe_class.return_value = mock_qe

            builder = ProfileBuilder(project_name="test_wiki")
            characters = [{"name": "Aang", "source_url": "wiki/Aang"}]

            profiles = builder.build_all_profiles(characters, save=True)

            # Should call save_profiles
            mock_save.assert_called_once_with(profiles)


class TestProfilePersistence:
    """Test saving profiles and relationship graph."""

    def test_save_profiles_creates_directories(self):
        """ProfileBuilder should create necessary directories."""
        from src.processor.analysis.profile_builder import ProfileBuilder
        from pathlib import Path

        with patch("src.processor.analysis.profile_builder.QueryEngine"):
            builder = ProfileBuilder(project_name="test_wiki")

            # Mock Path.mkdir to track calls
            with patch.object(Path, "mkdir") as mock_mkdir, \
                 patch("builtins.open", mock_open()):

                profiles = {
                    "Aang": {
                        "name": "Aang",
                        "full_name": "Avatar Aang",
                        "profile": {"relationships": [], "total_relationships": 0}
                    }
                }

                builder.save_profiles(profiles)

                # Should have called mkdir for directories
                assert mock_mkdir.call_count >= 2  # characters_dir and relationships_dir

    def test_save_profiles_writes_character_files(self):
        """ProfileBuilder should write JSON files for each character."""
        from src.processor.analysis.profile_builder import ProfileBuilder
        from pathlib import Path

        with patch("src.processor.analysis.profile_builder.QueryEngine"):
            builder = ProfileBuilder(project_name="test_wiki")

            written_files = {}

            def mock_open_func(filepath, mode="r", encoding=None):
                """Track what files are opened for writing."""
                m = mock_open()()
                # Capture writes
                original_write = m.write

                def capture_write(data):
                    written_files[str(filepath)] = data
                    return original_write(data)

                m.write = capture_write
                return m

            with patch.object(Path, "mkdir"), \
                 patch("builtins.open", side_effect=mock_open_func):

                profiles = {
                    "Aang": {
                        "name": "Aang",
                        "full_name": "Avatar Aang",
                        "profile": {"relationships": [], "total_relationships": 0}
                    }
                }

                builder.save_profiles(profiles)

                # Should have written at least 2 files (character + graph)
                assert len(written_files) >= 2

                # Should have written Aang's profile
                aang_files = [f for f in written_files.keys() if "Aang" in f or "Avatar Aang" in f]
                assert len(aang_files) > 0

    def test_build_relationship_graph_structure(self):
        """ProfileBuilder relationship graph should have correct structure."""
        from src.processor.analysis.profile_builder import ProfileBuilder

        with patch("src.processor.analysis.profile_builder.QueryEngine"):
            builder = ProfileBuilder(project_name="test_wiki")

            profiles = {
                "Aang": {
                    "name": "Aang",
                    "full_name": "Avatar Aang",
                    "source_url": "wiki/Aang",
                    "profile": {
                        "total_relationships": 1,
                        "relationships": [
                            {
                                "target": "Katara",
                                "type": "romantic",
                                "summary": "Close relationship",
                                "overall_confidence": 0.9,
                                "total_evidence_count": 5
                            }
                        ]
                    }
                }
            }

            graph = builder._build_relationship_graph(profiles)

            # Should have nodes, edges, and metadata
            assert "nodes" in graph
            assert "edges" in graph
            assert "metadata" in graph

            # Nodes should include character info
            assert len(graph["nodes"]) == 1
            assert graph["nodes"][0]["id"] == "Aang"

            # Edges should include relationship info
            assert len(graph["edges"]) == 1
            assert graph["edges"][0]["from"] == "Aang"
            assert graph["edges"][0]["to"] == "Katara"

            # Metadata should have project info
            assert graph["metadata"]["project_name"] == "test_wiki"
            assert graph["metadata"]["total_characters"] == 1
            assert graph["metadata"]["total_relationships"] == 1
