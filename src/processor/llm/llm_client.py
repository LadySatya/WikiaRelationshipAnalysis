"""
LLMClient - Anthropic Claude API wrapper for RAG queries.

This module provides a simple interface to Claude for text generation in RAG
workflows. Supports token counting, cost estimation, and conversation context.
"""
from typing import Optional, List, Dict, Any, TYPE_CHECKING, cast
import os
import logging
import time

from ..config import get_config
from src.utils.logging_config import get_logger, get_llm_logger

if TYPE_CHECKING:
    from anthropic import Anthropic
    from anthropic.types import MessageParam, TextBlock


class LLMClient:
    """
    Client for interacting with Claude API for text generation.

    Provides a simple interface for:
    - Text generation with system prompts
    - Multi-turn conversations with context
    - Token counting and cost tracking
    - Temperature and max_tokens control

    Args:
        provider: LLM provider - only "anthropic" supported currently
        model: Model name (default: from config)
        api_key: Anthropic API key (default: from ANTHROPIC_API_KEY env var)

    Raises:
        ValueError: If provider is not supported

    Example:
        >>> client = LLMClient()
        >>> response = client.generate(
        ...     prompt="Who is Aang?",
        ...     system_prompt="You are analyzing Avatar wiki content."
        ... )
        >>> print(response)
        "Aang is the protagonist..."

        >>> stats = client.get_usage_stats()
        >>> print(f"Cost: ${stats['estimated_cost_usd']:.4f}")
    """

    SUPPORTED_PROVIDERS = {"anthropic"}

    # Pricing per 1M tokens (as of 2024-10-16)
    PRICING = {
        "claude-3-5-haiku-20241022": {
            "input": 1.00,   # $1 per 1M input tokens
            "output": 5.00,  # $5 per 1M output tokens
        },
        "claude-3-5-sonnet-20241022": {
            "input": 3.00,   # $3 per 1M input tokens
            "output": 15.00, # $15 per 1M output tokens
        },
    }

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None
    ) -> None:
        """
        Initialize LLMClient with specified provider and model.

        Args:
            provider: LLM provider - "anthropic" (default: from config)
            model: Model name (default: from config)
            api_key: API key (default: from ANTHROPIC_API_KEY env var)
        """
        # Load config
        config = get_config()

        # Set provider from config if not specified
        if provider is None:
            provider = config.llm_provider

        # Validate provider
        if provider not in self.SUPPORTED_PROVIDERS:
            raise ValueError(
                f"provider must be one of {self.SUPPORTED_PROVIDERS}, got '{provider}'"
            )

        self.provider = provider

        # Set model from config if not specified
        if model is None:
            model = config.llm_model

        self.model = model

        # Get API key
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")

        # Lazy loading - client initialized on first use
        self._client: Optional["Anthropic"] = None

        # Token tracking
        self.total_input_tokens = 0
        self.total_output_tokens = 0

        self.logger = get_logger("llm")
        self.llm_logger = None

    def _init_client(self) -> None:
        """Initialize Anthropic client (lazy loading)."""
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic(api_key=self.api_key)

    def _ensure_llm_logger(self):
        """Lazy-initialize LLM logger."""
        if self.llm_logger is None:
            try:
                self.llm_logger = get_llm_logger()
            except RuntimeError:
                pass

    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost for given token counts."""
        return self.estimate_cost(input_tokens, output_tokens)

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        context: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """
        Generate text using Claude API.

        Args:
            prompt: User prompt/question
            system_prompt: Optional system prompt for context
            temperature: Sampling temperature 0-1 (default: 0.7)
            max_tokens: Maximum tokens to generate (default: 1024)
            context: Optional conversation context as list of messages

        Returns:
            Generated text response

        Raises:
            ValueError: If parameters are invalid
            Exception: If API call fails
        """
        # Validate inputs
        if not prompt or not prompt.strip():
            raise ValueError("prompt cannot be empty")

        if not (0 <= temperature <= 1):
            raise ValueError("temperature must be between 0 and 1")

        if max_tokens <= 0:
            raise ValueError("max_tokens must be positive")

        # Initialize client if needed
        self._init_client()
        assert self._client is not None, "Client should be initialized"

        # Build messages list with proper typing
        messages: List["MessageParam"] = []

        # Add context if provided
        if context:
            messages.extend(cast(List["MessageParam"], context))

        # Add current prompt
        messages.append(cast("MessageParam", {"role": "user", "content": prompt.strip()}))

        # Call Claude API with explicit parameters (not **kwargs unpacking)
        # The Anthropic SDK requires explicit named parameters for type safety
        # Retry logic for transient failures (529 overload, rate limits, network issues)
        max_retries = 3
        base_delay = 2.0  # seconds

        for attempt in range(max_retries):
            try:
                if system_prompt:
                    response = self._client.messages.create(
                        model=self.model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        system=system_prompt
                    )
                else:
                    response = self._client.messages.create(
                        model=self.model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens
                    )
                break  # Success, exit retry loop

            except Exception as e:
                error_str = str(e)
                is_last_attempt = (attempt == max_retries - 1)

                # Check if this is a retryable error (529 overload, rate limits, network)
                is_retryable = (
                    "overloaded" in error_str.lower() or
                    "529" in error_str or
                    "rate_limit" in error_str.lower() or
                    "timeout" in error_str.lower() or
                    "connection" in error_str.lower()
                )

                if is_retryable and not is_last_attempt:
                    # Exponential backoff: 2s, 4s, 8s
                    delay = base_delay * (2 ** attempt)
                    self.logger.warning(
                        f"API call failed (attempt {attempt + 1}/{max_retries}): {error_str}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                    continue
                else:
                    # Non-retryable error or last attempt failed
                    raise Exception(f"LLM API call failed: {error_str}") from e

        # Extract text from response
        # We expect TextBlock since we're not using tools/thinking
        content_block = response.content[0]
        if hasattr(content_block, "text"):
            text: str = cast("TextBlock", content_block).text
        else:
            raise Exception(f"Unexpected content block type: {type(content_block).__name__}")

        # Track token usage
        self.total_input_tokens += response.usage.input_tokens
        self.total_output_tokens += response.usage.output_tokens

        self._ensure_llm_logger()
        if self.llm_logger:
            self.llm_logger.log_prompt(
                prompt=prompt,
                model=self.model,
                purpose="text_generation",
                response=text,
                usage={
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens
                },
                cost=self._calculate_cost(
                    response.usage.input_tokens,
                    response.usage.output_tokens
                ),
                metadata={"has_context": context is not None}
            )

        return text

    def get_usage_stats(self) -> Dict[str, Any]:
        """
        Get token usage statistics and cost estimate.

        Returns:
            Dictionary with usage stats:
                {
                    "total_input_tokens": 1000,
                    "total_output_tokens": 500,
                    "total_tokens": 1500,
                    "estimated_cost_usd": 0.006,
                    "model": "claude-3-5-haiku-20241022"
                }
        """
        cost = self.estimate_cost(self.total_input_tokens, self.total_output_tokens)

        return {
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "estimated_cost_usd": cost,
            "model": self.model,
        }

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Estimate cost in USD for given token counts.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Estimated cost in USD
        """
        # Get pricing for current model (default to Haiku if unknown)
        pricing = self.PRICING.get(
            self.model,
            self.PRICING["claude-3-5-haiku-20241022"]
        )

        # Calculate cost (pricing is per 1M tokens)
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]

        return input_cost + output_cost

    def reset_usage_stats(self) -> None:
        """Reset token usage statistics to zero."""
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    def query_with_citations(
        self,
        query: str,
        documents: List[str],
        document_metadata: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 1024
    ) -> Dict[str, Any]:
        """
        Query Claude with documents and get automatic citation tracking.

        This method enables Claude's citation feature to track which documents
        support each claim in the response. Citations are automatically mapped
        back to source pages using the provided metadata.

        Args:
            query: Question or prompt to send to Claude
            documents: List of document texts (retrieved chunks)
            document_metadata: List of metadata dicts (one per document)
                Each dict should contain source tracking fields like:
                - source_url: URL of the source page
                - page_title: Title of the source page
                - chunk_id: ID of the chunk (optional)
            temperature: Sampling temperature 0-1 (default: 0.7)
            max_tokens: Maximum tokens to generate (default: 1024)

        Returns:
            Dictionary with:
                {
                    "text": "Generated response text",
                    "evidence": [
                        {
                            "cited_text": "Exact text from document",
                            "source_url": "wiki/page",
                            "page_title": "Page Title",
                            "document_index": 0,
                            "location": {"start": 0, "end": 27},
                            ... (other metadata fields)
                        },
                        ...
                    ]
                }

        Raises:
            ValueError: If inputs are invalid

        Example:
            >>> client = LLMClient()
            >>> result = client.query_with_citations(
            ...     "Who is Aang?",
            ...     ["Aang is the Avatar...", "He is the last Airbender..."],
            ...     [
            ...         {"source_url": "wiki/aang", "page_title": "Aang"},
            ...         {"source_url": "wiki/avatar", "page_title": "Avatar"}
            ...     ]
            ... )
            >>> print(result["text"])
            >>> print(f"Citations: {len(result['evidence'])}")
        """
        # Validate inputs
        if not query or not query.strip():
            raise ValueError("query cannot be empty")

        if not documents:
            raise ValueError("documents cannot be empty")

        if len(documents) != len(document_metadata):
            raise ValueError("documents and metadata must have same length")

        if not (0 <= temperature <= 1):
            raise ValueError("temperature must be between 0 and 1")

        if max_tokens <= 0:
            raise ValueError("max_tokens must be positive")

        # Initialize client if needed
        self._init_client()
        assert self._client is not None, "Client should be initialized"

        # Build document blocks with citations enabled
        content_blocks: List[Dict[str, Any]] = []

        for doc_text in documents:
            content_blocks.append({
                "type": "document",
                "source": {
                    "type": "text",
                    "media_type": "text/plain",
                    "data": doc_text
                },
                "citations": {"enabled": True}
            })

        # Add text query at the end
        content_blocks.append({
            "type": "text",
            "text": query.strip()
        })

        # Build message with mixed content
        messages: List["MessageParam"] = [
            cast("MessageParam", {
                "role": "user",
                "content": content_blocks
            })
        ]

        # Call Claude API
        try:
            response = self._client.messages.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
        except Exception as e:
            raise Exception(f"Claude API call failed: {str(e)}") from e

        # Extract text and citations from response
        result_text = ""
        evidence: List[Dict[str, Any]] = []

        for block in response.content:
            if block.type == "text":
                # Accumulate text from all text blocks
                text_block = cast("TextBlock", block)
                result_text += text_block.text

                # Extract citations if present
                if hasattr(block, "citations") and block.citations:
                    for citation in block.citations:
                        # Map citation back to source metadata
                        doc_idx = citation.document_index
                        metadata = document_metadata[doc_idx]

                        # Build evidence entry with all metadata fields
                        # citation has: cited_text, document_index, and a location object
                        # location is a CitationCharLocation with start and end attributes
                        location_dict = {
                            "start": citation.location.start,
                            "end": citation.location.end
                        } if hasattr(citation, "location") and citation.location else None

                        evidence_entry = {
                            "cited_text": citation.cited_text,
                            "document_index": doc_idx,
                            "location": location_dict,
                            **metadata  # Include all metadata fields
                        }

                        evidence.append(evidence_entry)

        # Track token usage
        self.total_input_tokens += response.usage.input_tokens
        self.total_output_tokens += response.usage.output_tokens

        return {
            "text": result_text,
            "evidence": evidence
        }

    def generate_with_tools(
        self,
        prompt: str,
        tools: List[Dict[str, Any]],
        tool_executor: callable,
        max_iterations: int = 10,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        prune_history: bool = True,
        keep_last_n: int = 3
    ) -> Dict[str, Any]:
        """
        Generate response with tool calling capability.

        Claude can make multiple tool calls, receive results, and continue reasoning.
        This enables autonomous information gathering and multi-step reasoning.

        Args:
            prompt: Initial prompt/task for Claude
            tools: List of tool definitions (Anthropic API format)
            tool_executor: Callback function to execute tools
                          Should have signature: fn(tool_name: str, **kwargs) -> Dict
            max_iterations: Max tool-call rounds (default: 10)
            system_prompt: Optional system prompt
            temperature: Sampling temperature (default: 0.3)
            max_tokens: Max tokens to generate (default: 4096)
            prune_history: If True, keep only recent conversation to reduce tokens (default: True)
            keep_last_n: Number of recent tool exchanges to keep when pruning (default: 3)

        Returns:
            {
                "final_response": "Claude's final answer",
                "tool_calls": [
                    {
                        "tool": "search_wiki",
                        "input": {"query": "..."},
                        "result": {...}
                    },
                    ...
                ],
                "usage": {
                    "total_input_tokens": N,
                    "total_output_tokens": M,
                    "estimated_cost_usd": X.XX,
                    "iterations": I
                }
            }

        Raises:
            RuntimeError: If max iterations reached without completion
            ValueError: If tool execution fails

        Example:
            >>> def my_tool_executor(name, **kwargs):
            ...     if name == "search":
            ...         return {"result": "..."}
            >>>
            >>> result = client.generate_with_tools(
            ...     prompt="Find info about Aang",
            ...     tools=[{"name": "search", ...}],
            ...     tool_executor=my_tool_executor
            ... )
        """
        # Validate inputs
        if not prompt or not prompt.strip():
            raise ValueError("prompt cannot be empty")

        if not tools:
            raise ValueError("tools cannot be empty")

        if not callable(tool_executor):
            raise ValueError("tool_executor must be callable")

        if not (0 <= temperature <= 1):
            raise ValueError("temperature must be between 0 and 1")

        if max_tokens <= 0:
            raise ValueError("max_tokens must be positive")

        # Initialize client if needed
        self._init_client()
        assert self._client is not None, "Client should be initialized"

        import json

        conversation: List["MessageParam"] = [
            cast("MessageParam", {"role": "user", "content": prompt.strip()})
        ]
        all_tool_calls = []
        iteration_input_tokens = 0
        iteration_output_tokens = 0

        for iteration in range(max_iterations):
            print(f"[INFO] Tool iteration {iteration + 1}/{max_iterations}")

            # OPTIMIZATION: Prune conversation history to reduce token usage
            # Keep only the original task and last N tool exchanges
            if prune_history and iteration > 0:
                conversation = self._prune_conversation(conversation, keep_last_n)

            # Call Claude with tools available
            try:
                if system_prompt:
                    response = self._client.messages.create(
                        model=self.model,
                        messages=conversation,
                        tools=tools,
                        system=system_prompt,
                        temperature=temperature,
                        max_tokens=max_tokens
                    )
                else:
                    response = self._client.messages.create(
                        model=self.model,
                        messages=conversation,
                        tools=tools,
                        temperature=temperature,
                        max_tokens=max_tokens
                    )
            except Exception as e:
                raise RuntimeError(f"LLM API call failed: {e}") from e

            # Track usage
            if hasattr(response, "usage"):
                iteration_input_tokens += response.usage.input_tokens
                iteration_output_tokens += response.usage.output_tokens

            # Check if Claude made tool calls
            if response.stop_reason == "tool_use":
                # Extract and execute tool calls
                tool_results = []

                for block in response.content:
                    if block.type == "tool_use":
                        tool_name = block.name
                        tool_input = block.input

                        print(f"[INFO] Claude called tool: {tool_name}")
                        print(f"[INFO] Tool input: {tool_input}")

                        # Execute tool via callback
                        try:
                            tool_result = tool_executor(tool_name, **tool_input)
                        except Exception as e:
                            # Return error to Claude so it can handle it
                            tool_result = {
                                "error": str(e),
                                "success": False
                            }
                            print(f"[ERROR] Tool execution failed: {e}")

                        print(f"[INFO] Tool result: {tool_result}")

                        # Track tool call
                        all_tool_calls.append({
                            "tool": tool_name,
                            "input": tool_input,
                            "result": tool_result
                        })

                        # Prepare tool result for Claude
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(tool_result)
                        })

                # Add assistant response and tool results to conversation
                conversation.append(
                    cast("MessageParam", {
                        "role": "assistant",
                        "content": response.content
                    })
                )
                conversation.append(
                    cast("MessageParam", {
                        "role": "user",
                        "content": tool_results
                    })
                )

                # Continue loop to let Claude process results
                continue

            elif response.stop_reason == "end_turn":
                # Claude finished - extract final response
                final_text = ""
                for block in response.content:
                    if hasattr(block, "text"):
                        final_text += block.text

                print(f"[INFO] Tool calling complete after {iteration + 1} iterations")
                print(f"[INFO] Total tool calls: {len(all_tool_calls)}")

                # Track total usage
                self.total_input_tokens += iteration_input_tokens
                self.total_output_tokens += iteration_output_tokens

                # Calculate cost
                estimated_cost = self.estimate_cost(iteration_input_tokens, iteration_output_tokens)

                self._ensure_llm_logger()
                if self.llm_logger:
                    self.llm_logger.log_prompt(
                        prompt=prompt,
                        model=self.model,
                        purpose="tool_based_generation",
                        response=final_text,
                        usage={
                            "input_tokens": iteration_input_tokens,
                            "output_tokens": iteration_output_tokens
                        },
                        cost=estimated_cost,
                        metadata={
                            "iterations": iteration + 1,
                            "tool_calls_count": len(all_tool_calls)
                        }
                    )

                    for tool_call in all_tool_calls:
                        self.llm_logger.log_tool_call(
                            tool_name=tool_call["tool"],
                            tool_input=tool_call["input"],
                            result=tool_call.get("result"),
                            error=tool_call.get("error")
                        )

                return {
                    "final_response": final_text,
                    "tool_calls": all_tool_calls,
                    "usage": {
                        "total_input_tokens": iteration_input_tokens,
                        "total_output_tokens": iteration_output_tokens,
                        "estimated_cost_usd": estimated_cost,
                        "iterations": iteration + 1
                    }
                }

            else:
                # Unexpected stop reason
                print(f"[WARN] Unexpected stop reason: {response.stop_reason}")
                break

        # Max iterations reached
        raise RuntimeError(
            f"Max iterations ({max_iterations}) reached without completion. "
            f"Claude may need more iterations or there may be an issue with the task."
        )

    def _prune_conversation(
        self,
        messages: List["MessageParam"],
        keep_last_n: int = 3
    ) -> List["MessageParam"]:
        """
        Prune conversation to keep only recent exchanges.

        This prevents unbounded context growth while maintaining recent
        context for coherent responses. Significantly reduces token usage
        in multi-iteration tool calling.

        Strategy:
        - Keep first message (original task description)
        - Keep last N exchanges (assistant + user pairs)
        - Discard older exchanges in the middle

        Args:
            messages: Full conversation history
            keep_last_n: Number of recent exchanges to keep (default: 3)

        Returns:
            Pruned conversation

        Example:
            Original (7 messages):
            [user_task, assistant_1, user_result_1, assistant_2, user_result_2, assistant_3, user_result_3]

            Pruned with keep_last_n=2:
            [user_task, assistant_2, user_result_2, assistant_3, user_result_3]
        """
        # If conversation is short enough, don't prune
        # Need at least: 1 task + (keep_last_n * 2) messages
        if len(messages) <= (keep_last_n * 2 + 1):
            return messages

        # Keep first message (original task)
        task_message = messages[0]

        # Keep last N exchanges (each exchange = 2 messages: assistant + user)
        # Last N exchanges = last (N * 2) messages
        recent_exchanges = messages[-(keep_last_n * 2):]

        # Rebuild conversation: task + recent exchanges
        pruned = [task_message] + recent_exchanges

        return pruned
