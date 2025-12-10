"""
Unit tests for CharacterKnowledgeBuilder tool executors.

Tests each of the 9 tools:
- search_characters: Fuzzy character search
- create_character: Create new character entry
- update_character: Update existing character
- get_character: Retrieve character data
- create_relationship: Create new relationship (validates both characters exist)
- get_relationship: Retrieve relationship data
- add_relationship_claim: Add evidence to relationship
- search_wiki: RAG-based wiki search
- add_affiliation: Add group/organization membership to character

NOTE: All tools now require a 'canon' parameter to support multi-canon wikis.
The default canon used in tests is 'main'.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
from src.processor.analysis.knowledge_builder import CharacterKnowledgeBuilder

# Default test canon
TEST_CANON = "main"


@pytest.fixture
def mock_builder():
    """Create a mocked CharacterKnowledgeBuilder for testing."""
    with patch("src.processor.analysis.knowledge_builder.QueryEngine"), \
         patch("src.processor.analysis.knowledge_builder.load_system_prompt") as mock_prompt, \
         patch("src.processor.analysis.knowledge_builder.load_tool_schemas") as mock_schemas:

        mock_prompt.return_value = "Test prompt"
        mock_schemas.return_value = []

        builder = CharacterKnowledgeBuilder(project_name="test")
        # Ensure the default canon exists in knowledge base
        builder.knowledge_base["characters"][TEST_CANON] = {}
        builder.knowledge_base["relationships"][TEST_CANON] = {}
        return builder


@pytest.mark.unit
class TestSearchCharactersTool:
    """Test _tool_search_characters fuzzy matching."""

    def test_search_returns_exact_match(self, mock_builder):
        """Should return exact name match with similarity 1.0."""
        mock_builder.knowledge_base["characters"][TEST_CANON] = {
            "Aang": {"name": "Aang", "aliases": ["Avatar Aang"]}
        }

        result = mock_builder._tool_search_characters("Aang", canon=TEST_CANON)

        assert result["count"] == 1
        assert result["matches"][0]["name"] == "Aang"
        assert result["matches"][0]["similarity"] == 1.0

    def test_search_returns_fuzzy_match(self, mock_builder):
        """Should return fuzzy match with similarity > 0.6."""
        mock_builder.knowledge_base["characters"][TEST_CANON] = {
            "Katara": {"name": "Katara", "aliases": []}
        }

        result = mock_builder._tool_search_characters("Katare", canon=TEST_CANON)  # Small typo

        assert result["count"] == 1
        assert result["matches"][0]["name"] == "Katara"
        assert result["matches"][0]["similarity"] > 0.6

    def test_search_matches_alias(self, mock_builder):
        """Should match character by alias."""
        mock_builder.knowledge_base["characters"][TEST_CANON] = {
            "Aang": {"name": "Aang", "aliases": ["The Last Airbender", "Avatar"]}
        }

        result = mock_builder._tool_search_characters("Last Airbender", canon=TEST_CANON)

        assert result["count"] == 1
        assert result["matches"][0]["name"] == "Aang"

    def test_search_returns_multiple_matches(self, mock_builder):
        """Should return all matches above threshold."""
        mock_builder.knowledge_base["characters"][TEST_CANON] = {
            "Aang": {"name": "Aang", "aliases": ["Avatar Aang"]},
            "Avatar Korra": {"name": "Avatar Korra", "aliases": []}
        }

        result = mock_builder._tool_search_characters("Avatar", canon=TEST_CANON)

        assert result["count"] >= 1  # At least one match

    def test_search_returns_empty_for_no_query(self, mock_builder):
        """Should return empty results for empty query."""
        result = mock_builder._tool_search_characters("", canon=TEST_CANON)

        assert result["count"] == 0
        assert result["matches"] == []

    def test_search_returns_empty_for_no_matches(self, mock_builder):
        """Should return empty for query with no matches."""
        mock_builder.knowledge_base["characters"][TEST_CANON] = {
            "Aang": {"name": "Aang", "aliases": []}
        }

        result = mock_builder._tool_search_characters("Zzzzzz", canon=TEST_CANON)

        assert result["count"] == 0
        assert result["matches"] == []


@pytest.mark.unit
class TestCreateCharacterTool:
    """Test _tool_create_character functionality."""

    def test_create_character_success(self, mock_builder):
        """Should create new character successfully."""
        result = mock_builder._tool_create_character(
            name="Aang",
            canon=TEST_CANON,
            aliases=["Avatar Aang"],
            bio="The last airbender",
            source_url="https://example.com/aang"
        )

        assert result["success"] is True
        assert result["name"] == "Aang"
        assert "Aang" in mock_builder.knowledge_base["characters"][TEST_CANON]

    def test_create_character_stores_data(self, mock_builder):
        """Should store all character data correctly."""
        mock_builder._tool_create_character(
            name="Aang",
            canon=TEST_CANON,
            aliases=["Avatar Aang", "The Last Airbender"],
            bio="Test bio",
            source_url="https://example.com"
        )

        char = mock_builder.knowledge_base["characters"][TEST_CANON]["Aang"]
        assert char["name"] == "Aang"
        assert char["aliases"] == ["Avatar Aang", "The Last Airbender"]
        assert char["bio"] == "Test bio"
        assert "https://example.com" in char["source_urls"]
        assert "created_at" in char

    def test_create_character_rejects_duplicate(self, mock_builder):
        """Should reject duplicate character creation."""
        mock_builder._tool_create_character(
            name="Aang",
            canon=TEST_CANON,
            aliases=[],
            bio="Test",
            source_url="https://example.com"
        )

        result = mock_builder._tool_create_character(
            name="Aang",
            canon=TEST_CANON,
            aliases=[],
            bio="Test2",
            source_url="https://example.com"
        )

        assert result["success"] is False
        assert "already exists" in result["error"]

    def test_create_character_requires_name(self, mock_builder):
        """Should require name parameter."""
        result = mock_builder._tool_create_character(
            name="",
            canon=TEST_CANON,
            aliases=[],
            bio="Test",
            source_url="https://example.com"
        )

        assert result["success"] is False
        assert "required" in result["error"].lower()


@pytest.mark.unit
class TestUpdateCharacterTool:
    """Test _tool_update_character functionality."""

    def test_update_adds_source_url(self, mock_builder):
        """Should add new source URL to existing character."""
        mock_builder.knowledge_base["characters"][TEST_CANON]["Aang"] = {
            "name": "Aang",
            "aliases": [],
            "source_urls": ["https://example.com/1"]
        }

        result = mock_builder._tool_update_character(
            name="Aang",
            canon=TEST_CANON,
            add_source_url="https://example.com/2"
        )

        assert result["success"] is True
        assert result["source_url_count"] == 2
        char = mock_builder.knowledge_base["characters"][TEST_CANON]["Aang"]
        assert "https://example.com/2" in char["source_urls"]

    def test_update_adds_aliases(self, mock_builder):
        """Should add new aliases to character."""
        mock_builder.knowledge_base["characters"][TEST_CANON]["Aang"] = {
            "name": "Aang",
            "aliases": ["Avatar Aang"],
            "source_urls": []
        }

        result = mock_builder._tool_update_character(
            name="Aang",
            canon=TEST_CANON,
            add_aliases=["The Last Airbender"]
        )

        assert result["success"] is True
        assert "The Last Airbender" in result["aliases"]
        char = mock_builder.knowledge_base["characters"][TEST_CANON]["Aang"]
        assert "The Last Airbender" in char["aliases"]
        assert "Avatar Aang" in char["aliases"]  # Preserves existing

    def test_update_updates_bio(self, mock_builder):
        """Should update character biography."""
        mock_builder.knowledge_base["characters"][TEST_CANON]["Aang"] = {
            "name": "Aang",
            "aliases": [],
            "bio": "Old bio",
            "source_urls": []
        }

        result = mock_builder._tool_update_character(
            name="Aang",
            canon=TEST_CANON,
            bio="New bio"
        )

        assert result["success"] is True
        char = mock_builder.knowledge_base["characters"][TEST_CANON]["Aang"]
        assert char["bio"] == "New bio"

    def test_update_prevents_duplicate_urls(self, mock_builder):
        """Should not add duplicate source URLs."""
        mock_builder.knowledge_base["characters"][TEST_CANON]["Aang"] = {
            "name": "Aang",
            "aliases": [],
            "source_urls": ["https://example.com"]
        }

        result = mock_builder._tool_update_character(
            name="Aang",
            canon=TEST_CANON,
            add_source_url="https://example.com"
        )

        assert result["source_url_count"] == 1  # No duplicate

    def test_update_returns_error_for_nonexistent(self, mock_builder):
        """Should return error for nonexistent character."""
        result = mock_builder._tool_update_character(
            name="Nonexistent",
            canon=TEST_CANON,
            bio="Test"
        )

        assert result["success"] is False
        assert "not found" in result["error"]


@pytest.mark.unit
class TestGetCharacterTool:
    """Test _tool_get_character functionality."""

    def test_get_character_returns_data(self, mock_builder):
        """Should return character data."""
        mock_builder.knowledge_base["characters"][TEST_CANON]["Aang"] = {
            "name": "Aang",
            "aliases": ["Avatar Aang"],
            "bio": "The last airbender",
            "source_urls": ["https://example.com"]
        }

        result = mock_builder._tool_get_character("Aang", canon=TEST_CANON)

        assert result["name"] == "Aang"
        assert result["aliases"] == ["Avatar Aang"]
        assert result["bio"] == "The last airbender"

    def test_get_character_returns_none_for_nonexistent(self, mock_builder):
        """Should return None for nonexistent character."""
        result = mock_builder._tool_get_character("Nonexistent", canon=TEST_CANON)

        assert result is None


@pytest.mark.unit
class TestCreateRelationshipTool:
    """Test _tool_create_relationship functionality."""

    def test_create_relationship_success(self, mock_builder):
        """Should create new relationship successfully when both characters exist."""
        # Setup: characters must exist first
        mock_builder.knowledge_base["characters"][TEST_CANON]["Aang"] = {"name": "Aang"}
        mock_builder.knowledge_base["characters"][TEST_CANON]["Katara"] = {"name": "Katara"}

        result = mock_builder._tool_create_relationship(
            character_a="Aang",
            character_b="Katara",
            canon=TEST_CANON,
            relationship_type="friend",
            summary="They are friends"
        )

        assert result["success"] is True
        assert set(result["characters"]) == {"Aang", "Katara"}
        assert result["type"] == "friend"
        assert result["claim_count"] == 0

    def test_create_relationship_normalizes_order(self, mock_builder):
        """Should normalize character order alphabetically."""
        mock_builder.knowledge_base["characters"][TEST_CANON]["Aang"] = {"name": "Aang"}
        mock_builder.knowledge_base["characters"][TEST_CANON]["Zuko"] = {"name": "Zuko"}

        mock_builder._tool_create_relationship(
            character_a="Zuko",
            character_b="Aang",
            canon=TEST_CANON,
            relationship_type="enemy",
            summary="Enemies"
        )

        # Should be stored as (Aang, Zuko) due to alphabetical order
        key = ("Aang", "Zuko")
        assert key in mock_builder.knowledge_base["relationships"][TEST_CANON]

    def test_create_relationship_stores_data(self, mock_builder):
        """Should store all relationship data."""
        mock_builder.knowledge_base["characters"][TEST_CANON]["Aang"] = {"name": "Aang"}
        mock_builder.knowledge_base["characters"][TEST_CANON]["Katara"] = {"name": "Katara"}

        mock_builder._tool_create_relationship(
            character_a="Aang",
            character_b="Katara",
            canon=TEST_CANON,
            relationship_type="friend",
            summary="Best friends"
        )

        key = ("Aang", "Katara")
        rel = mock_builder.knowledge_base["relationships"][TEST_CANON][key]
        assert rel["type"] == "friend"
        assert rel["summary"] == "Best friends"
        assert rel["claims"] == []
        assert "created_at" in rel

    def test_create_relationship_rejects_duplicate(self, mock_builder):
        """Should reject duplicate relationship."""
        mock_builder.knowledge_base["characters"][TEST_CANON]["Aang"] = {"name": "Aang"}
        mock_builder.knowledge_base["characters"][TEST_CANON]["Katara"] = {"name": "Katara"}

        mock_builder._tool_create_relationship(
            character_a="Aang",
            character_b="Katara",
            canon=TEST_CANON,
            relationship_type="friend",
            summary="Test"
        )

        result = mock_builder._tool_create_relationship(
            character_a="Aang",
            character_b="Katara",
            canon=TEST_CANON,
            relationship_type="ally",
            summary="Test2"
        )

        assert result["success"] is False
        assert "already exists" in result["error"]

    def test_create_relationship_fails_if_character_a_missing(self, mock_builder):
        """Should fail if character_a doesn't exist."""
        mock_builder.knowledge_base["characters"][TEST_CANON]["Katara"] = {"name": "Katara"}

        result = mock_builder._tool_create_relationship(
            character_a="NonexistentPerson",
            character_b="Katara",
            canon=TEST_CANON,
            relationship_type="friend",
            summary="Test"
        )

        assert result["success"] is False
        assert "not found" in result["error"]
        assert "NonexistentPerson" in result["error"]
        assert "hint" in result

    def test_create_relationship_fails_if_character_b_missing(self, mock_builder):
        """Should fail if character_b doesn't exist."""
        mock_builder.knowledge_base["characters"][TEST_CANON]["Aang"] = {"name": "Aang"}

        result = mock_builder._tool_create_relationship(
            character_a="Aang",
            character_b="Kyoshi Warriors",  # This is a group, not a character
            canon=TEST_CANON,
            relationship_type="member",
            summary="Test"
        )

        assert result["success"] is False
        assert "not found" in result["error"]
        assert "Kyoshi Warriors" in result["error"]
        assert "add_affiliation" in result["hint"]

    def test_create_relationship_fails_if_both_missing(self, mock_builder):
        """Should fail and list both missing characters."""
        result = mock_builder._tool_create_relationship(
            character_a="Nobody",
            character_b="AlsoNobody",
            canon=TEST_CANON,
            relationship_type="friend",
            summary="Test"
        )

        assert result["success"] is False
        assert "Nobody" in result["error"]
        assert "AlsoNobody" in result["error"]


