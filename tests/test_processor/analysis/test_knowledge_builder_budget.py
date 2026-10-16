"""
Tests for the discover spending cap (max_cost) in CharacterKnowledgeBuilder.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.processor.analysis.knowledge_builder import CharacterKnowledgeBuilder

pytestmark = pytest.mark.unit


@pytest.fixture
def builder(tmp_path):
    """Builder with 5 fake pages that each cost $0.40 to process."""
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
    b.project_dir = tmp_path
    b.characters_dir = tmp_path / "characters"
    b.relationships_dir = tmp_path / "relationships"
    b.state_file = tmp_path / "cache" / "discovery_state.json"
    b.processed_pages = {}
    b._load_crawled_pages = MagicMock(
        return_value=[
            {"title": f"Page {i}", "url": f"https://wiki/p{i}", "main_content": "x"}
            for i in range(5)
        ]
    )
    b._process_page = MagicMock(return_value=0.40)
    return b


class TestMaxCost:
    def test_no_cap_processes_all_pages(self, builder):
        builder.build_knowledge_base()

        assert builder._process_page.call_count == 5

    def test_stops_starting_pages_once_budget_is_spent(self, builder):
        """$1.00 cap at $0.40/page: pages 1-3 run ($1.20), then it stops."""
        builder.build_knowledge_base(max_cost=1.00)

        assert builder._process_page.call_count == 3

    def test_stopped_run_is_resumable(self, builder):
        """Pages processed before the cap are saved; the rest remain for resume."""
        builder.build_knowledge_base(max_cost=1.00)

        assert len(builder.processed_pages) == 3
        assert builder.state_file.exists()
        assert builder.budget_exhausted is True

    def test_budget_not_exhausted_when_run_completes(self, builder):
        builder.build_knowledge_base(max_cost=100.0)

        assert builder.budget_exhausted is False


class TestPagesProcessedMetadata:
    def test_counts_processed_pages_not_loop_index(self, builder):
        """Regression: pages_processed was the loop index, counting skipped pages."""
        # The last page was processed in an earlier run, so the loop ends on a skip
        builder.processed_pages = {"https://wiki/p4": "t"}

        builder.build_knowledge_base()

        # p0-p3 processed now + p4 earlier = 5 (the loop index would say 4)
        assert builder._process_page.call_count == 4
        assert builder.knowledge_base["metadata"]["pages_processed"] == 5
