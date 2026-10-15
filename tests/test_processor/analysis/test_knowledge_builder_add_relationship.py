"""
Tests for the add_relationship tool (create-or-add, evidence required).

add_relationship replaces create_relationship + add_relationship_claim:
every call carries a claim with an exact quote, so a relationship can never
exist without verified evidence, and calling it for an existing relationship
adds the claim instead of failing.
"""

from unittest.mock import patch

import pytest

from src.processor.analysis.knowledge_builder import CharacterKnowledgeBuilder

pytestmark = pytest.mark.unit

CANON = "main"
URL = "https://avatar.fandom.com/wiki/Aang"
PAGE = {
    "main_content": "Aang married Katara after the war . They had three children. "
    "Katara and her brother Sokka found Aang in an iceberg.",
    "infobox_data": {"Love interest": "Katara(wife)", "Enemies": "Azula,Ozai"},
}


@pytest.fixture
def builder():
    with (
        patch("src.processor.analysis.knowledge_builder.QueryEngine"),
        patch(
            "src.processor.analysis.knowledge_builder.load_system_prompt",
            return_value="Test prompt",
        ),
        patch(
            "src.processor.analysis.knowledge_builder.load_tool_schemas",
            return_value=[],
        ),
    ):
        b = CharacterKnowledgeBuilder(project_name="test")
    b.knowledge_base["characters"] = {CANON: {}}
    b.knowledge_base["relationships"] = {CANON: {}}
    for name in ("Aang", "Katara", "Sokka", "Ozai", "Bumi", "King Bumi"):
        b.knowledge_base["characters"][CANON][name] = {"name": name, "aliases": []}
    b.page_texts = {URL: b._quotable_text(PAGE)}
    b.current_page_url = URL
    return b


def add(builder, **overrides):
    args = {
        "character_a": "Aang",
        "character_b": "Katara",
        "canon": CANON,
        "relationship_type": "romantic_partner",
        "summary": "Aang and Katara married.",
        "claim": "Aang married Katara",
        "evidence_url": URL,
        "evidence_text": "Aang married Katara after the war",
    }
    args.update(overrides)
    return builder._tool_add_relationship(**args)


def rels(builder):
    return builder.knowledge_base["relationships"][CANON]


class TestCreatesNewRelationship:
    def test_creates_relationship_with_its_first_claim(self, builder):
        result = add(builder)

        assert result["success"] is True
        assert result["created"] is True
        rel = rels(builder)[("Aang", "Katara")]
        assert rel["type"] == "romantic_partner"
        assert rel["summary"] == "Aang and Katara married."
        assert rel["claims"][0]["claim"] == "Aang married Katara"
        assert rel["claims"][0]["evidence"][0]["evidence_url"] == URL

    def test_normalizes_character_order(self, builder):
        add(builder, character_a="Katara", character_b="Aang")

        assert ("Aang", "Katara") in rels(builder)

    def test_summary_defaults_to_claim(self, builder):
        add(builder, summary="")

        assert rels(builder)[("Aang", "Katara")]["summary"] == "Aang married Katara"

    def test_truncates_stored_evidence_to_200_chars(self, builder):
        builder.page_texts[URL] += builder._normalize_quote("x" * 300)

        add(builder, evidence_text="x" * 300)

        evidence = rels(builder)[("Aang", "Katara")]["claims"][0]["evidence"][0]
        assert len(evidence["evidence_text"]) == 200


class TestAddsToExistingRelationship:
    def test_existing_relationship_gets_new_claim_not_error(self, builder):
        add(builder)

        result = add(
            builder,
            relationship_type="family",
            claim="Aang and Katara had three children",
            evidence_text="They had three children",
        )

        assert result["success"] is True
        assert result["created"] is False
        rel = rels(builder)[("Aang", "Katara")]
        assert len(rel["claims"]) == 2

    def test_existing_type_and_summary_are_kept_and_reported(self, builder):
        add(builder)

        result = add(
            builder,
            relationship_type="family",
            summary="Different summary",
            claim="Aang and Katara had three children",
            evidence_text="They had three children",
        )

        rel = rels(builder)[("Aang", "Katara")]
        assert rel["type"] == "romantic_partner"
        assert rel["summary"] == "Aang and Katara married."
        assert result["type"] == "romantic_partner"
        assert result["summary"] == "Aang and Katara married."
        assert "romantic_partner" in result["note"]

    def test_response_lists_existing_claims(self, builder):
        add(builder)

        result = add(
            builder,
            claim="Aang and Katara had three children",
            evidence_text="They had three children",
        )

        assert result["claims"] == [
            "Aang married Katara",
            "Aang and Katara had three children",
        ]

    def test_same_claim_text_appends_evidence(self, builder):
        add(builder)

        result = add(builder, evidence_text="Love interest: Katara (wife)")

        claims = rels(builder)[("Aang", "Katara")]["claims"]
        assert len(claims) == 1
        assert len(claims[0]["evidence"]) == 2
        assert len(result["updated_claim"]["evidence"]) == 2