@pytest.mark.unit
class TestAddRelationshipClaimTool:
    """Test _tool_add_relationship_claim functionality."""

    def test_add_claim_to_new_relationship(self, mock_builder):
        """Should add claim to existing relationship."""
        mock_builder.knowledge_base["relationships"][TEST_CANON][("Aang", "Katara")] = {
            "characters": ["Aang", "Katara"],
            "type": "friend",
            "summary": "Friends",
            "claims": []
        }

        result = mock_builder._tool_add_relationship_claim(
            character_a="Aang",
            character_b="Katara",
            canon=TEST_CANON,
            claim="They met in an iceberg",
            evidence_url="https://example.com",
            evidence_text="Katara found Aang in an iceberg"
        )

        assert result["success"] is True
        assert result["claim_count"] == 1
        assert result["evidence_count"] == 1
        assert "updated_claim" in result
        assert result["updated_claim"]["claim"] == "They met in an iceberg"

    def test_add_claim_creates_evidence_array(self, mock_builder):
        """Should create evidence array for new claim."""
        mock_builder.knowledge_base["relationships"][TEST_CANON][("Aang", "Katara")] = {
            "characters": ["Aang", "Katara"],
            "type": "friend",
            "claims": []
        }

        mock_builder._tool_add_relationship_claim(
            character_a="Aang",
            character_b="Katara",
            canon=TEST_CANON,
            claim="Test claim",
            evidence_url="https://example.com",
            evidence_text="Test evidence"
        )

        key = ("Aang", "Katara")
        rel = mock_builder.knowledge_base["relationships"][TEST_CANON][key]
        assert len(rel["claims"]) == 1
        assert "evidence" in rel["claims"][0]
        assert isinstance(rel["claims"][0]["evidence"], list)

    def test_add_evidence_to_existing_claim(self, mock_builder):
        """Should add evidence to existing claim."""
        mock_builder.knowledge_base["relationships"][TEST_CANON][("Aang", "Katara")] = {
            "characters": ["Aang", "Katara"],
            "type": "friend",
            "claims": [
                {
                    "claim": "They met in an iceberg",
                    "evidence": [
                        {
                            "evidence_url": "https://example.com/1",
                            "evidence_text": "First evidence",
                            "added_at": "2025-01-01T00:00:00Z"
                        }
                    ]
                }
            ]
        }

        result = mock_builder._tool_add_relationship_claim(
            character_a="Aang",
            character_b="Katara",
            canon=TEST_CANON,
            claim="They met in an iceberg",
            evidence_url="https://example.com/2",
            evidence_text="Second evidence"
        )

        assert result["success"] is True
        assert result["evidence_count"] == 2
        assert len(result["updated_claim"]["evidence"]) == 2

    def test_add_claim_truncates_evidence_text(self, mock_builder):
        """Should truncate evidence text to 200 characters."""
        mock_builder.knowledge_base["relationships"][TEST_CANON][("Aang", "Katara")] = {
            "characters": ["Aang", "Katara"],
            "type": "friend",
            "claims": []
        }

        long_text = "x" * 300

        mock_builder._tool_add_relationship_claim(
            character_a="Aang",
            character_b="Katara",
            canon=TEST_CANON,
            claim="Test",
            evidence_url="https://example.com",
            evidence_text=long_text
        )

        key = ("Aang", "Katara")
        evidence = mock_builder.knowledge_base["relationships"][TEST_CANON][key]["claims"][0]["evidence"][0]
        assert len(evidence["evidence_text"]) == 200

    def test_add_claim_returns_error_for_nonexistent_relationship(self, mock_builder):
        """Should return error if relationship doesn't exist."""
        result = mock_builder._tool_add_relationship_claim(
            character_a="Aang",
            character_b="Nobody",
            canon=TEST_CANON,
            claim="Test",
            evidence_url="https://example.com",
            evidence_text="Test"
        )

        assert result["success"] is False
        assert "not found" in result["error"]


