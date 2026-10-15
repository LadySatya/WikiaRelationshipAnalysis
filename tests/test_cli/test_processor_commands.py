"""
Tests for Phase 2 CLI command helpers.

Tests cover:
- Knowledge base summary statistics (canon-nested KB structure)
"""

import pytest

pytestmark = pytest.mark.unit


def _make_kb():
    """Build a KB in the canon-nested shape returned by build_knowledge_base."""
    return {
        "characters": {
            "main": {
                "Aang": {"source_urls": ["u1", "u2", "u3"], "aliases": ["Avatar"]},
                "Zuko": {"source_urls": ["u1"], "aliases": []},
            },
            "film": {
                "Aang": {"source_urls": ["u4", "u5"], "aliases": []},
            },
        },
        "relationships": {
            "main": {
                ("Aang", "Zuko"): {
                    "type": "friend",
                    "summary": "Former enemies turned friends",
                    "claims": [{"claim": "c1", "evidence": []}, {"claim": "c2"}],
                },
            },
            "film": {
                ("Aang", "Katara"): {"type": "romantic", "claims": [{"claim": "c3"}]},
            },
        },
    }


class TestSummarizeKnowledgeBase:
    """Test summary statistics over the canon-nested KB."""

    def test_counts_characters_and_relationships_across_canons(self):
        """Counts must be per character/relationship, not per canon."""
        from src.cli.processor_commands import summarize_knowledge_base

        summary = summarize_knowledge_base(_make_kb())

        assert summary["num_characters"] == 3
        assert summary["num_relationships"] == 2

    def test_counts_claims_and_average(self):
        """Claims are summed across all canons."""
        from src.cli.processor_commands import summarize_knowledge_base

        summary = summarize_knowledge_base(_make_kb())

        assert summary["total_claims"] == 3
        assert summary["avg_claims"] == pytest.approx(1.5)

    def test_top_characters_sorted_by_source_count(self):
        """Top characters include canon and are ordered by source count."""
        from src.cli.processor_commands import summarize_knowledge_base

        summary = summarize_knowledge_base(_make_kb())

        assert summary["top_characters"][0] == {
            "name": "Aang",
            "canon": "main",
            "sources": 3,
            "aliases": 1,
        }
        assert [c["sources"] for c in summary["top_characters"]] == [3, 2, 1]

    def test_sample_relationship_unpacks_character_pair(self):
        """Regression: sample relationship key is (char_a, char_b) within a canon."""
        from src.cli.processor_commands import summarize_knowledge_base

        sample = summarize_knowledge_base(_make_kb())["sample_relationship"]

        assert sample["characters"] == ("Aang", "Zuko")
        assert sample["canon"] == "main"
        assert sample["data"]["type"] == "friend"

    def test_empty_kb(self):
        """Empty KB yields zero counts and no sample, without errors."""
        from src.cli.processor_commands import summarize_knowledge_base

        summary = summarize_knowledge_base({"characters": {}, "relationships": {}})

        assert summary["num_characters"] == 0
        assert summary["num_relationships"] == 0
        assert summary["avg_claims"] == 0
        assert summary["top_characters"] == []
        assert summary["sample_relationship"] is None
