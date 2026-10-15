"""
Tests for LLMClient tool-calling loop (generate_with_tools).

These tests cover the multi-turn tool interaction loop that powers
the knowledge builder's autonomous character/relationship discovery.
"""

from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


class TestGenerateWithToolsValidation:
    """Test input validation for generate_with_tools."""

    def test_empty_prompt_raises_error(self):
        """Should raise ValueError for empty prompt."""
        from src.processor.llm.llm_client import LLMClient

        client = LLMClient()
        tools = [{"name": "test_tool", "input_schema": {}}]

        with pytest.raises(ValueError, match="prompt cannot be empty"):
            client.generate_with_tools("", tools, lambda n, **k: {})

    def test_whitespace_prompt_raises_error(self):
        """Should raise ValueError for whitespace-only prompt."""
        from src.processor.llm.llm_client import LLMClient

        client = LLMClient()
        tools = [{"name": "test_tool", "input_schema": {}}]

        with pytest.raises(ValueError, match="prompt cannot be empty"):
            client.generate_with_tools("   ", tools, lambda n, **k: {})

    def test_empty_tools_raises_error(self):
        """Should raise ValueError for empty tools list."""
        from src.processor.llm.llm_client import LLMClient

        client = LLMClient()

        with pytest.raises(ValueError, match="tools cannot be empty"):
            client.generate_with_tools("Test prompt", [], lambda n, **k: {})

    def test_non_callable_executor_raises_error(self):
        """Should raise ValueError if tool_executor is not callable."""
        from src.processor.llm.llm_client import LLMClient

        client = LLMClient()
        tools = [{"name": "test_tool", "input_schema": {}}]

        with pytest.raises(ValueError, match="tool_executor must be callable"):
            client.generate_with_tools("Test prompt", tools, "not_callable")

    def test_negative_max_tokens_raises_error(self):
        """Should raise ValueError for non-positive max_tokens."""
        from src.processor.llm.llm_client import LLMClient

        client = LLMClient()
        tools = [{"name": "test_tool", "input_schema": {}}]

        with pytest.raises(ValueError, match="max_tokens must be positive"):
            client.generate_with_tools(
                "Test prompt", tools, lambda n, **k: {}, max_tokens=0
            )