@pytest.mark.unit
class TestGetRelationshipTool:
    """Test _tool_get_relationship functionality."""

    def test_get_relationship_returns_data(self, mock_builder):
        """Should return complete relationship data."""
        mock_builder.knowledge_base["relationships"][TEST_CANON][("Aang", "Katara")] = {
            "characters": ["Aang", "Katara"],
            "type": "friend",
            "summary": "Best friends",
            "claims": [
                {
                    "claim": "They met in an iceberg",
                    "evidence": [
                        {
                            "evidence_url": "https://example.com",
                            "evidence_text": "Test evidence",
                            "added_at": "2025-01-01T00:00:00Z"
                        }
                    ]
                }
            ]
        }

        result = mock_builder._tool_get_relationship("Aang", "Katara", canon=TEST_CANON)

        assert result["type"] == "friend"
        assert result["summary"] == "Best friends"
        assert len(result["claims"]) == 1
        assert result["claims"][0]["claim"] == "They met in an iceberg"

    def test_get_relationship_returns_null_for_nonexistent(self, mock_builder):
        """Should return null for nonexistent relationship."""
        result = mock_builder._tool_get_relationship("Aang", "Nobody", canon=TEST_CANON)

        assert result is None


@pytest.mark.unit
class TestSearchWikiTool:
    """Test _tool_search_wiki RAG functionality."""

    def test_search_wiki_calls_query_engine(self, mock_builder):
        """Should call query engine with correct parameters."""
        mock_builder.query_engine.query_with_citations = Mock(return_value={
            "evidence": [
                {
                    "cited_text": "Test result",
                    "url": "https://example.com",
                    "page_title": "Test Page"
                }
            ],
            "text": "Summary text"
        })

        result = mock_builder._tool_search_wiki("test query", max_results=3)

        mock_builder.query_engine.query_with_citations.assert_called_once_with(
            query="test query",
            k=3
        )
        assert result["count"] == 1
        assert len(result["results"]) == 1

    def test_search_wiki_returns_empty_for_no_query(self, mock_builder):
        """Should return empty results for empty query."""
        result = mock_builder._tool_search_wiki("")

        assert result["count"] == 0
        assert result["results"] == []

    def test_search_wiki_handles_errors(self, mock_builder):
        """Should handle query engine errors gracefully."""
        mock_builder.query_engine.query_with_citations = Mock(
            side_effect=Exception("Test error")
        )

        result = mock_builder._tool_search_wiki("test query")

        assert "error" in result
        assert result["count"] == 0
        assert result["results"] == []


