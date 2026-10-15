"""
Tests for windowed page processing in CharacterKnowledgeBuilder.

Long pages are processed in consecutive windows so the whole page is read
without putting the entire page into a single LLM call.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.processor.analysis.knowledge_builder import (
    CharacterKnowledgeBuilder,
    split_into_windows,
)

pytestmark = pytest.mark.unit


def _sentences(count: int, prefix: str = "Sentence") -> str:
    return " ".join(f"{prefix} number {i} is here." for i in range(count))


class TestSplitIntoWindows:
    """Test splitting page text into windows."""

    def test_short_text_is_single_window(self):
        assert split_into_windows("Aang is the Avatar.", 1000) == [
            "Aang is the Avatar."
        ]

    def test_empty_text_has_no_windows(self):
        assert split_into_windows("", 1000) == []

    def test_windows_respect_size_limit(self):
        windows = split_into_windows(_sentences(200), 500)

        assert len(windows) > 1
        assert all(len(w) <= 500 for w in windows)

    def test_no_text_is_lost(self):
        """Regression: unlike the old 3000-char cut, every character is covered."""
        text = _sentences(300)

        windows = split_into_windows(text, 700)

        assert "".join(windows).replace(" ", "") == text.replace(" ", "")

    def test_breaks_at_sentence_boundaries(self):
        windows = split_into_windows(_sentences(200), 500)

        assert all(w.endswith(".") for w in windows[:-1])

    def test_hard_splits_text_without_sentence_breaks(self):
        text = "x" * 2500

        windows = split_into_windows(text, 1000)

        assert [len(w) for w in windows] == [1000, 1000, 500]


@pytest.fixture
def builder(tmp_path):
    """Builder with mocked LLM, writing state to a temp directory."""
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
    b.llm_logger = MagicMock()
    b.query_engine.llm_client.generate_with_tools.return_value = {
        "final_response": "done",
        "tool_calls": [],
        "usage": {
            "total_input_tokens": 100,
            "total_output_tokens": 50,
            "estimated_cost_usd": 0.001,
            "iterations": 1,
        },
    }
    return b


def _page(content: str):
    return {
        "title": "Aang | Avatar Wiki | Fandom",
        "url": "https://avatar.fandom.com/wiki/Aang",
        "main_content": content,
        "infobox_data": {"Allies": "Katara, Sokka"},
    }


def _prompts(builder):
    calls = builder.query_engine.llm_client.generate_with_tools.call_args_list
    return [c.kwargs["prompt"] for c in calls]


class TestWindowedProcessing:
    """Test that _process_page reads every window of a page."""

    def test_short_page_uses_one_call(self, builder):
        builder.window_chars = 5000

        builder._process_page(_page(_sentences(10)))

        assert len(_prompts(builder)) == 1

    def test_long_page_processes_every_window(self, builder):
        """Regression: text far beyond 3000 chars must reach the model."""
        builder.window_chars = 1000
        content = _sentences(200) + " The final sentence mentions Kyoshi."

        builder._process_page(_page(content))

        prompts = _prompts(builder)
        assert len(prompts) == len(split_into_windows(content, 1000))
        assert "The final sentence mentions Kyoshi." in prompts[-1]

    def test_page_cost_is_summed_across_windows(self, builder):
        builder.window_chars = 1000
        content = _sentences(100)

        cost = builder._process_page(_page(content))

        windows = len(split_into_windows(content, 1000))
        assert cost == pytest.approx(0.001 * windows)

    def test_infobox_only_in_first_window(self, builder):
        builder.window_chars = 1000

        builder._process_page(_page(_sentences(100)))

        prompts = _prompts(builder)
        assert "Allies: Katara, Sokka" in prompts[0]
        assert all("Allies: Katara, Sokka" not in p for p in prompts[1:])

    def test_later_windows_state_part_number_and_canon(self, builder):
        builder.window_chars = 1000

        def set_canon(**kwargs):
            builder.current_page_canon = "main"
            return builder.query_engine.llm_client.generate_with_tools.return_value

        builder.query_engine.llm_client.generate_with_tools.side_effect = set_canon

        builder._process_page(_page(_sentences(100)))

        prompts = _prompts(builder)
        total = len(prompts)
        assert f"part 2 of {total}" in prompts[1]
        assert "'main'" in prompts[1]

    def test_window_cap_is_enforced_and_recorded(self, builder):
        """Pages over the cap are partly read - and that is recorded, not silent."""
        builder.window_chars = 500
        builder.max_windows_per_page = 2
        page = _page(_sentences(200))

        builder._process_page(page)

        assert len(_prompts(builder)) == 2
        partial = builder.partial_pages[page["url"]]
        assert partial["windows_processed"] == 2
        assert partial["windows_total"] == len(
            split_into_windows(page["main_content"], 500)
        )

    def test_partial_pages_are_saved_in_state(self, builder):
        builder.partial_pages = {"u": {"windows_processed": 2, "windows_total": 5}}

        builder.save()

        import json

        state = json.loads(builder.state_file.read_text())
        assert state["partial_pages"] == builder.partial_pages

    def test_window_settings_read_config(self, builder):
        from src.processor.config import get_config

        config = get_config()
        assert builder.window_chars == config.knowledge_window_chars
        assert builder.max_windows_per_page == config.knowledge_max_windows_per_page