class TestGenerateWithToolsExecution:
    """Test the tool-calling execution loop."""

    def _create_mock_tool_use_response(
        self, tool_name: str, tool_input: Dict, tool_id: str = "tool_123"
    ):
        """Helper to create a mock tool_use response."""
        mock_response = MagicMock()
        mock_response.stop_reason = "tool_use"

        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.name = tool_name
        tool_block.input = tool_input
        tool_block.id = tool_id

        mock_response.content = [tool_block]
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=50)
        return mock_response

    def _create_mock_end_turn_response(self, text: str = "Final response"):
        """Helper to create a mock end_turn response."""
        mock_response = MagicMock()
        mock_response.stop_reason = "end_turn"

        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = text

        mock_response.content = [text_block]
        mock_response.usage = MagicMock(input_tokens=50, output_tokens=25)
        return mock_response

    def test_single_tool_call_then_end(self):
        """Should execute one tool call and return final response."""
        from src.processor.llm.llm_client import LLMClient

        with patch("anthropic.Anthropic") as mock_anthropic_class:
            mock_client = MagicMock()
            mock_anthropic_class.return_value = mock_client

            # First call: tool_use, Second call: end_turn
            mock_client.messages.create.side_effect = [
                self._create_mock_tool_use_response(
                    "search_characters", {"query": "Aang"}
                ),
                self._create_mock_end_turn_response("Found character Aang"),
            ]

            client = LLMClient()
            tools = [{"name": "search_characters", "input_schema": {"type": "object"}}]

            executed_tools = []

            def tool_executor(name, **kwargs):
                executed_tools.append((name, kwargs))
                return {"matches": ["Aang"], "count": 1}

            result = client.generate_with_tools("Find Aang", tools, tool_executor)

            assert result["final_response"] == "Found character Aang"
            assert len(result["tool_calls"]) == 1
            assert result["tool_calls"][0]["tool"] == "search_characters"
            assert result["tool_calls"][0]["input"] == {"query": "Aang"}
            assert executed_tools == [("search_characters", {"query": "Aang"})]

    def test_multiple_tool_calls_in_sequence(self):
        """Should execute multiple tool calls before ending."""
        from src.processor.llm.llm_client import LLMClient

        with patch("anthropic.Anthropic") as mock_anthropic_class:
            mock_client = MagicMock()
            mock_anthropic_class.return_value = mock_client

            # Three iterations: tool, tool, end
            mock_client.messages.create.side_effect = [
                self._create_mock_tool_use_response(
                    "determine_canon", {"canon": "main"}, "t1"
                ),
                self._create_mock_tool_use_response(
                    "create_character", {"name": "Aang"}, "t2"
                ),
                self._create_mock_end_turn_response("Created Aang"),
            ]

            client = LLMClient()
            tools = [
                {"name": "determine_canon", "input_schema": {"type": "object"}},
                {"name": "create_character", "input_schema": {"type": "object"}},
            ]

            def tool_executor(name, **kwargs):
                return {"success": True}

            result = client.generate_with_tools("Build KB", tools, tool_executor)

            assert len(result["tool_calls"]) == 2
            assert result["tool_calls"][0]["tool"] == "determine_canon"
            assert result["tool_calls"][1]["tool"] == "create_character"
            assert result["usage"]["iterations"] == 3

    def test_tool_executor_error_is_returned_to_claude(self):
        """Tool execution errors should be returned to Claude, not raised."""
        from src.processor.llm.llm_client import LLMClient

        with patch("anthropic.Anthropic") as mock_anthropic_class:
            mock_client = MagicMock()
            mock_anthropic_class.return_value = mock_client

            mock_client.messages.create.side_effect = [
                self._create_mock_tool_use_response("bad_tool", {}),
                self._create_mock_end_turn_response("Handled error"),
            ]

            client = LLMClient()
            tools = [{"name": "bad_tool", "input_schema": {"type": "object"}}]

            def failing_executor(name, **kwargs):
                raise RuntimeError("Tool failed!")

            result = client.generate_with_tools("Test", tools, failing_executor)

            # Should complete without raising
            assert result["final_response"] == "Handled error"
            # Tool call should have error recorded
            assert result["tool_calls"][0]["result"]["error"] == "Tool failed!"
            assert result["tool_calls"][0]["result"]["success"] is False

    def test_max_iterations_raises_error(self):
        """Should raise RuntimeError if max iterations reached without completion."""
        from src.processor.llm.llm_client import LLMClient

        with patch("anthropic.Anthropic") as mock_anthropic_class:
            mock_client = MagicMock()
            mock_anthropic_class.return_value = mock_client

            # Always return tool_use (never ends)
            mock_client.messages.create.return_value = self._create_mock_tool_use_response(
                "infinite_tool", {}
            )

            client = LLMClient()
            tools = [{"name": "infinite_tool", "input_schema": {"type": "object"}}]

            with pytest.raises(RuntimeError, match="Max iterations.*reached"):
                client.generate_with_tools(
                    "Test", tools, lambda n, **k: {}, max_iterations=3
                )

    def test_api_error_raises_runtime_error(self):
        """API call failures should raise RuntimeError."""
        from src.processor.llm.llm_client import LLMClient

        with patch("anthropic.Anthropic") as mock_anthropic_class:
            mock_client = MagicMock()
            mock_anthropic_class.return_value = mock_client

            mock_client.messages.create.side_effect = Exception("API down")

            client = LLMClient()
            tools = [{"name": "test_tool", "input_schema": {"type": "object"}}]

            with pytest.raises(RuntimeError, match="LLM API call failed"):
                client.generate_with_tools("Test", tools, lambda n, **k: {})

    def test_usage_tracking(self):
        """Should track token usage across iterations."""
        from src.processor.llm.llm_client import LLMClient

        with patch("anthropic.Anthropic") as mock_anthropic_class:
            mock_client = MagicMock()
            mock_anthropic_class.return_value = mock_client

            mock_client.messages.create.side_effect = [
                self._create_mock_tool_use_response("tool1", {}),
                self._create_mock_end_turn_response("Done"),
            ]

            client = LLMClient()
            tools = [{"name": "tool1", "input_schema": {"type": "object"}}]

            result = client.generate_with_tools("Test", tools, lambda n, **k: {})

            # First call: 100 in + 50 out, Second call: 50 in + 25 out
            assert result["usage"]["total_input_tokens"] == 150
            assert result["usage"]["total_output_tokens"] == 75
            assert "estimated_cost_usd" in result["usage"]

    def test_system_prompt_passed_to_api(self):
        """System prompt should be passed to Claude API."""
        from src.processor.llm.llm_client import LLMClient

        with patch("anthropic.Anthropic") as mock_anthropic_class:
            mock_client = MagicMock()
            mock_anthropic_class.return_value = mock_client

            mock_client.messages.create.return_value = (
                self._create_mock_end_turn_response("Done")
            )

            client = LLMClient()
            client.prompt_caching = False  # plain pass-through; caching tested below
            tools = [{"name": "test", "input_schema": {"type": "object"}}]

            client.generate_with_tools(
                "Test", tools, lambda n, **k: {}, system_prompt="You are helpful"
            )

            # Verify system prompt was passed
            call_kwargs = mock_client.messages.create.call_args[1]
            assert call_kwargs["system"] == "You are helpful"

    def test_immediate_end_turn(self):
        """Should handle Claude ending immediately without tool calls."""
        from src.processor.llm.llm_client import LLMClient

        with patch("anthropic.Anthropic") as mock_anthropic_class:
            mock_client = MagicMock()
            mock_anthropic_class.return_value = mock_client

            mock_client.messages.create.return_value = (
                self._create_mock_end_turn_response("No tools needed")
            )

            client = LLMClient()
            tools = [{"name": "test", "input_schema": {"type": "object"}}]

            result = client.generate_with_tools("Test", tools, lambda n, **k: {})

            assert result["final_response"] == "No tools needed"
            assert len(result["tool_calls"]) == 0
            assert result["usage"]["iterations"] == 1

    def test_does_not_send_sampling_params_and_sends_effort(self):
        """Tool loop must not send temperature (rejected by Haiku 5.5) and should send effort."""
        from src.processor.llm.llm_client import LLMClient

        with patch("anthropic.Anthropic") as mock_anthropic_class:
            mock_client = MagicMock()
            mock_anthropic_class.return_value = mock_client
            mock_client.messages.create.return_value = (
                self._create_mock_end_turn_response("Done")
            )

            client = LLMClient()
            tools = [{"name": "test", "input_schema": {"type": "object"}}]
            client.generate_with_tools("Test", tools, lambda n, **k: {})

            call_kwargs = mock_client.messages.create.call_args[1]
            assert "temperature" not in call_kwargs
            assert call_kwargs["output_config"] == {"effort": client.effort}

    def test_refusal_raises_clear_error(self):
        """A refusal should raise an error naming the refusal, not 'max iterations'."""
        from src.processor.llm.llm_client import LLMClient

        with patch("anthropic.Anthropic") as mock_anthropic_class:
            mock_client = MagicMock()
            mock_anthropic_class.return_value = mock_client

            refusal = MagicMock()
            refusal.stop_reason = "refusal"
            refusal.stop_details = MagicMock(category="general_harms")
            refusal.content = []
            refusal.usage = MagicMock(input_tokens=10, output_tokens=0)
            mock_client.messages.create.return_value = refusal

            client = LLMClient()
            tools = [{"name": "test", "input_schema": {"type": "object"}}]

            with pytest.raises(RuntimeError, match="refus"):
                client.generate_with_tools("Test", tools, lambda n, **k: {})

    def test_max_tokens_stop_raises_clear_error(self):
        """Hitting max_tokens mid-turn should raise an error naming max_tokens."""
        from src.processor.llm.llm_client import LLMClient

        with patch("anthropic.Anthropic") as mock_anthropic_class:
            mock_client = MagicMock()
            mock_anthropic_class.return_value = mock_client

            truncated = MagicMock()
            truncated.stop_reason = "max_tokens"
            truncated.content = [MagicMock(type="thinking", thinking="")]
            truncated.usage = MagicMock(input_tokens=10, output_tokens=4096)
            mock_client.messages.create.return_value = truncated

            client = LLMClient()
            tools = [{"name": "test", "input_schema": {"type": "object"}}]

            with pytest.raises(RuntimeError, match="max_tokens"):
                client.generate_with_tools("Test", tools, lambda n, **k: {})

    def test_thinking_blocks_passed_back_unmodified(self):
        """Assistant turns (including thinking blocks) must be sent back as-is."""
        from src.processor.llm.llm_client import LLMClient

        with patch("anthropic.Anthropic") as mock_anthropic_class:
            mock_client = MagicMock()
            mock_anthropic_class.return_value = mock_client

            tool_response = self._create_mock_tool_use_response("search", {"q": "x"})
            thinking_block = MagicMock(type="thinking", thinking="", signature="sig")
            tool_response.content = [thinking_block] + tool_response.content

            sent_conversations = []

            def record(**kwargs):
                sent_conversations.append(list(kwargs["messages"]))
                if len(sent_conversations) == 1:
                    return tool_response
                return self._create_mock_end_turn_response("Done")

            mock_client.messages.create.side_effect = record

            client = LLMClient()
            tools = [{"name": "search", "input_schema": {"type": "object"}}]
            client.generate_with_tools("Test", tools, lambda n, **k: {"ok": True})

            assistant_turn = sent_conversations[1][1]
            assert assistant_turn["role"] == "assistant"
            assert assistant_turn["content"][0] is thinking_block


