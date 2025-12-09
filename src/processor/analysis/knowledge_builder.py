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
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import json
import re
from datetime import datetime, timezone
from difflib import SequenceMatcher

from ..rag.query_engine import QueryEngine
from src.utils.logging_config import get_logger, get_llm_logger
from src.utils.tool_schema_loader import load_tool_schemas, load_system_prompt

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

    def __init__(
        self,
        project_name: str,
        save_frequency: int = 10
    ) -> None:
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

        # In-memory knowledge base
        self.knowledge_base: Dict[str, Any] = {
            "characters": {},  # name -> character data
            "relationships": {},  # (char_a, char_b) -> relationship data
            "metadata": {
                "project_name": project_name,
                "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "pages_processed": 0,
                "last_updated": None
            }
        }

        logger.info(f"CharacterKnowledgeBuilder initialized with {len(self.kb_tools)} tools")
        logger.info(f"Tools: {[t['name'] for t in self.kb_tools]}")

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

        for i, page in enumerate(pages, 1):
            page_title = page.get("title", "Unknown")
            page_url = page.get("url", "")

            logger.info(f"[{i}/{len(pages)}] Processing: {page_title}")

            try:
                self._process_page(page)
                self.knowledge_base["metadata"]["pages_processed"] = i

                # Save periodically
                if i % self.save_frequency == 0:
                    logger.info(f"Saving KB (processed {i} pages)...")
                    self.save()

            except Exception as e:
                logger.error(f"Failed to process page '{page_title}': {e}")
                continue

        # Final save
        logger.info("Processing complete. Saving final KB...")
        self.save()

        # Print summary
        char_count = len(self.knowledge_base["characters"])
        rel_count = len(self.knowledge_base["relationships"])
        logger.info(f"Knowledge base complete: {char_count} characters, {rel_count} relationships")

        return self.knowledge_base

    def _process_page(self, page: Dict[str, Any]) -> None:
        """
        Process a single page, extracting characters and relationships.

        Args:
            page: Page dictionary with title, content, infobox, etc.
        """
        title = page.get("title", "Unknown")
        url = page.get("url", "")
        content = page.get("main_content", "")
        infobox = page.get("infobox_data", {})

        # Build task prompt with page content
        task_prompt = self._build_task_prompt(title, url, content, infobox)

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
            keep_last_n=10
        )

        # Log the interaction
        self.llm_logger.log_prompt(
            prompt=task_prompt,
            model=self.query_engine.llm_client.model,
            purpose=f"knowledge_building:{title}",
            response=result["final_response"],
            usage={
                "input_tokens": result["usage"].get("total_input_tokens", 0),
                "output_tokens": result["usage"].get("total_output_tokens", 0)
            },
            metadata={
                "page_title": title,
                "page_url": url,
                "tool_calls_made": len(result.get("tool_calls", [])),
                "iterations": result["usage"].get("iterations", 0)
            }
        )

        # Update metadata
        self.knowledge_base["metadata"]["last_updated"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def _build_task_prompt(
        self,
        title: str,
        url: str,
        content: str,
        infobox: Dict[str, Any]
    ) -> str:
        """
        Build task prompt with page content.

        Args:
            title: Page title
            url: Page URL
            content: Main page content
            infobox: Infobox data

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

        prompt = f"""Process this wiki page and extract all characters and relationships.

<page>
Title: {title}
URL: {url}

Infobox:
{infobox_str if infobox_str else "  (no infobox)"}

Content:
{content_excerpt}
</page>

Use the available tools to:
1. Check for existing characters (avoid duplicates)
2. Create new character entries
3. Extract and document relationships with evidence

Be thorough - extract all characters mentioned, not just the page subject.
"""
        return prompt

    # === TOOL EXECUTORS ===

    def _execute_kb_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a knowledge base tool.

        Args:
            tool_name: Name of the tool
            tool_input: Tool parameters

        Returns:
            Tool result dictionary
        """
        try:
            if tool_name == "search_characters":
                return self._tool_search_characters(tool_input.get("query", ""))

            elif tool_name == "get_character":
                return self._tool_get_character(tool_input.get("name", ""))

            elif tool_name == "create_character":
                return self._tool_create_character(
                    name=tool_input.get("name", ""),
                    aliases=tool_input.get("aliases", []),
                    bio=tool_input.get("bio", ""),
                    source_url=tool_input.get("source_url", "")
                )

            elif tool_name == "update_character":
                return self._tool_update_character(
                    name=tool_input.get("name", ""),
                    add_aliases=tool_input.get("add_aliases", []),
                    bio=tool_input.get("bio"),
                    add_source_url=tool_input.get("add_source_url")
                )

            elif tool_name == "get_relationship":
                return self._tool_get_relationship(
                    character_a=tool_input.get("character_a", ""),
                    character_b=tool_input.get("character_b", "")
                )

            elif tool_name == "create_relationship":
                return self._tool_create_relationship(
                    character_a=tool_input.get("character_a", ""),
                    character_b=tool_input.get("character_b", ""),
                    relationship_type=tool_input.get("relationship_type", ""),
                    summary=tool_input.get("summary", "")
                )

            elif tool_name == "add_relationship_claim":
                return self._tool_add_relationship_claim(
                    character_a=tool_input.get("character_a", ""),
                    character_b=tool_input.get("character_b", ""),
                    claim=tool_input.get("claim", ""),
                    evidence_url=tool_input.get("evidence_url", ""),
                    evidence_text=tool_input.get("evidence_text", "")
                )

            elif tool_name == "search_wiki":
                return self._tool_search_wiki(
                    query=tool_input.get("query", ""),
                    max_results=tool_input.get("max_results", 5)
                )

            elif tool_name == "add_affiliation":
                return self._tool_add_affiliation(
                    character_name=tool_input.get("character_name", ""),
                    group=tool_input.get("group", ""),
                    role=tool_input.get("role"),
                    evidence_url=tool_input.get("evidence_url", ""),
                    evidence_text=tool_input.get("evidence_text", "")
                )

            else:
                return {"error": f"Unknown tool: {tool_name}", "success": False}

        except Exception as e:
            logger.error(f"Tool '{tool_name}' failed: {e}")
            return {"error": str(e), "success": False}

    def _tool_search_characters(self, query: str) -> Dict[str, Any]:
        """Search for characters using fuzzy matching."""
        if not query:
            return {"matches": [], "count": 0}

        query_lower = query.lower()
        matches = []

        for name, char_data in self.knowledge_base["characters"].items():
            # Check name match
            name_similarity = SequenceMatcher(None, query_lower, name.lower()).ratio()
            if name_similarity > 0.6:
                matches.append({
                    "name": name,
                    "aliases": char_data.get("aliases", []),
                    "similarity": round(name_similarity, 2)
                })
                continue

            # Check alias matches
            for alias in char_data.get("aliases", []):
                alias_similarity = SequenceMatcher(None, query_lower, alias.lower()).ratio()
                if alias_similarity > 0.6:
                    matches.append({
                        "name": name,
                        "aliases": char_data.get("aliases", []),
                        "similarity": round(alias_similarity, 2)
                    })
                    break

        # Sort by similarity
        matches.sort(key=lambda x: x["similarity"], reverse=True)

        return {
            "matches": matches[:10],  # Top 10 matches
            "count": len(matches)
        }

    def _tool_get_character(self, name: str) -> Optional[Dict[str, Any]]:
        """Get character data by name."""
        return self.knowledge_base["characters"].get(name)

    def _tool_create_character(
        self,
        name: str,
        aliases: List[str],
        bio: str,
        source_url: str
    ) -> Dict[str, Any]:
        """Create a new character entry."""
        if not name:
            return {"error": "name is required", "success": False}

        if name in self.knowledge_base["characters"]:
            return {"error": f"Character '{name}' already exists", "success": False}

        self.knowledge_base["characters"][name] = {
            "name": name,
            "aliases": aliases,
            "bio": bio,
            "source_urls": [source_url] if source_url else [],
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        }

        logger.info(f"Created character: {name}")
        return {"success": True, "name": name}

    def _tool_update_character(
        self,
        name: str,
        add_aliases: Optional[List[str]] = None,
        bio: Optional[str] = None,
        add_source_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update an existing character."""
        if name not in self.knowledge_base["characters"]:
            return {"error": f"Character '{name}' not found", "success": False}

        char_data = self.knowledge_base["characters"][name]

        if add_aliases:
            existing = set(char_data.get("aliases", []))
            char_data["aliases"] = list(existing | set(add_aliases))

        if bio is not None:
            char_data["bio"] = bio

        if add_source_url:
            if add_source_url not in char_data.get("source_urls", []):
                char_data.setdefault("source_urls", []).append(add_source_url)

        char_data["updated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        # Return updated character data so LLM can see current state
        return {
            "success": True,
            "name": name,
            "aliases": char_data.get("aliases", []),
            "source_url_count": len(char_data.get("source_urls", []))
        }

    def _normalize_relationship_key(self, char_a: str, char_b: str) -> Tuple[str, str]:
        """Normalize relationship key to alphabetical order."""
        return tuple(sorted([char_a, char_b]))

    def _tool_get_relationship(self, character_a: str, character_b: str) -> Optional[Dict[str, Any]]:
        """Get relationship data."""
        key = self._normalize_relationship_key(character_a, character_b)
        return self.knowledge_base["relationships"].get(key)

    def _tool_create_relationship(
        self,
        character_a: str,
        character_b: str,
        relationship_type: str,
        summary: str
    ) -> Dict[str, Any]:
        """Create a new relationship between two existing characters."""
        # Validate both characters exist
        missing = []
        if character_a not in self.knowledge_base["characters"]:
            missing.append(character_a)
        if character_b not in self.knowledge_base["characters"]:
            missing.append(character_b)

        if missing:
            return {
                "error": f"Character(s) not found: {', '.join(missing)}. Create them first with create_character().",
                "success": False,
                "hint": "If this is a group/organization (like 'Kyoshi Warriors' or 'Air Acolytes'), use add_affiliation() instead."
            }

        key = self._normalize_relationship_key(character_a, character_b)

        if key in self.knowledge_base["relationships"]:
            return {"error": f"Relationship between '{character_a}' and '{character_b}' already exists", "success": False}

        new_rel = {
            "characters": list(key),
            "type": relationship_type,
            "summary": summary,
            "claims": [],
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        }
        self.knowledge_base["relationships"][key] = new_rel

        logger.info(f"Created relationship: {character_a} <-> {character_b} ({relationship_type})")
        # Return relationship structure so LLM knows it starts with empty claims
        return {
            "success": True,
            "characters": list(key),
            "type": relationship_type,
            "claim_count": 0
        }

    def _tool_add_relationship_claim(
        self,
        character_a: str,
        character_b: str,
        claim: str,
        evidence_url: str,
        evidence_text: str
    ) -> Dict[str, Any]:
        """Add a claim to an existing relationship."""
        key = self._normalize_relationship_key(character_a, character_b)

        if key not in self.knowledge_base["relationships"]:
            return {"error": f"Relationship between '{character_a}' and '{character_b}' not found. Create it first.", "success": False}

        rel_data = self.knowledge_base["relationships"][key]

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
            "added_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        }

        if existing_claim:
            # Add to existing claim's evidence array
            evidence_list = existing_claim.setdefault("evidence", [])
            evidence_list.append(new_evidence)
            # Return the full updated claim so LLM can see all existing evidence
            return {
                "success": True,
                "claim_count": len(claims_list),
                "evidence_count": len(evidence_list),
                "updated_claim": {
                    "claim": claim,
                    "evidence": evidence_list  # Show all evidence for this claim
                }
            }
        else:
            # Create new claim with evidence array
            new_claim = {
                "claim": claim,
                "evidence": [new_evidence]
            }
            claims_list.append(new_claim)
            rel_data["updated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            # Return the new claim so LLM sees the structure
            return {
                "success": True,
                "claim_count": len(claims_list),
                "evidence_count": 1,
                "updated_claim": new_claim
            }

    def _tool_search_wiki(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        """Search wiki using RAG."""
        if not query:
            return {"results": [], "count": 0}

        try:
            # Use RAG to search
            result = self.query_engine.query_with_citations(
                query=query,
                k=min(max_results, 10)
            )

            # Format results
            results = []
            for evidence in result.get("evidence", [])[:max_results]:
                results.append({
                    "text": evidence.get("cited_text", "")[:300],
                    "url": evidence.get("url", ""),
                    "page_title": evidence.get("page_title", "")
                })

            return {
                "results": results,
                "count": len(results),
                "answer_summary": result.get("text", "")[:200]
            }

        except Exception as e:
            return {"error": str(e), "results": [], "count": 0}

    def _tool_add_affiliation(
        self,
        character_name: str,
        group: str,
        evidence_url: str,
        evidence_text: str,
        role: Optional[str] = None
    ) -> Dict[str, Any]:
        """Add a group/organization affiliation to a character."""
        if character_name not in self.knowledge_base["characters"]:
            return {
                "error": f"Character '{character_name}' not found. Create the character first with create_character().",
                "success": False
            }

        char_data = self.knowledge_base["characters"][character_name]
        affiliations = char_data.setdefault("affiliations", [])

        # Check if this group affiliation already exists (case-insensitive)
        existing = next(
            (a for a in affiliations if a["group"].lower() == group.lower()),
            None
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
                "message": f"Affiliation with '{group}' already exists" + (" (role updated)" if updated else ""),
                "character_name": character_name,
                "current_affiliations": [
                    {"group": a["group"], "role": a.get("role")}
                    for a in affiliations
                ],
                "affiliation_count": len(affiliations)
            }

        # Add new affiliation
        new_affiliation = {
            "group": group,
            "evidence_url": evidence_url,
            "evidence_text": evidence_text[:200]  # Truncate to 200 chars
        }
        if role:
            new_affiliation["role"] = role

        affiliations.append(new_affiliation)
        char_data["updated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        logger.info(f"Added affiliation: {character_name} -> {group} ({role or 'Member'})")

        return {
            "success": True,
            "character_name": character_name,
            "current_affiliations": [
                {"group": a["group"], "role": a.get("role")}
                for a in affiliations
            ],
            "affiliation_count": len(affiliations)
        }

    def _load_crawled_pages(self) -> List[Dict[str, Any]]:
        """Load all crawled pages from processed directory."""
        processed_dir = self.project_dir / "processed"

        if not processed_dir.exists():
            raise FileNotFoundError(f"No crawled pages found: {processed_dir}")

        pages = []
        for file_path in processed_dir.glob("*.json"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
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

        # Save individual character files
        for char_name, char_data in self.knowledge_base["characters"].items():
            safe_name = re.sub(r'[\\/:*?"<>|]', '_', char_name).replace(" ", "_")
            filepath = self.characters_dir / f"{safe_name}.json"
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(char_data, f, indent=2, ensure_ascii=False)

        # Save individual relationship files
        for (char_a, char_b), rel_data in self.knowledge_base["relationships"].items():
            safe_a = re.sub(r'[\\/:*?"<>|]', '_', char_a).replace(" ", "_")
            safe_b = re.sub(r'[\\/:*?"<>|]', '_', char_b).replace(" ", "_")
            filepath = self.relationships_dir / f"{safe_a}_{safe_b}.json"
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(rel_data, f, indent=2, ensure_ascii=False)

        # Save metadata
        metadata_file = self.project_dir / "knowledge_base_metadata.json"
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(self.knowledge_base["metadata"], f, indent=2, ensure_ascii=False)

        logger.info(f"Saved {len(self.knowledge_base['characters'])} characters and {len(self.knowledge_base['relationships'])} relationships")
