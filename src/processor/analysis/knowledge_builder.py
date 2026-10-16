"""
CharacterKnowledgeBuilder - Unified character discovery and relationship extraction.

This module combines character discovery and relationship extraction into a single pass.
The LLM processes wiki pages one at a time, extracting characters and relationships while
maintaining an in-memory knowledge base that it can query and update via tools.

Key features:
- Single-pass processing (no separate discovery/profiling phases)
- Tool-based knowledge base interaction
- Incremental learning with RAG support
- Automatic deduplication via search tools
"""

import json
import re
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.utils.logging_config import get_llm_logger, get_logger
from src.utils.tool_schema_loader import load_system_prompt, load_tool_schemas

from ..config import get_config
from ..rag.query_engine import QueryEngine

logger = get_logger("processor.knowledge_builder")


def split_into_windows(text: str, window_chars: int) -> List[str]:
    """
    Split page text into consecutive windows of at most window_chars characters.

    Breaks after the last sentence end (". ") in the second half of each window;
    text with no sentence break there is split hard at the limit. No text is
    dropped - the windows together cover the whole page.

    Args:
        text: Page text (crawled pages are a single line, so sentences are the
            natural boundary)
        window_chars: Maximum characters per window

    Returns:
        List of windows (empty for empty text)
    """
    text = text.strip()
    windows: List[str] = []
    start = 0
    while start < len(text):
        end = start + window_chars
        if end < len(text):
            boundary = text.rfind(". ", start + window_chars // 2, end)
            if boundary != -1:
                end = boundary + 1  # keep the period, drop the space
        window = text[start:end].strip()
        if window:
            windows.append(window)
        start = end
    return windows


class CharacterKnowledgeBuilder:
    """
    Build character knowledge base from wiki pages in a single pass.

    Processes pages sequentially, extracting characters and relationships.
    The LLM uses tools to interact with an in-memory knowledge base,
    checking for existing entries and adding new information incrementally.

    Args:
        project_name: Name of the wikia project
        save_frequency: Save KB to disk every N pages (default: 10)

    Example:
        >>> builder = CharacterKnowledgeBuilder("avatar_wiki")
        >>> builder.build_knowledge_base()
        >>> builder.save()
    """

    def __init__(self, project_name: str, save_frequency: int = 10) -> None:
        """
        Initialize CharacterKnowledgeBuilder for a specific project.

        Args:
            project_name: Name of the wikia project
            save_frequency: Save KB to disk every N pages
        """
        self.project_name = project_name
        self.save_frequency = save_frequency

        # Pages are read in windows; pages over the cap are recorded as partial
        config = get_config()
        self.window_chars = config.knowledge_window_chars
        self.max_windows_per_page = config.knowledge_max_windows_per_page
        self.partial_pages: Dict[str, Dict[str, int]] = {}

        # Normalized quotable text per page URL; evidence quotes are checked
        # against it (see _tool_add_relationship)
        self.page_texts: Dict[str, str] = {}
        self.current_page_url: Optional[str] = None
        self.evidence_rejections = 0

        # Initialize query engine for RAG
        self.query_engine = QueryEngine(project_name=project_name)

        # Load tool schemas and system prompt
        self.kb_tools = load_tool_schemas("knowledge_building")
        self.system_prompt = load_system_prompt("knowledge_building_system")

        # Initialize LLM logger
        project_log_dir = Path("data/projects") / self.project_name / "logs"
        self.llm_logger = get_llm_logger(project_log_dir)

        # Setup paths
        self.project_dir = Path("data") / "projects" / project_name
        self.characters_dir = self.project_dir / "characters"
        self.relationships_dir = self.project_dir / "relationships"
        self.state_file = self.project_dir / "cache" / "discovery_state.json"

        # In-memory knowledge base (canon-aware)
        # Structure: characters[canon][name] -> character data
        #           relationships[canon][(char_a, char_b)] -> relationship data
        self.knowledge_base: Dict[str, Any] = {
            "characters": {},  # canon -> {name -> character data}
            "relationships": {},  # canon -> {(char_a, char_b) -> relationship data}
            "metadata": {
                "project_name": project_name,
                "created_at": datetime.now(timezone.utc)
                .isoformat()
                .replace("+00:00", "Z"),
                "pages_processed": 0,
                "last_updated": None,
            },
        }

        # Set when a run stops early because max_cost was reached
        self.budget_exhausted = False

        # Track which pages have been fully processed (for resume support)
        # Key: page URL, Value: timestamp of completion
        self.processed_pages: Dict[str, str] = {}

        # Track current page's canon (set by determine_canon tool)
        self.current_page_canon: Optional[str] = None

        # Load existing state if available (for resume)
        self._load_existing_state()

        logger.info(
            f"CharacterKnowledgeBuilder initialized with {len(self.kb_tools)} tools"
        )
        logger.info(f"Tools: {[t['name'] for t in self.kb_tools]}")

    def _load_existing_state(self) -> None:
        """
        Load existing discovery state and knowledge base for resume support.

        This loads:
        1. Processed pages list (to know what to skip)
        2. Existing characters from disk into memory
        3. Existing relationships from disk into memory
        """
        # Load processed pages state
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    state_data = json.load(f)
                self.processed_pages = state_data.get("processed_pages", {})
                self.partial_pages = state_data.get("partial_pages", {})
                logger.info(
                    f"Loaded discovery state: {len(self.processed_pages)} pages "
                    f"previously processed"
                )
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Failed to load discovery state: {e}")
                self.processed_pages = {}

        # Load existing characters into memory
        if self.characters_dir.exists():
            char_count = 0
            for char_file in self.characters_dir.glob("*.json"):
                try:
                    with open(char_file, "r", encoding="utf-8") as f:
                        char_data = json.load(f)
                    canon = char_data.get("canon", "main")
                    name = char_data.get("name", char_file.stem)

                    if canon not in self.knowledge_base["characters"]:
                        self.knowledge_base["characters"][canon] = {}
                    self.knowledge_base["characters"][canon][name] = char_data
                    char_count += 1
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"Failed to load character {char_file}: {e}")

            if char_count > 0:
                logger.info(f"Loaded {char_count} existing characters from disk")

        # Load existing relationships into memory
        if self.relationships_dir.exists():
            rel_count = 0
            for rel_file in self.relationships_dir.glob("*.json"):
                # Skip legacy graph.json file
                if rel_file.name == "graph.json":
                    continue
                try:
                    with open(rel_file, "r", encoding="utf-8") as f:
                        rel_data = json.load(f)
                    canon = rel_data.get("canon", "main")
                    chars = rel_data.get("characters", [])
                    if len(chars) >= 2:
                        # Normalize key order
                        key = tuple(sorted([chars[0], chars[1]]))

                        if canon not in self.knowledge_base["relationships"]:
                            self.knowledge_base["relationships"][canon] = {}
                        self.knowledge_base["relationships"][canon][key] = rel_data
                        rel_count += 1
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"Failed to load relationship {rel_file}: {e}")

            if rel_count > 0:
                logger.info(f"Loaded {rel_count} existing relationships from disk")

    def build_knowledge_base(
        self, max_pages: Optional[int] = None, max_cost: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Build knowledge base by processing all crawled pages.

        Args:
            max_pages: Optional limit on number of pages to process
            max_cost: Optional spending cap in USD. No new page is started once
                this run has spent at least this much, so a run can exceed it by
                up to one page's cost. Remaining pages are left for resume.

        Returns:
            Final knowledge base dictionary
        """
        # Load all crawled pages
        pages = self._load_crawled_pages()
        self.page_texts = {
            page["url"]: self._quotable_text(page) for page in pages if page.get("url")
        }

        if max_pages:
            pages = pages[:max_pages]
            logger.info(f"Limited to {max_pages} pages")

        logger.info(f"Processing {len(pages)} pages...")

        # Track success/failure counts
        success_count = 0
        failure_count = 0
        skipped_count = 0
        consecutive_failures = 0
        total_cost = 0.0
        self.budget_exhausted = False

        for i, page in enumerate(pages, 1):
            page_title = page.get("title", "Unknown")
            page_url = page.get("url", "")

            if max_cost is not None and total_cost >= max_cost:
                self.budget_exhausted = True
                logger.warning(
                    f"Spending cap reached: ${total_cost:.4f} spent (max_cost "
                    f"${max_cost:.2f}). Stopping before page {i}/{len(pages)}; "
                    f"run discover again to resume."
                )
                break

            # Skip already-processed pages (resume support)
            if page_url and page_url in self.processed_pages:
                skipped_count += 1
                if skipped_count <= 3 or skipped_count % 50 == 0:
                    logger.info(
                        f"[{i}/{len(pages)}] Skipping (already processed): {page_title}"
                    )
                continue

            logger.info(f"[{i}/{len(pages)}] Processing: {page_title}")

            try:
                page_cost = self._process_page(page)

                # Mark page as successfully processed AFTER full completion
                # This is critical for resume - partial processing won't be marked
                if page_url:
                    self.processed_pages[page_url] = (
                        datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                    )

                self.knowledge_base["metadata"]["pages_processed"] = len(
                    self.processed_pages
                )
                success_count += 1
                consecutive_failures = 0  # Reset on success
                if page_cost:
                    total_cost += page_cost

                # Log running totals every 10 pages
                if success_count % 10 == 0:
                    logger.info(
                        f"Progress: {success_count} pages succeeded, "
                        f"{failure_count} failed, {skipped_count} skipped, "
                        f"${total_cost:.4f} spent"
                    )

                # Save periodically (includes processed_pages state)
                if success_count % self.save_frequency == 0:
                    logger.info(f"Saving KB (processed {success_count} pages)...")
                    self.save()

            except Exception as e:
                failure_count += 1
                consecutive_failures += 1
                error_msg = str(e)

                # Detect credit exhaustion specifically
                if "credit balance is too low" in error_msg:
                    logger.error(
                        f"API CREDIT EXHAUSTED at page {i}/{len(pages)}. "
                        f"Successfully processed: {success_count} pages. "
                        f"Estimated cost: ${total_cost:.4f}"
                    )
                    logger.error(
                        "Add credits at https://console.anthropic.com/settings/billing"
                    )
                    # Save what we have and stop
                    logger.info("Saving partial results before stopping...")
                    self.save()
                    break
                else:
                    logger.error(f"Failed to process page '{page_title}': {e}")

                # Stop if too many consecutive failures (likely systemic issue)
                if consecutive_failures >= 5:
                    logger.error(
                        f"Stopping after {consecutive_failures} consecutive failures. "
                        f"Last error: {error_msg}"
                    )
                    self.save()
                    break

                continue

        # Final save and summary
        logger.info("Processing complete. Saving final KB...")
        self.save()

        # Clear summary of what happened
        logger.info("=" * 60)
        logger.info("DISCOVERY SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Pages in corpus:  {len(pages)}")
        logger.info(f"Pages skipped:    {skipped_count} (already processed)")
        logger.info(f"Pages attempted:  {success_count + failure_count}")
        logger.info(f"Pages succeeded:  {success_count}")
        logger.info(f"Pages failed:     {failure_count}")
        logger.info(f"Estimated cost:   ${total_cost:.4f}")
        logger.info(f"Total processed:  {len(self.processed_pages)} (cumulative)")
        logger.info(
            f"Evidence rejected: {self.evidence_rejections} quotes not found on the "
            f"cited page (model was asked to retry)"
        )
        if self.partial_pages:
            logger.warning(
                f"Partly read:      {len(self.partial_pages)} pages hit "
                f"max_windows_per_page ({self.max_windows_per_page}); see "
                f"partial_pages in {self.state_file}"
            )

        # Print summary (count across all canons)
        char_count = sum(
            len(chars) for chars in self.knowledge_base["characters"].values()
        )
        rel_count = sum(
            len(rels) for rels in self.knowledge_base["relationships"].values()
        )
        canon_count = len(self.knowledge_base["characters"])
        logger.info(
            f"Knowledge base complete: {char_count} characters, {rel_count} relationships across {canon_count} canons"
        )

        return self.knowledge_base

    def _process_page(self, page: Dict[str, Any]) -> Optional[float]:
        """
        Process a single page, extracting characters and relationships.

        Args:
            page: Page dictionary with title, content, infobox, etc.

        Returns:
            Estimated cost for this page, or None if unknown
        """
        # Reset canon state for new page (kept across this page's windows)
        self.current_page_canon = None

        title = page.get("title", "Unknown")
        url = page.get("url", "")
        self.current_page_url = url
        content = page.get("main_content", "")
        infobox = page.get("infobox_data", {})
        categories = page.get("categories", [])

        # Read the whole page in windows; each window is its own short conversation
        # and the knowledge base (via tools) carries what earlier windows found.
        windows = split_into_windows(content, self.window_chars) or [""]
        window_count = len(windows)
        if window_count > self.max_windows_per_page:
            logger.warning(
                f"Page '{title}' has {window_count} windows; reading only the first "
                f"{self.max_windows_per_page} (max_windows_per_page). Page is "
                f"recorded as partly read."
            )
            self.partial_pages[url] = {
                "windows_processed": self.max_windows_per_page,
                "windows_total": window_count,
            }
            windows = windows[: self.max_windows_per_page]

        def tool_executor(tool_name: str, **tool_input):
            return self._execute_kb_tool(tool_name, tool_input)

        page_cost = 0.0
        for index, window in enumerate(windows, 1):
            if window_count > 1:
                logger.info(f"  Window {index}/{window_count} ({len(window)} chars)")

            task_prompt = self._build_task_prompt(
                title,
                url,
                window,
                infobox if index == 1 else {},
                categories,
                window_index=index,
                window_count=window_count,
            )

            purpose = f"knowledge_building:{title} [part {index}/{window_count}]"
            result = self.query_engine.llm_client.generate_with_tools(
                prompt=task_prompt,
                tools=self.kb_tools,
                tool_executor=tool_executor,
                max_iterations=50,  # Allow many tool calls for thorough extraction
                system_prompt=self.system_prompt,
                prune_history=True,  # Prune to avoid context overflow
                keep_last_n=10,
                # LLMClient writes the single prompts.jsonl entry for this window
                log_purpose=purpose,
                log_metadata={
                    "page_title": title,
                    "page_url": url,
                    "window_index": index,
                    "window_count": window_count,
                },
            )

            # Cost is calculated by LLMClient from its pricing table
            page_cost += result["usage"].get("estimated_cost_usd", 0.0)

        # Update metadata
        self.knowledge_base["metadata"]["last_updated"] = (
            datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        )

        return page_cost

    def _build_task_prompt(
        self,
        title: str,
        url: str,
        content: str,
        infobox: Dict[str, Any],
        categories: List[str],
        window_index: int = 1,
        window_count: int = 1,
    ) -> str:
        """
        Build task prompt for one window of a page.

        Args:
            title: Page title
            url: Page URL
            content: Text of this window (the full page text is split by
                split_into_windows; nothing is truncated here)
            infobox: Infobox data (pass {} for windows after the first)
            categories: Page categories
            window_index: 1-based number of this window
            window_count: Total windows for the page

        Returns:
            Task prompt string
        """
        content_excerpt = content if content else "No content available"

        # Format infobox (all fields - it is only sent with the first window)
        infobox_str = ""
        if infobox:
            infobox_str = "\n".join(f"  - {k}: {v}" for k, v in infobox.items())
        elif window_index > 1:
            infobox_str = "  (shown with part 1 of this page)"

        # Format categories
        categories_str = ", ".join(categories[:15]) if categories else "(no categories)"

        # Windowed pages: say which part this is and what earlier parts already did
        part_str = ""
        if window_count > 1:
            part_str = f"\nThis is part {window_index} of {window_count} of the page."
            if window_index > 1:
                part_str += (
                    " Earlier parts were already processed: their characters and"
                    " relationships are in the knowledge base, so search before"
                    " creating."
                )

        if window_index > 1 and self.current_page_canon:
            canon_step = (
                f"1. The canon for this page is already set to "
                f"'{self.current_page_canon}' - do not call determine_canon() again"
            )
        else:
            canon_step = (
                "1. FIRST call determine_canon() to declare the canon for this page"
            )

        prompt = f"""Process this wiki page and extract all characters and relationships.{part_str}

<page>
Title: {title}
URL: {url}
Categories: {categories_str}

Infobox:
{infobox_str if infobox_str else "  (no infobox)"}

Content:
{content_excerpt}
</page>

Use the available tools to:
{canon_step}
2. Check for existing characters (avoid duplicates)
3. Create new character entries with the determined canon
4. Extract and document relationships with evidence (within the same canon)

Be thorough - extract all characters mentioned, not just the page subject.
"""
        return prompt

    # === TOOL EXECUTORS ===

    def _execute_kb_tool(
        self, tool_name: str, tool_input: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a knowledge base tool.

        Args:
            tool_name: Name of the tool
            tool_input: Tool parameters

        Returns:
            Tool result dictionary
        """
        try:
            if tool_name == "determine_canon":
                return self._tool_determine_canon(
                    canon=tool_input.get("canon", "main"),
                    reasoning=tool_input.get("reasoning", ""),
                )

            elif tool_name == "search_characters":
                return self._tool_search_characters(
                    query=tool_input.get("query", ""),
                    canon=tool_input.get("canon"),  # Optional filter
                )

            elif tool_name == "get_character":
                return self._tool_get_character(
                    name=tool_input.get("name", ""), canon=tool_input.get("canon", "")
                )

            elif tool_name == "create_character":
                return self._tool_create_character(
                    name=tool_input.get("name", ""),
                    canon=tool_input.get("canon", ""),
                    aliases=tool_input.get("aliases", []),
                    bio=tool_input.get("bio", ""),
                    source_url=tool_input.get("source_url", ""),
                )

            elif tool_name == "update_character":
                return self._tool_update_character(
                    name=tool_input.get("name", ""),
                    canon=tool_input.get("canon", ""),
                    add_aliases=tool_input.get("add_aliases", []),
                    bio=tool_input.get("bio"),
                    add_source_url=tool_input.get("add_source_url"),
                )

            elif tool_name == "get_relationship":
                return self._tool_get_relationship(
                    character_a=tool_input.get("character_a", ""),
                    character_b=tool_input.get("character_b", ""),
                    canon=tool_input.get("canon", ""),
                )

            elif tool_name == "add_relationship":
                return self._tool_add_relationship(
                    character_a=tool_input.get("character_a", ""),
                    character_b=tool_input.get("character_b", ""),
                    canon=tool_input.get("canon", ""),
                    relationship_type=tool_input.get("relationship_type", ""),
                    summary=tool_input.get("summary", ""),
                    claim=tool_input.get("claim", ""),
                    evidence_url=tool_input.get("evidence_url", ""),
                    evidence_text=tool_input.get("evidence_text", ""),
                )

            elif tool_name == "search_wiki":
                return self._tool_search_wiki(
                    query=tool_input.get("query", ""),
                    max_results=tool_input.get("max_results", 5),
                )

            elif tool_name == "add_affiliation":
                return self._tool_add_affiliation(
                    character_name=tool_input.get("character_name", ""),
                    canon=tool_input.get("canon", ""),
                    group=tool_input.get("group", ""),
                    role=tool_input.get("role"),
                    evidence_url=tool_input.get("evidence_url", ""),
                    evidence_text=tool_input.get("evidence_text", ""),
                )

            else:
                return {"error": f"Unknown tool: {tool_name}", "success": False}

        except Exception as e:
            logger.error(f"Tool '{tool_name}' failed: {e}")
            return {"error": str(e), "success": False}

    def _tool_determine_canon(self, canon: str, reasoning: str) -> Dict[str, Any]:
        """Set the canon for the current page being processed."""
        if not canon:
            canon = "main"

        # Normalize canon to lowercase
        canon = canon.lower().strip()

        # Set the current page canon
        self.current_page_canon = canon

        # Ensure canon bucket exists in knowledge base
        if canon not in self.knowledge_base["characters"]:
            self.knowledge_base["characters"][canon] = {}
        if canon not in self.knowledge_base["relationships"]:
            self.knowledge_base["relationships"][canon] = {}

        logger.info(f"Canon determined: {canon} - {reasoning}")

        return {
            "success": True,
            "canon": canon,
            "message": f"Canon set to '{canon}'. All subsequent characters and relationships will be stored in this canon.",
        }

    def _tool_search_characters(
        self, query: str, canon: Optional[str] = None
    ) -> Dict[str, Any]:
        """Search for characters using fuzzy matching, optionally filtered by canon."""
        if not query:
            return {"matches": [], "count": 0}

        query_lower = query.lower()
        matches = []

        # Determine which canons to search
        if canon:
            canons_to_search = [canon.lower()]
        else:
            canons_to_search = list(self.knowledge_base["characters"].keys())

        for search_canon in canons_to_search:
            canon_chars = self.knowledge_base["characters"].get(search_canon, {})
            for name, char_data in canon_chars.items():
                # Check name match
                name_similarity = SequenceMatcher(
                    None, query_lower, name.lower()
                ).ratio()
                if name_similarity > 0.6:
                    matches.append(
                        {
                            "name": name,
                            "canon": search_canon,
                            "aliases": char_data.get("aliases", []),
                            "similarity": round(name_similarity, 2),
                        }
                    )
                    continue

                # Check alias matches
                for alias in char_data.get("aliases", []):
                    alias_similarity = SequenceMatcher(
                        None, query_lower, alias.lower()
                    ).ratio()
                    if alias_similarity > 0.6:
                        matches.append(
                            {
                                "name": name,
                                "canon": search_canon,
                                "aliases": char_data.get("aliases", []),
                                "similarity": round(alias_similarity, 2),
                            }
                        )
                        break

        # Sort by similarity
        matches.sort(key=lambda x: x["similarity"], reverse=True)

        return {"matches": matches[:10], "count": len(matches)}  # Top 10 matches

    def _tool_get_character(self, name: str, canon: str) -> Optional[Dict[str, Any]]:
        """Get character data by name and canon."""
        if not canon:
            return {"error": "canon is required", "success": False}

        canon = canon.lower()
        canon_chars = self.knowledge_base["characters"].get(canon, {})
        return canon_chars.get(name)

    def _tool_create_character(
        self, name: str, canon: str, aliases: List[str], bio: str, source_url: str
    ) -> Dict[str, Any]:
        """Create a new character entry in the specified canon."""
        if not name:
            return {"error": "name is required", "success": False}

        if not canon:
            return {"error": "canon is required", "success": False}

        canon = canon.lower()

        # Ensure canon bucket exists
        if canon not in self.knowledge_base["characters"]:
            self.knowledge_base["characters"][canon] = {}

        existing = self.knowledge_base["characters"][canon].get(name)
        if existing:
            # Create-or-get: return the existing record instead of an error
            return {
                "success": True,
                "existed": True,
                "name": name,
                "canon": canon,
                "character": existing,
            }

        self.knowledge_base["characters"][canon][name] = {
            "name": name,
            "canon": canon,
            "aliases": aliases,
            "bio": bio,
            "source_urls": [source_url] if source_url else [],
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }

        logger.info(f"Created character: {name} (canon: {canon})")
        return {"success": True, "existed": False, "name": name, "canon": canon}

    def _tool_update_character(
        self,
        name: str,
        canon: str,
        add_aliases: Optional[List[str]] = None,
        bio: Optional[str] = None,
        add_source_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update an existing character in the specified canon."""
        if not canon:
            return {"error": "canon is required", "success": False}

        canon = canon.lower()
        canon_chars = self.knowledge_base["characters"].get(canon, {})

        if name not in canon_chars:
            return {
                "error": f"Character '{name}' not found in canon '{canon}'",
                "success": False,
            }

        char_data = canon_chars[name]

        if add_aliases:
            existing = set(char_data.get("aliases", []))
            char_data["aliases"] = list(existing | set(add_aliases))

        if bio is not None:
            char_data["bio"] = bio

        if add_source_url:
            if add_source_url not in char_data.get("source_urls", []):
                char_data.setdefault("source_urls", []).append(add_source_url)

        char_data["updated_at"] = (
            datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        )

        # Return updated character data so LLM can see current state
        return {
            "success": True,
            "name": name,
            "canon": canon,
            "aliases": char_data.get("aliases", []),
            "source_url_count": len(char_data.get("source_urls", [])),
        }

    def _normalize_relationship_key(self, char_a: str, char_b: str) -> Tuple[str, str]:
        """Normalize relationship key to alphabetical order."""
        return tuple(sorted([char_a, char_b]))

    def _tool_get_relationship(
        self, character_a: str, character_b: str, canon: str
    ) -> Optional[Dict[str, Any]]:
        """Get relationship data for a specific canon."""
        if not canon:
            return {"error": "canon is required", "success": False}

        canon = canon.lower()
        key = self._normalize_relationship_key(character_a, character_b)
        canon_rels = self.knowledge_base["relationships"].get(canon, {})
        return canon_rels.get(key)

    # Typographic characters normalized before quote matching (escaped: no
    # non-ASCII characters in .py files)
    _QUOTE_TRANSLATION = str.maketrans(
        {
            "\u2018": "'",
            "\u2019": "'",
            "\u201c": '"',
            "\u201d": '"',
            "\u2013": "-",
            "\u2014": "-",
        }
    )

    @classmethod
    def _normalize_quote(cls, text: str) -> str:
        """Lowercase, unify typographic quotes/dashes, and drop all whitespace."""
        return re.sub(r"\s+", "", text.translate(cls._QUOTE_TRANSLATION).lower())

    @classmethod
    def _quotable_text(cls, page: Dict[str, Any]) -> str:
        """Normalized text evidence can quote: main content plus 'Key: value' infobox lines."""
        infobox = page.get("infobox_data") or {}
        infobox_lines = "\n".join(f"{k}: {v}" for k, v in infobox.items())
        return cls._normalize_quote(
            f"{page.get('main_content') or ''}\n{infobox_lines}"
        )

    def _check_evidence(self, evidence_url: str, evidence_text: str) -> Optional[str]:
        """Return an error message if the evidence is not a quote from a crawled page."""
        if not evidence_text or not evidence_text.strip():
            return "evidence_text is required: an exact quote from the page."

        page_text = self.page_texts.get(evidence_url)
        if page_text is None:
            return (
                f"evidence_url '{evidence_url}' is not a crawled page. Cite the page "
                f"the quote comes from (current page: {self.current_page_url})."
            )

        if self._normalize_quote(evidence_text) not in page_text:
            return (
                f"evidence_text was not found on {evidence_url}. Copy one exact, "
                "contiguous passage word-for-word from the page content or infobox "
                "(e.g. 'Enemies: Ozai'). Do not paraphrase or join fragments with "
                "'...'. If no passage states this, do not add the claim."
            )

        return None

    def _tool_add_relationship(
        self,
        character_a: str,
        character_b: str,
        canon: str,
        relationship_type: str,
        summary: str,
        claim: str,
        evidence_url: str,
        evidence_text: str,
    ) -> Dict[str, Any]:
        """
        Create a relationship with its first claim, or add a claim to an existing one.

        Every call must carry a claim with an exact quote, which is verified before
        anything is stored - so a relationship never exists without evidence.
        Calling this for an existing relationship adds the claim (no error); the
        existing type and summary are kept and returned.
        """
        if not canon:
            return {"error": "canon is required", "success": False}
        if not claim or not claim.strip():
            return {
                "error": "claim is required: a specific factual statement.",
                "success": False,
            }

        canon = canon.lower()
        canon_chars = self.knowledge_base["characters"].get(canon, {})

        # Both characters must exist; suggest close names to save a search round
        missing = [c for c in (character_a, character_b) if c not in canon_chars]
        if missing:
            suggestions = {
                name: [
                    m["name"]
                    for m in self._tool_search_characters(name, canon)["matches"][:3]
                ]
                for name in missing
            }
            return {
                "error": f"Character(s) not found in canon '{canon}': "
                f"{', '.join(missing)}. Create them first with create_character(), "
                "or use one of the suggested existing names.",
                "success": False,
                "suggestions": suggestions,
                "hint": "If this is a group/organization (like 'Kyoshi Warriors' or "
                "'Air Acolytes'), use add_affiliation() instead.",
            }

        # Evidence must be a real quote from a crawled page - this keeps claims
        # grounded in ingested text rather than the model's prior knowledge
        evidence_error = self._check_evidence(evidence_url, evidence_text)
        if evidence_error:
            self.evidence_rejections += 1
            return {"error": evidence_error, "success": False}

        key = self._normalize_relationship_key(character_a, character_b)
        canon_rels = self.knowledge_base["relationships"].setdefault(canon, {})
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        created = key not in canon_rels
        if created:
            canon_rels[key] = {
                "characters": list(key),
                "canon": canon,
                "type": relationship_type,
                "summary": summary.strip() if summary and summary.strip() else claim,
                "claims": [],
                "created_at": now,
            }
            logger.info(
                f"Created relationship: {character_a} <-> {character_b} "
                f"({relationship_type}) [canon: {canon}]"
            )
        rel_data = canon_rels[key]

        new_evidence = {
            "evidence_url": evidence_url,
            "evidence_text": evidence_text[:200],  # Truncate to 200 chars
            "added_at": now,
        }
        claims_list = rel_data.setdefault("claims", [])
        claim_entry = next((c for c in claims_list if c.get("claim") == claim), None)
        if claim_entry:
            claim_entry.setdefault("evidence", []).append(new_evidence)
        else:
            claim_entry = {"claim": claim, "evidence": [new_evidence]}
            claims_list.append(claim_entry)
        rel_data["updated_at"] = now

        # Show the relationship as it now stands so the model can avoid duplicates
        result: Dict[str, Any] = {
            "success": True,
            "created": created,
            "characters": list(key),
            "canon": canon,
            "type": rel_data["type"],
            "summary": rel_data["summary"],
            "claims": [c["claim"] for c in claims_list],
            "updated_claim": claim_entry,
        }
        if not created and relationship_type and relationship_type != rel_data["type"]:
            result["note"] = (
                f"Relationship already existed with type '{rel_data['type']}'; "
                "type and summary were kept and your claim was added."
            )
        return result

    def _tool_search_wiki(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        """Search wiki using RAG."""
        if not query:
            return {"results": [], "count": 0}

        try:
            # Use RAG to search
            result = self.query_engine.query_with_citations(
                query=query, k=min(max_results, 10)
            )

            # Format results
            results = []
            for evidence in result.get("evidence", [])[:max_results]:
                results.append(
                    {
                        "text": evidence.get("cited_text", "")[:300],
                        "url": evidence.get("url", ""),
                        "page_title": evidence.get("title", ""),
                    }
                )

            return {
                "results": results,
                "count": len(results),
                "answer_summary": result.get("text", "")[:200],
            }

        except Exception as e:
            return {"error": str(e), "results": [], "count": 0}

    def _tool_add_affiliation(
        self,
        character_name: str,
        canon: str,
        group: str,
        evidence_url: str,
        evidence_text: str,
        role: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Add a group/organization affiliation to a character in a specific canon."""
        if not canon:
            return {"error": "canon is required", "success": False}

        canon = canon.lower()
        canon_chars = self.knowledge_base["characters"].get(canon, {})

        if character_name not in canon_chars:
            return {
                "error": f"Character '{character_name}' not found in canon '{canon}'. Create the character first with create_character().",
                "success": False,
            }

        char_data = canon_chars[character_name]
        affiliations = char_data.setdefault("affiliations", [])

        # Check if this group affiliation already exists (case-insensitive)
        existing = next(
            (a for a in affiliations if a["group"].lower() == group.lower()), None
        )

        if existing:
            # Update role if provided and different
            updated = False
            if role and existing.get("role") != role:
                existing["role"] = role
                existing["evidence_url"] = evidence_url
                existing["evidence_text"] = evidence_text[:200]
                updated = True

            return {
                "success": True,
                "message": f"Affiliation with '{group}' already exists"
                + (" (role updated)" if updated else ""),
                "character_name": character_name,
                "canon": canon,
                "current_affiliations": [
                    {"group": a["group"], "role": a.get("role")} for a in affiliations
                ],
                "affiliation_count": len(affiliations),
            }

        # Add new affiliation
        new_affiliation = {
            "group": group,
            "evidence_url": evidence_url,
            "evidence_text": evidence_text[:200],  # Truncate to 200 chars
        }
        if role:
            new_affiliation["role"] = role

        affiliations.append(new_affiliation)
        char_data["updated_at"] = (
            datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        )

        logger.info(
            f"Added affiliation: {character_name} -> {group} ({role or 'Member'}) [canon: {canon}]"
        )

        return {
            "success": True,
            "character_name": character_name,
            "canon": canon,
            "current_affiliations": [
                {"group": a["group"], "role": a.get("role")} for a in affiliations
            ],
            "affiliation_count": len(affiliations),
        }

    def _load_crawled_pages(self) -> List[Dict[str, Any]]:
        """Load all crawled pages from processed directory."""
        processed_dir = self.project_dir / "processed"

        if not processed_dir.exists():
            raise FileNotFoundError(f"No crawled pages found: {processed_dir}")

        pages = []
        for file_path in processed_dir.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    page_content = data.get("content", {})
                    if "url" not in page_content and "url" in data:
                        page_content["url"] = data["url"]
                    pages.append(page_content)
            except Exception as e:
                logger.warning(f"Failed to load page {file_path}: {e}")
                continue

        logger.info(f"Loaded {len(pages)} crawled pages")
        return pages

    def save(self) -> None:
        """Save knowledge base to disk."""
        # Ensure directories exist
        self.characters_dir.mkdir(parents=True, exist_ok=True)
        self.relationships_dir.mkdir(parents=True, exist_ok=True)

        # Count totals for logging
        total_chars = 0
        total_rels = 0

        # Save individual character files (canon-aware)
        for canon, canon_chars in self.knowledge_base["characters"].items():
            for char_name, char_data in canon_chars.items():
                safe_name = re.sub(r'[\\/:*?"<>|]', "_", char_name).replace(" ", "_")
                safe_canon = re.sub(r'[\\/:*?"<>|]', "_", canon).replace(" ", "_")
                filepath = self.characters_dir / f"{safe_name}_{safe_canon}.json"
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(char_data, f, indent=2, ensure_ascii=False)
                total_chars += 1

        # Save individual relationship files (canon-aware)
        for canon, canon_rels in self.knowledge_base["relationships"].items():
            for (char_a, char_b), rel_data in canon_rels.items():
                safe_a = re.sub(r'[\\/:*?"<>|]', "_", char_a).replace(" ", "_")
                safe_b = re.sub(r'[\\/:*?"<>|]', "_", char_b).replace(" ", "_")
                safe_canon = re.sub(r'[\\/:*?"<>|]', "_", canon).replace(" ", "_")
                filepath = (
                    self.relationships_dir / f"{safe_a}_{safe_b}_{safe_canon}.json"
                )
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(rel_data, f, indent=2, ensure_ascii=False)
                total_rels += 1

        # Save metadata with canon information
        metadata = self.knowledge_base["metadata"].copy()
        metadata["canons"] = list(self.knowledge_base["characters"].keys())
        metadata_file = self.project_dir / "knowledge_base_metadata.json"
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        # Save discovery state (processed pages list for resume support)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        state_data = {
            "processed_pages": self.processed_pages,
            "partial_pages": self.partial_pages,
            "last_saved": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "total_processed": len(self.processed_pages),
        }
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(state_data, f, indent=2, ensure_ascii=False)

        logger.info(
            f"Saved {total_chars} characters and {total_rels} relationships across {len(metadata['canons'])} canons"
        )