@pytest.mark.unit
class TestAddAffiliationTool:
    """Test _tool_add_affiliation functionality."""

    def test_add_affiliation_success(self, mock_builder):
        """Should add affiliation to existing character."""
        mock_builder.knowledge_base["characters"][TEST_CANON]["Suki"] = {
            "name": "Suki",
            "aliases": [],
            "source_urls": []
        }

        result = mock_builder._tool_add_affiliation(
            character_name="Suki",
            canon=TEST_CANON,
            group="Kyoshi Warriors",
            role="Leader",
            evidence_url="https://example.com/suki",
            evidence_text="Suki is the leader of the Kyoshi Warriors"
        )

        assert result["success"] is True
        assert result["character_name"] == "Suki"
        assert result["affiliation_count"] == 1
        assert len(result["current_affiliations"]) == 1
        assert result["current_affiliations"][0]["group"] == "Kyoshi Warriors"
        assert result["current_affiliations"][0]["role"] == "Leader"

    def test_add_affiliation_stores_data(self, mock_builder):
        """Should store affiliation data in character record."""
        mock_builder.knowledge_base["characters"][TEST_CANON]["Aang"] = {
            "name": "Aang",
            "aliases": [],
            "source_urls": []
        }

        mock_builder._tool_add_affiliation(
            character_name="Aang",
            canon=TEST_CANON,
            group="Air Acolytes",
            role="Founder",
            evidence_url="https://example.com/aang",
            evidence_text="Aang founded the Air Acolytes"
        )

        char = mock_builder.knowledge_base["characters"][TEST_CANON]["Aang"]
        assert "affiliations" in char
        assert len(char["affiliations"]) == 1
        aff = char["affiliations"][0]
        assert aff["group"] == "Air Acolytes"
        assert aff["role"] == "Founder"
        assert aff["evidence_url"] == "https://example.com/aang"
        assert "updated_at" in char

    def test_add_affiliation_without_role(self, mock_builder):
        """Should add affiliation without role specified."""
        mock_builder.knowledge_base["characters"][TEST_CANON]["Zuko"] = {
            "name": "Zuko",
            "aliases": [],
            "source_urls": []
        }

        result = mock_builder._tool_add_affiliation(
            character_name="Zuko",
            canon=TEST_CANON,
            group="Team Avatar",
            evidence_url="https://example.com/zuko",
            evidence_text="Zuko joined Team Avatar"
        )

        assert result["success"] is True
        assert result["current_affiliations"][0]["role"] is None

    def test_add_affiliation_detects_duplicate(self, mock_builder):
        """Should detect duplicate affiliation (case-insensitive)."""
        mock_builder.knowledge_base["characters"][TEST_CANON]["Suki"] = {
            "name": "Suki",
            "aliases": [],
            "source_urls": [],
            "affiliations": [
                {
                    "group": "Kyoshi Warriors",
                    "role": "Member",
                    "evidence_url": "https://old.com",
                    "evidence_text": "Old evidence"
                }
            ]
        }

        result = mock_builder._tool_add_affiliation(
            character_name="Suki",
            canon=TEST_CANON,
            group="kyoshi warriors",  # Different case
            role="Member",
            evidence_url="https://new.com",
            evidence_text="New evidence"
        )

        assert result["success"] is True
        assert "already exists" in result["message"]
        assert result["affiliation_count"] == 1  # Still just one

    def test_add_affiliation_updates_role(self, mock_builder):
        """Should update role if different from existing."""
        mock_builder.knowledge_base["characters"][TEST_CANON]["Suki"] = {
            "name": "Suki",
            "aliases": [],
            "source_urls": [],
            "affiliations": [
                {
                    "group": "Kyoshi Warriors",
                    "role": "Member",
                    "evidence_url": "https://old.com",
                    "evidence_text": "Old evidence"
                }
            ]
        }

        result = mock_builder._tool_add_affiliation(
            character_name="Suki",
            canon=TEST_CANON,
            group="Kyoshi Warriors",
            role="Leader",  # Updated role
            evidence_url="https://new.com",
            evidence_text="Suki became the leader"
        )

        assert result["success"] is True
        assert "role updated" in result["message"]
        # Check the stored data was updated
        char = mock_builder.knowledge_base["characters"][TEST_CANON]["Suki"]
        assert char["affiliations"][0]["role"] == "Leader"
        assert char["affiliations"][0]["evidence_url"] == "https://new.com"

    def test_add_affiliation_multiple_groups(self, mock_builder):
        """Should allow multiple affiliations per character."""
        mock_builder.knowledge_base["characters"][TEST_CANON]["Zuko"] = {
            "name": "Zuko",
            "aliases": [],
            "source_urls": []
        }

        mock_builder._tool_add_affiliation(
            character_name="Zuko",
            canon=TEST_CANON,
            group="Fire Nation",
            role="Prince",
            evidence_url="https://example.com/1",
            evidence_text="Zuko is prince of Fire Nation"
        )

        result = mock_builder._tool_add_affiliation(
            character_name="Zuko",
            canon=TEST_CANON,
            group="Team Avatar",
            role="Member",
            evidence_url="https://example.com/2",
            evidence_text="Zuko joined Team Avatar"
        )

        assert result["success"] is True
        assert result["affiliation_count"] == 2
        groups = [a["group"] for a in result["current_affiliations"]]
        assert "Fire Nation" in groups
        assert "Team Avatar" in groups

    def test_add_affiliation_fails_for_nonexistent_character(self, mock_builder):
        """Should fail if character doesn't exist."""
        result = mock_builder._tool_add_affiliation(
            character_name="Nonexistent",
            canon=TEST_CANON,
            group="Some Group",
            evidence_url="https://example.com",
            evidence_text="Test"
        )

        assert result["success"] is False
        assert "not found" in result["error"]
        assert "create_character" in result["error"]

    def test_add_affiliation_truncates_long_evidence(self, mock_builder):
        """Should truncate evidence text to 200 characters."""
        mock_builder.knowledge_base["characters"][TEST_CANON]["Aang"] = {
            "name": "Aang",
            "aliases": [],
            "source_urls": []
        }

        long_text = "A" * 300  # 300 characters

        mock_builder._tool_add_affiliation(
            character_name="Aang",
            canon=TEST_CANON,
            group="Test Group",
            evidence_url="https://example.com",
            evidence_text=long_text
        )

        char = mock_builder.knowledge_base["characters"][TEST_CANON]["Aang"]
        assert len(char["affiliations"][0]["evidence_text"]) == 200