class TestEvidenceIsRequired:
    def test_paraphrase_creates_nothing(self, builder):
        result = add(builder, evidence_text="Aang and Katara got married")

        assert result["success"] is False
        assert "exact" in result["error"]
        assert rels(builder) == {}

    def test_rejected_quote_does_not_change_existing_relationship(self, builder):
        add(builder)

        add(builder, claim="Made up", evidence_text="something not on the page")

        assert len(rels(builder)[("Aang", "Katara")]["claims"]) == 1

    def test_ignores_case_and_whitespace(self, builder):
        result = add(builder, evidence_text="aang married katara after the war.")

        assert result["success"] is True

    def test_accepts_infobox_line(self, builder):
        result = add(
            builder,
            character_b="Ozai",
            relationship_type="enemy",
            claim="Ozai is an enemy of Aang",
            evidence_text="Enemies: Azula, Ozai",
        )

        assert result["success"] is True

    def test_rejects_fragments_joined_with_ellipsis(self, builder):
        result = add(builder, evidence_text="Aang married Katara... three children")

        assert result["success"] is False

    def test_rejects_unknown_page(self, builder):
        result = add(builder, evidence_url="https://example.com/nope")

        assert result["success"] is False
        assert "not a crawled page" in result["error"]

    def test_rejects_empty_evidence(self, builder):
        assert add(builder, evidence_text="  ")["success"] is False

    def test_counts_rejections(self, builder):
        add(builder, evidence_text="made up quote")
        add(builder)

        assert builder.evidence_rejections == 1


class TestValidation:
    def test_requires_canon(self, builder):
        assert add(builder, canon="")["success"] is False

    def test_requires_claim(self, builder):
        result = add(builder, claim="")

        assert result["success"] is False
        assert rels(builder) == {}

    def test_missing_character_lists_both_and_suggests_names(self, builder):
        result = add(builder, character_a="Bummi", character_b="Zuko")

        assert result["success"] is False
        assert "Bummi" in result["error"] and "Zuko" in result["error"]
        assert "Bumi" in result["suggestions"]["Bummi"]
        assert rels(builder) == {}

    def test_missing_character_mentions_affiliation_for_groups(self, builder):
        result = add(builder, character_b="Kyoshi Warriors")

        assert "add_affiliation" in result["hint"]


class TestCreateCharacterIsCreateOrGet:
    def test_existing_character_returns_record_not_error(self, builder):
        builder.knowledge_base["characters"][CANON]["Aang"]["bio"] = "The Avatar"

        result = builder._tool_create_character(
            name="Aang", canon=CANON, aliases=[], bio="New bio", source_url=URL
        )

        assert result["success"] is True
        assert result["existed"] is True
        assert result["character"]["bio"] == "The Avatar"
        # Existing record is not overwritten
        assert builder.knowledge_base["characters"][CANON]["Aang"]["bio"] == (
            "The Avatar"
        )

    def test_new_character_reports_created(self, builder):
        result = builder._tool_create_character(
            name="Zuko", canon=CANON, aliases=[], bio="Prince", source_url=URL
        )

        assert result["success"] is True
        assert result["existed"] is False


class TestToolDispatch:
    def test_add_relationship_is_dispatched(self, builder):
        result = builder._execute_kb_tool(
            "add_relationship",
            {
                "character_a": "Aang",
                "character_b": "Katara",
                "canon": CANON,
                "relationship_type": "romantic_partner",
                "summary": "Married",
                "claim": "Aang married Katara",
                "evidence_url": URL,
                "evidence_text": "Aang married Katara after the war",
            },
        )

        assert result["success"] is True

    @pytest.mark.parametrize(
        "old_tool", ["create_relationship", "add_relationship_claim"]
    )
    def test_old_tools_are_gone(self, builder, old_tool):
        result = builder._execute_kb_tool(old_tool, {})

        assert result["success"] is False
        assert "Unknown tool" in result["error"]