class TestPruneConversation:
    """Test the conversation pruning helper."""

    def test_prune_keeps_first_message(self):
        """Should always keep the first message (original task)."""
        from src.processor.llm.llm_client import LLMClient

        client = LLMClient()

        messages = [
            {"role": "user", "content": "Original task"},
            {"role": "assistant", "content": "Response 1"},
            {"role": "user", "content": "Result 1"},
            {"role": "assistant", "content": "Response 2"},
            {"role": "user", "content": "Result 2"},
            {"role": "assistant", "content": "Response 3"},
            {"role": "user", "content": "Result 3"},
        ]

        pruned = client._prune_conversation(messages, keep_last_n=1)

        assert pruned[0] == {"role": "user", "content": "Original task"}

    def test_prune_keeps_last_n_exchanges(self):
        """Should keep last N exchanges (N*2 messages)."""
        from src.processor.llm.llm_client import LLMClient

        client = LLMClient()

        messages = [
            {"role": "user", "content": "Original task"},
            {"role": "assistant", "content": "Response 1"},
            {"role": "user", "content": "Result 1"},
            {"role": "assistant", "content": "Response 2"},
            {"role": "user", "content": "Result 2"},
            {"role": "assistant", "content": "Response 3"},
            {"role": "user", "content": "Result 3"},
        ]

        pruned = client._prune_conversation(messages, keep_last_n=2)

        # Should have: task + last 4 messages (2 exchanges)
        assert len(pruned) == 5
        assert pruned[0]["content"] == "Original task"
        assert pruned[-1]["content"] == "Result 3"
        assert pruned[-2]["content"] == "Response 3"

    def test_prune_short_conversation_unchanged(self):
        """Short conversations should not be pruned."""
        from src.processor.llm.llm_client import LLMClient

        client = LLMClient()

        messages = [
            {"role": "user", "content": "Task"},
            {"role": "assistant", "content": "Response"},
            {"role": "user", "content": "Result"},
        ]

        pruned = client._prune_conversation(messages, keep_last_n=3)

        # With keep_last_n=3, need 1 + 6 = 7 messages to prune
        # 3 messages is under that threshold
        assert pruned == messages

    def test_prune_boundary_case(self):
        """Test exact boundary case where pruning just starts."""
        from src.processor.llm.llm_client import LLMClient

        client = LLMClient()

        # keep_last_n=2 means keep 1 + 4 = 5 messages
        # With exactly 6 messages, should prune 1
        messages = [
            {"role": "user", "content": "Task"},
            {"role": "assistant", "content": "R1"},
            {"role": "user", "content": "U1"},
            {"role": "assistant", "content": "R2"},
            {"role": "user", "content": "U2"},
            {"role": "assistant", "content": "R3"},
        ]

        pruned = client._prune_conversation(messages, keep_last_n=2)

        # Should keep: Task + last 4
        assert len(pruned) == 5
        assert pruned[0]["content"] == "Task"
        # R1 and U1 should be gone
        assert "R1" not in [m["content"] for m in pruned]

    def test_prune_strips_thinking_blocks_when_history_changes(self):
        """Thinking blocks are invalid after earlier turns are removed, so strip them."""
        from src.processor.llm.llm_client import LLMClient

        client = LLMClient()

        def assistant_turn(n):
            return {
                "role": "assistant",
                "content": [
                    MagicMock(type="thinking", thinking="", signature=f"s{n}"),
                    {"type": "redacted_thinking", "data": "x"},
                    MagicMock(type="tool_use", id=f"t{n}", name="search", input={}),
                ],
            }

        messages = [{"role": "user", "content": "Task"}]
        for n in range(3):
            messages.append(assistant_turn(n))
            messages.append({"role": "user", "content": [{"type": "tool_result"}]})

        pruned = client._prune_conversation(messages, keep_last_n=1)

        assistant_blocks = pruned[1]["content"]
        types = [
            b["type"] if isinstance(b, dict) else b.type for b in assistant_blocks
        ]
        assert types == ["tool_use"]
        assert assistant_blocks[0].id == "t2"
        # Original conversation must not be mutated
        assert len(messages[5]["content"]) == 3

    def test_prune_keeps_thinking_blocks_when_nothing_pruned(self):
        """Short conversations are unchanged, so thinking blocks stay valid."""
        from src.processor.llm.llm_client import LLMClient

        client = LLMClient()
        thinking = MagicMock(type="thinking", thinking="", signature="s")
        messages = [
            {"role": "user", "content": "Task"},
            {"role": "assistant", "content": [thinking]},
            {"role": "user", "content": "Result"},
        ]

        pruned = client._prune_conversation(messages, keep_last_n=3)

        assert pruned[1]["content"][0] is thinking


