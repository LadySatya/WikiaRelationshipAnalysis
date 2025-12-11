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

from ..rag.query_engine import QueryEngine

logger = get_logger("processor.knowledge_builder")


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

    def build_knowledge_base(self, max_pages: Optional[int] = None) -> Dict[str, Any]:
        """
        Build knowledge base by processing all crawled pages.

        Args:
            max_pages: Optional limit on number of pages to process

        Returns:
            Final knowledge base dictionary
        """
        # Load all crawled pages
        pages = self._load_crawled_pages()

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

        for i, page in enumerate(pages, 1):
            page_title = page.get("title", "Unknown")
            page_url = page.get("url", "")

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

                self.knowledge_base["metadata"]["pages_processed"] = i
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
                    logger.error("Add credits at https://console.anthropic.com/settings/billing")
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
        # Reset canon state for new page
        self.current_page_canon = None

        title = page.get("title", "Unknown")
        url = page.get("url", "")
        content = page.get("main_content", "")
        infobox = page.get("infobox_data", {})
        categories = page.get("categories", [])

        # Build task prompt with page content
        task_prompt = self._build_task_prompt(title, url, content, infobox, categories)

        # Execute with tools
        def tool_executor(tool_name: str, **tool_input):
            return self._execute_kb_tool(tool_name, tool_input)

        result = self.query_engine.llm_client.generate_with_tools(
            prompt=task_prompt,
            tools=self.kb_tools,
            tool_executor=tool_executor,
            max_iterations=50,  # Allow many tool calls for thorough extraction
            system_prompt=self.system_prompt,
            temperature=0.1,  # Low temperature for factual extraction
            prune_history=True,  # Prune to avoid context overflow
            keep_last_n=10,
        )

        # Calculate cost (Haiku pricing: $0.80/1M input, $4.00/1M output)
        input_tokens = result["usage"].get("total_input_tokens", 0)
        output_tokens = result["usage"].get("total_output_tokens", 0)
        page_cost = (input_tokens * 0.80 / 1_000_000) + (output_tokens * 4.00 / 1_000_000)

        # Log the interaction
        self.llm_logger.log_prompt(
            prompt=task_prompt,
            model=self.query_engine.llm_client.model,
            purpose=f"knowledge_building:{title}",
            response=result["final_response"],
            usage={
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            },
            metadata={
                "page_title": title,
                "page_url": url,
                "tool_calls_made": len(result.get("tool_calls", [])),
                "iterations": result["usage"].get("iterations", 0),
                "estimated_cost": page_cost,
            },
        )

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
    ) -> str:
        """
        Build task prompt with page content.

        Args:
            title: Page title
            url: Page URL
            content: Main page content
            infobox: Infobox data
            categories: Page categories

        Returns:
            Task prompt string
        """
        # Truncate content to avoid token limits (keep first 3000 chars)
        content_excerpt = content[:3000] if content else "No content available"

        # Format infobox
        infobox_str = ""
        if infobox:
            infobox_lines = [f"  - {k}: {v}" for k, v in list(infobox.items())[:10]]
            infobox_str = "\n".join(infobox_lines)

        # Format categories
        categories_str = ", ".join(categories[:15]) if categories else "(no categories)"

        prompt = f"""Process this wiki page and extract all characters and relationships.

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
1. FIRST call determine_canon() to declare the canon for this page
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

            elif tool_name == "create_relationship":
                return self._tool_create_relationship(
                    character_a=tool_input.get("character_a", ""),
                    character_b=tool_input.get("character_b", ""),
                    canon=tool_input.get("canon", ""),
                    relationship_type=tool_input.get("relationship_type", ""),
                    summary=tool_input.get("summary", ""),
                )

            elif tool_name == "add_relationship_claim":
                return self._tool_add_relationship_claim(
                    character_a=tool_input.get("character_a", ""),
                    character_b=tool_input.get("character_b", ""),
                    canon=tool_input.get("canon", ""),
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

        if name in self.knowledge_base["characters"][canon]:
            return {
                "error": f"Character '{name}' already exists in canon '{canon}'",
                "success": False,
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
        return {"success": True, "name": name, "canon": canon}

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

    def _tool_create_relationship(
        self,
        character_a: str,
        character_b: str,
        canon: str,
        relationship_type: str,
        summary: str,
    ) -> Dict[str, Any]:
        """Create a new relationship between two existing characters in the same canon."""
        if not canon:
            return {"error": "canon is required", "success": False}

        canon = canon.lower()
        canon_chars = self.knowledge_base["characters"].get(canon, {})

        # Validate both characters exist in this canon
        missing = []
        if character_a not in canon_chars:
            missing.append(character_a)
        if character_b not in canon_chars:
            missing.append(character_b)

        if missing:
            return {
                "error": f"Character(s) not found in canon '{canon}': {', '.join(missing)}. Create them first with create_character().",
                "success": False,
                "hint": "If this is a group/organization (like 'Kyoshi Warriors' or 'Air Acolytes'), use add_affiliation() instead.",
            }

        key = self._normalize_relationship_key(character_a, character_b)

        # Ensure canon bucket exists for relationships
        if canon not in self.knowledge_base["relationships"]:
            self.knowledge_base["relationships"][canon] = {}

        if key in self.knowledge_base["relationships"][canon]:
            return {
                "error": f"Relationship between '{character_a}' and '{character_b}' already exists in canon '{canon}'",
                "success": False,
            }

        new_rel = {
            "characters": list(key),
            "canon": canon,
            "type": relationship_type,
            "summary": summary,
            "claims": [],
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        self.knowledge_base["relationships"][canon][key] = new_rel

        logger.info(
            f"Created relationship: {character_a} <-> {character_b} ({relationship_type}) [canon: {canon}]"
        )
        # Return relationship structure so LLM knows it starts with empty claims
        return {
            "success": True,
            "characters": list(key),
            "canon": canon,
            "type": relationship_type,
            "claim_count": 0,
        }

    def _tool_add_relationship_claim(
        self,
        character_a: str,
        character_b: str,
        canon: str,
        claim: str,
        evidence_url: str,
        evidence_text: str,
    ) -> Dict[str, Any]:
        """Add a claim to an existing relationship in a specific canon."""
        if not canon:
            return {"error": "canon is required", "success": False}

        canon = canon.lower()
        key = self._normalize_relationship_key(character_a, character_b)
        canon_rels = self.knowledge_base["relationships"].get(canon, {})

        if key not in canon_rels:
            return {
                "error": f"Relationship between '{character_a}' and '{character_b}' not found in canon '{canon}'. Create it first.",
                "success": False,
            }

        rel_data = canon_rels[key]

        # Find or create claim
        claims_list = rel_data.setdefault("claims", [])
        existing_claim = None

        for claim_entry in claims_list:
            if claim_entry.get("claim") == claim:
                existing_claim = claim_entry
                break

        # Create new evidence entry
        new_evidence = {
            "evidence_url": evidence_url,
            "evidence_text": evidence_text[:200],  # Truncate to 200 chars
            "added_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }

        if existing_claim:
            # Add to existing claim's evidence array
            evidence_list = existing_claim.setdefault("evidence", [])
            evidence_list.append(new_evidence)
            # Return the full updated claim so LLM can see all existing evidence
            return {
                "success": True,
                "canon": canon,
                "claim_count": len(claims_list),
                "evidence_count": len(evidence_list),
                "updated_claim": {
                    "claim": claim,
                    "evidence": evidence_list,  # Show all evidence for this claim
                },
            }
        else:
            # Create new claim with evidence array
            new_claim = {"claim": claim, "evidence": [new_evidence]}
            claims_list.append(new_claim)
            rel_data["updated_at"] = (
                datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            )
            # Return the new claim so LLM sees the structure
            return {
                "success": True,
                "canon": canon,
                "claim_count": len(claims_list),
                "evidence_count": 1,
                "updated_claim": new_claim,
            }

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
                        "page_title": evidence.get("page_title", ""),
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
            "last_saved": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "total_processed": len(self.processed_pages),
        }
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(state_data, f, indent=2, ensure_ascii=False)

        logger.info(
            f"Saved {total_chars} characters and {total_rels} relationships across {len(metadata['canons'])} canons"
        )