class TestPromptCaching:
    """Test prompt caching in the tool loop and cache-aware cost tracking."""

    def _end_turn(self, input_tokens=100, output_tokens=50, cache_read=0, cache_write=0):
        response = MagicMock()
        response.stop_reason = "end_turn"
        response.content = [MagicMock(type="text", text="Done")]
        response.usage = MagicMock(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_input_tokens=cache_read,
            cache_creation_input_tokens=cache_write,
        )
        return response

    def _run(self, client, response, system_prompt="You are helpful"):
        with patch("anthropic.Anthropic") as mock_anthropic_class:
            mock_client = MagicMock()
            mock_anthropic_class.return_value = mock_client
            mock_client.messages.create.return_value = response
            tools = [{"name": "test", "input_schema": {"type": "object"}}]
            result = client.generate_with_tools(
                "Test", tools, lambda n, **k: {}, system_prompt=system_prompt
            )
            return result, mock_client.messages.create.call_args[1]

    def test_caching_marks_system_prompt_and_enables_auto_caching(self):
        """System prompt (after tools) gets a breakpoint; history uses auto caching."""
        from src.processor.llm.llm_client import LLMClient

        client = LLMClient()
        client.prompt_caching = True
        _, kwargs = self._run(client, self._end_turn())

        assert kwargs["system"] == [
            {
                "type": "text",
                "text": "You are helpful",
                "cache_control": {"type": "ephemeral"},
            }
        ]
        assert kwargs["cache_control"] == {"type": "ephemeral"}

    def test_caching_disabled_sends_plain_system_prompt(self):
        """With caching off, requests are unchanged from the uncached form."""
        from src.processor.llm.llm_client import LLMClient

        client = LLMClient()
        client.prompt_caching = False
        _, kwargs = self._run(client, self._end_turn())

        assert kwargs["system"] == "You are helpful"
        assert "cache_control" not in kwargs

    def test_caching_without_system_prompt(self):
        """Without a system prompt, only automatic caching is used."""
        from src.processor.llm.llm_client import LLMClient

        client = LLMClient()
        client.prompt_caching = True
        _, kwargs = self._run(client, self._end_turn(), system_prompt=None)

        assert "system" not in kwargs
        assert kwargs["cache_control"] == {"type": "ephemeral"}

    def test_prompt_caching_reads_config(self):
        """prompt_caching defaults from processor config."""
        from src.processor.config import get_config
        from src.processor.llm.llm_client import LLMClient

        assert LLMClient().prompt_caching == get_config().llm_prompt_caching

    def test_usage_includes_cache_tokens_and_cost(self):
        """Cache reads/writes are tracked and priced (0.1x / 1.25x input rate)."""
        from src.processor.llm.llm_client import LLMClient

        client = LLMClient(model="claude-haiku-5-5")
        result, _ = self._run(
            client, self._end_turn(100, 50, cache_read=1000, cache_write=200)
        )

        usage = result["usage"]
        assert usage["total_cache_read_tokens"] == 1000
        assert usage["total_cache_write_tokens"] == 200
        expected = (100 * 0.10 + 50 * 0.50 + 1000 * 0.01 + 200 * 0.125) / 1_000_000
        assert usage["estimated_cost_usd"] == pytest.approx(expected)

        stats = client.get_usage_stats()
        assert stats["total_cache_read_tokens"] == 1000
        assert stats["total_cache_write_tokens"] == 200
        assert stats["estimated_cost_usd"] == pytest.approx(expected)
