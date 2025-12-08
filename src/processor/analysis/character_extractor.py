"""
CharacterExtractor - Discovers characters from wiki corpus using RAG queries.

This module uses a multi-query RAG approach to discover all characters mentioned
in the crawled wiki data, with intelligent deduplication, variation tracking,
and disambiguation of duplicate names.
"""

from typing import List, Dict, Any, Optional
from pathlib import Path
import json
import re
from datetime import datetime, timezone
import logging

from ..rag.query_engine import QueryEngine
from ..config import get_config
from src.utils.logging_config import get_logger, get_llm_logger
from src.utils.tool_schema_loader import load_tool_schemas, load_system_prompt

logger = get_logger("processor.discovery")
llm_logger = None  # Initialized in __init__ when we have project_name


class CharacterExtractor:
    """
    Discovers characters from wiki corpus using RAG queries.

    Uses multiple broad queries to discover character names,
    then validates and filters results for accuracy. Handles
    name variations and disambiguates duplicate names.

    Args:
        project_name: Name of the wikia project
        min_mentions: Minimum chunks mentioning character (default: from config)
        confidence_threshold: Minimum confidence score (default: from config)

    Example:
        >>> extractor = CharacterExtractor(project_name="avatar_wiki")
        >>> characters = extractor.discover_characters()
        >>> print(f"Found {len(characters)} characters")
        >>> extractor.save_discovered_characters(characters)
    """

    # === CLASSIFICATION CONSTANTS ===

    # Namespaces to exclude from character discovery
    # These are meta-pages that should never be classified as characters
    EXCLUDED_NAMESPACES = [
        "Transcript:",
        "Category:",
        "Template:",
        "User:",
        "File:",
        "Help:",
        "Talk:",
        "Special:",
        "MediaWiki:",
    ]


    def __init__(
        self,
        project_name: str,
        min_mentions: Optional[int] = None,
        confidence_threshold: Optional[float] = None
    ) -> None:
        """
        Initialize CharacterExtractor for a specific project.

        Args:
            project_name: Name of the wikia project
            min_mentions: Min chunks mentioning character (default: from config)
            confidence_threshold: Min confidence score (default: from config)

        Raises:
            ValueError: If project_name is empty
        """
        # Validate project name
        if not project_name or not project_name.strip():
            raise ValueError("project_name cannot be empty")

        self.project_name = project_name.strip()

        # Load config
        config = get_config()

        # Set thresholds (use provided values or defaults from config)
        self.min_mentions = min_mentions if min_mentions is not None else config.character_discovery_min_mentions
        self.confidence_threshold = confidence_threshold if confidence_threshold is not None else config.character_discovery_confidence_threshold

        # Initialize QueryEngine for RAG queries
        self.query_engine = QueryEngine(project_name=self.project_name)

        # Initialize LLM logger for detailed prompt tracking
        from pathlib import Path
        project_log_dir = Path("data/projects") / self.project_name / "logs"
        self.llm_logger = get_llm_logger(project_log_dir)

        # Load tool schemas and system prompt
        self.classification_tools = load_tool_schemas("character_classification")
        self.classification_system_prompt = load_system_prompt("character_classification_system")

        logger.info(f"Loaded {len(self.classification_tools)} classification tools: {[t['name'] for t in self.classification_tools]}")

    def _parse_character_name(self, title: str) -> Dict[str, Optional[str]]:
        """
        Parse character name and disambiguation from page title.

        Wiki pages often disambiguate characters with the same name using
        parenthetical notation: "Bumi (King of Omashu)" vs "Bumi (son of Aang)".

        This method extracts:
        - base_name: The character's primary name (e.g., "Bumi")
        - disambiguation: The disambiguating context (e.g., "King of Omashu")
        - full_name: The complete page title (e.g., "Bumi (King of Omashu)")

        Args:
            title: Page title to parse

        Returns:
            Dictionary with keys:
            - base_name: Primary character name
            - disambiguation: Disambiguation tag (None if not present)
            - full_name: Complete page title

        Examples:
            >>> _parse_character_name("Bumi (King of Omashu)")
            {"base_name": "Bumi", "disambiguation": "King of Omashu", "full_name": "Bumi (King of Omashu)"}

            >>> _parse_character_name("Aang")
            {"base_name": "Aang", "disambiguation": None, "full_name": "Aang"}

            >>> _parse_character_name("Amon | Avatar Wiki | Fandom")
            {"base_name": "Amon", "disambiguation": None, "full_name": "Amon"}
        """
        # Strip common wiki title suffixes (e.g., " | Avatar Wiki | Fandom")
        # Pattern: anything after " | " followed by "Wiki" or "Fandom"
        cleaned_title = re.sub(r'\s*\|\s*.*(Wiki|Fandom).*$', '', title)

        # Match pattern: "Name (Disambiguation)"
        # Use greedy match for first group to capture LAST set of parentheses
        # e.g., "Character (First) (Second)" → base="Character (First)", disambiguation="Second"
        match = re.match(r'^(.+)\s*\((.+?)\)$', cleaned_title)

        if match:
            return {
                "base_name": match.group(1).strip(),
                "disambiguation": match.group(2).strip(),
                "full_name": cleaned_title
            }

        # No disambiguation found
        return {
            "base_name": cleaned_title,
            "disambiguation": None,
            "full_name": cleaned_title
        }

    def _create_character_entry(
        self,
        page: Dict[str, Any],
        tier: str
    ) -> Dict[str, Any]:
        """
        Create standardized character entry with proper name handling.

        This method centralizes character entry creation to ensure consistent
        handling of disambiguation, name variations, and metadata across all
        discovery tiers.

        Args:
            page: Page dictionary from crawled data
            tier: Discovery tier ("metadata", "title_llm", "content_llm")

        Returns:
            Character dictionary with structure:
            {
                "name": "Bumi",                         # Base name for querying
                "full_name": "Bumi (King of Omashu)",   # Display name
                "disambiguation": "King of Omashu",      # Disambiguation tag (or None)
                "name_variations": ["Bumi"],             # Will expand during profile building
                "discovered_via": ["metadata"],          # Discovery tier(s)
                "source_url": "wiki/Bumi_(King)",        # Unique identifier
                "source_page": {...}                     # Full page data
            }
        """
        title = page.get("title", "Unknown")
        name_info = self._parse_character_name(title)

        return {
            "name": name_info["base_name"],
            "full_name": name_info["full_name"],
            "disambiguation": name_info["disambiguation"],
            "name_variations": [name_info["base_name"]],
            "discovered_via": [tier],
            "source_url": page.get("url", ""),
            "source_page": page
        }

    def discover_characters(
        self,
        max_characters: Optional[int] = None,
        enable_disambiguation: bool = True,
        save: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Discover all characters in the wiki corpus.

        Args:
            max_characters: Maximum characters to return (default: None = all)
            enable_disambiguation: Whether to split duplicate names (default: True)
            save: Whether to automatically save discovered characters to disk (default: False)

        Returns:
            List of character dictionaries with full variation tracking
        """
        logger.info("Starting character discovery...")

        # Step 1: Execute multiple discovery queries
        logger.info("Executing discovery queries...")
        raw_characters = self._execute_discovery_queries()
        logger.info(f"Found {len(raw_characters)} raw character mentions")

        # Step 2: Deduplicate and track variations
        logger.info("Deduplicating and tracking name variations...")
        merged_characters = self._deduplicate_characters(raw_characters)
        logger.info(f"Merged to {len(merged_characters)} unique characters")

        # Step 3: Validate each character (check mention count + disambiguation detection)
        logger.info("Validating characters and detecting duplicates...")
        validated_characters = self._validate_characters(merged_characters)
        logger.info(f"{len(validated_characters)} characters passed validation")

        # Step 4: Disambiguate characters with duplicate names
        if enable_disambiguation:
            duplicates = [c for c in validated_characters if c.get("requires_disambiguation", False)]
            if duplicates:
                logger.info(f"Disambiguating {len(duplicates)} characters with duplicate names...")
                validated_characters = self._disambiguate_characters(validated_characters)
                logger.info(f"After disambiguation: {len(validated_characters)} total characters")

        # Step 5: Filter by confidence threshold
        filtered_characters = [
            char for char in validated_characters
            if char["confidence"] >= self.confidence_threshold
        ]
        logger.info(f"{len(filtered_characters)} characters above confidence threshold")

        # Step 6: Sort by confidence (descending)
        sorted_characters = sorted(
            filtered_characters,
            key=lambda x: x["confidence"],
            reverse=True
        )

        # Step 7: Apply max limit if specified
        if max_characters:
            sorted_characters = sorted_characters[:max_characters]
            logger.info(f"Limited to top {max_characters} characters")

        # Step 8: Optionally save to disk
        if save:
            self.save_characters(sorted_characters)

        return sorted_characters

    def save_characters(
        self,
        characters: List[Dict[str, Any]],
        output_dir: Optional[Path] = None
    ) -> Path:
        """
        Save discovered characters to disk as JSON files.

        Each character is saved to a separate JSON file in the characters directory.
        Duplicate names are saved with disambiguated filenames (e.g., "Bumi_(King_of_Omashu).json").

        Args:
            characters: List of character dictionaries from discover_characters()
            output_dir: Optional custom output directory (default: data/projects/<project_name>/characters)

        Returns:
            Path to the characters directory where files were saved

        Example:
            >>> extractor = CharacterExtractor(project_name="avatar_wiki")
            >>> characters = extractor.discover_characters()
            >>> save_path = extractor.save_characters(characters)
            >>> print(f"Saved {len(characters)} characters to {save_path}")
        """
        # Determine output directory
        if output_dir is None:
            output_dir = Path("data/projects") / self.project_name / "characters"

        # Create directory if it doesn't exist
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save timestamp
        saved_at = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

        # Save each character to a separate file
        for char in characters:
            # Generate filename from full_name (handles disambiguation)
            filename = self._generate_filename(char["full_name"])

            # Add save metadata
            char_data = char.copy()
            char_data["saved_at"] = saved_at
            char_data["project_name"] = self.project_name

            # Remove source_page to avoid saving entire page content
            if "source_page" in char_data:
                del char_data["source_page"]

            # Write to file
            file_path = output_dir / f"{filename}.json"
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(char_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved {len(characters)} characters to {output_dir}")

        # Also save summary file for build command
        self.save_discovered_characters(characters, output_path=output_dir / "_discovered.json")

        return output_dir

    def _generate_filename(self, full_name: str) -> str:
        """
        Generate safe filename from character's full name.

        Replaces special characters with underscores, preserves disambiguation.

        Args:
            full_name: Character's full name (e.g., "Bumi (King of Omashu)")

        Returns:
            Safe filename without extension (e.g., "Bumi_(King_of_Omashu)")

        Examples:
            >>> extractor._generate_filename("Aang")
            "Aang"
            >>> extractor._generate_filename("Bumi (King of Omashu)")
            "Bumi_(King_of_Omashu)"
            >>> extractor._generate_filename("Avatar: Roku")
            "Avatar_Roku"
        """
        # Replace problematic characters with underscores
        # Keep parentheses for disambiguation, replace other special chars
        safe_name = full_name
        safe_name = safe_name.replace(":", "_")
        safe_name = safe_name.replace("/", "_")
        safe_name = safe_name.replace("\\", "_")
        safe_name = safe_name.replace("*", "_")
        safe_name = safe_name.replace("?", "_")
        safe_name = safe_name.replace("\"", "_")
        safe_name = safe_name.replace("<", "_")
        safe_name = safe_name.replace(">", "_")
        safe_name = safe_name.replace("|", "_")

        # Replace spaces with underscores (except inside parentheses for readability)
        # "Bumi (King of Omashu)" -> "Bumi_(King_of_Omashu)"
        safe_name = re.sub(r'\s+', '_', safe_name)

        # Remove any trailing/leading underscores
        safe_name = safe_name.strip("_")

        return safe_name

    def _load_crawled_pages(self) -> List[Dict[str, Any]]:
        """
        Load all crawled pages from the project's processed directory.

        Returns:
            List of page dictionaries with structure:
                {
                    "title": "Page Title",
                    "url": "https://...",
                    "namespace": "Main" or "Character",
                    "main_content": "...",
                    "infobox_data": {...},
                    "links": [...],
                    ...
                }

        Raises:
            FileNotFoundError: If processed directory doesn't exist
        """
        processed_dir = Path("data/projects") / self.project_name / "processed"

        if not processed_dir.exists():
            raise FileNotFoundError(
                f"No crawled pages found for project '{self.project_name}'. "
                f"Expected directory: {processed_dir}"
            )

        pages = []

        # Load all JSON files from processed directory
        for file_path in processed_dir.glob("*.json"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                    # Extract content from wrapper
                    page_content = data.get("content", {})

                    # Add URL from wrapper if not in content
                    if "url" not in page_content and "url" in data:
                        page_content["url"] = data["url"]

                    pages.append(page_content)

            except Exception as e:
                logger.warning(f"Failed to load page {file_path}: {e}")
                continue

        if not pages:
            raise ValueError(f"No pages found in {processed_dir}")

        logger.info(f"Loaded {len(pages)} crawled pages")
        return pages

    # === TOOL-BASED CLASSIFICATION METHODS ===

    def _execute_classification_tool(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        batch: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Execute a classification tool.

        Args:
            tool_name: Name of the tool to execute
            tool_input: Tool input parameters (must contain "page_title")
            batch: Full batch of pages for lookup

        Returns:
            Tool result dictionary

        Raises:
            ValueError: If tool_name is unknown or page_title not found
        """
        # Get page by title
        page_title = tool_input.get("page_title", "")
        page_data = None

        # Try exact match first
        for page in batch:
            if page.get("title", "") == page_title:
                page_data = page
                break

        # If not found, try case-insensitive match
        if not page_data:
            page_title_lower = page_title.lower()
            for page in batch:
                if page.get("title", "").lower() == page_title_lower:
                    page_data = page
                    break

        if not page_data:
            # Log available titles for debugging
            available_titles = [p.get("title", "Unknown") for p in batch]
            logger.debug(f"Page '{page_title}' not found in batch. Available: {available_titles[:3]}...")
            return {"error": f"Page not found: {page_title}"}

        if tool_name == "get_infobox_fields":
            # Return infobox field names
            infobox = page_data.get("infobox_data", {})
            return {
                "fields": list(infobox.keys()) if infobox else [],
                "field_count": len(infobox) if infobox else 0
            }

        elif tool_name == "get_page_excerpt":
            # Return first 500 characters of main content
            content = page_data.get("main_content", "")
            return {
                "excerpt": content[:500] if content else "No content available",
                "total_length": len(content)
            }

        else:
            raise ValueError(f"Unknown tool: {tool_name}")

    def _classify_pages_batch(
        self,
        pages: List[Dict[str, Any]],
        batch_size: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Classify pages using tool-enabled LLM in batches.

        This replaces the old two-tier classification (metadata + selective LLM)
        with a single LLM-first approach where the LLM can use tools to examine
        pages before classifying them.

        Args:
            pages: List of page dictionaries to classify
            batch_size: Number of pages to classify per LLM call

        Returns:
            List of character dictionaries (only pages classified as characters)
        """
        characters = []
        total_batches = (len(pages) + batch_size - 1) // batch_size

        logger.info(f"Classifying {len(pages)} pages in {total_batches} batches (size={batch_size})...")

        for batch_num in range(total_batches):
            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, len(pages))
            batch = pages[start_idx:end_idx]

            logger.info(f"Processing batch {batch_num + 1}/{total_batches} ({len(batch)} pages)...")

            # Build page list for LLM
            page_titles = [p.get("title", "Unknown") for p in batch]
            page_list_str = "\n".join([f"{i+1}. {title}" for i, title in enumerate(page_titles)])

            # Create task prompt
            task_prompt = f"""Classify the following {len(batch)} wiki pages as either CHARACTER or NOT_CHARACTER.

<pages>
{page_list_str}
</pages>

For each page, you can use the available tools to gather information:
- get_infobox_fields: See what metadata fields the page has
- get_page_excerpt: Read the opening content of the page

When you're done investigating, provide a JSON response with your classifications:

{{
  "classifications": [
    {{"page_number": 1, "title": "Page Title", "classification": "CHARACTER", "reasoning": "Brief reason"}},
    {{"page_number": 2, "title": "Page Title", "classification": "NOT_CHARACTER", "reasoning": "Brief reason"}},
    ...
  ]
}}

Use page_number to match the page in the list above (1-indexed).
"""

            # Execute with tools
            try:
                # Create closure to capture batch in tool executor
                def tool_executor(tool_name: str, **tool_input):
                    return self._execute_classification_tool(tool_name, tool_input, batch)

                result = self.query_engine.llm_client.generate_with_tools(
                    prompt=task_prompt,
                    tools=self.classification_tools,
                    tool_executor=tool_executor,
                    max_iterations=30,  # Allow multiple tool calls
                    system_prompt=self.classification_system_prompt,
                    temperature=0.0
                )

                # Parse JSON response
                final_response = result["final_response"]
                classifications = self._parse_classification_response(final_response, batch)

                # Log to LLM logger (convert usage format: total_input_tokens -> input_tokens)
                usage_stats = result.get("usage", {})
                self.llm_logger.log_prompt(
                    prompt=task_prompt,
                    model=self.query_engine.llm_client.model,
                    purpose=f"character_classification:batch_{batch_num+1}",
                    response=final_response,
                    usage={
                        "input_tokens": usage_stats.get("total_input_tokens", 0),
                        "output_tokens": usage_stats.get("total_output_tokens", 0)
                    },
                    metadata={
                        "batch_number": batch_num + 1,
                        "batch_size": len(batch),
                        "tool_calls_made": len(result.get("tool_calls", [])),
                        "characters_found": sum(1 for c in classifications if c["is_character"]),
                        "system_prompt": self.classification_system_prompt
                    }
                )

                # Add character entries
                for classification in classifications:
                    if classification["is_character"]:
                        page_idx = classification["page_index"]
                        characters.append(self._create_character_entry(batch[page_idx], tier="llm_tools"))

                logger.info(f"Batch {batch_num + 1}: Found {sum(1 for c in classifications if c['is_character'])} characters")

            except Exception as e:
                logger.error(f"Batch {batch_num + 1} classification failed: {e}")
                continue

        logger.info(f"Total discovered: {len(characters)} characters")
        return characters

    def _parse_classification_response(
        self,
        response: str,
        batch: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Parse LLM classification response into structured format.

        Args:
            response: LLM response text (should contain JSON)
            batch: Original batch of pages

        Returns:
            List of classification results:
            [
                {"page_index": 0, "is_character": True, "reasoning": "..."},
                {"page_index": 1, "is_character": False, "reasoning": "..."},
                ...
            ]
        """
        try:
            # Extract JSON from response (may be wrapped in markdown code blocks)
            json_match = re.search(r'```json\s*(\{.*\})\s*```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to find JSON object directly
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    raise ValueError("No JSON found in LLM response")

            data = json.loads(json_str)
            classifications_raw = data.get("classifications", [])

            # Convert to normalized format
            classifications = []
            for item in classifications_raw:
                page_num = item.get("page_number", 0)
                page_idx = page_num - 1  # Convert to 0-indexed

                # Validate page_idx
                if page_idx < 0 or page_idx >= len(batch):
                    logger.warning(f"Invalid page_number {page_num} in classification response")
                    continue

                classification = item.get("classification", "NOT_CHARACTER").upper()
                is_character = classification == "CHARACTER"

                classifications.append({
                    "page_index": page_idx,
                    "is_character": is_character,
                    "reasoning": item.get("reasoning", "")
                })

            return classifications

        except Exception as e:
            logger.error(f"Failed to parse classification response: {e}")
            logger.error(f"Response: {response[:500]}...")
            # Return empty list on parse failure
            return []

    # === CLASSIFICATION HELPER METHODS ===

    def _is_excluded_namespace(self, title: str) -> bool:
        """Check if page is in an excluded namespace (Transcript:, Category:, etc.)."""
        return any(title.startswith(ns) for ns in self.EXCLUDED_NAMESPACES)

    def _execute_discovery_queries(self) -> List[Dict[str, Any]]:
        """
        Execute page-based character discovery using tool-enabled LLM classification.

        The LLM uses tools to examine pages before classifying them, allowing it to
        inspect infobox fields and page content as needed for accurate classification.

        Returns:
            List of character dictionaries with name and discovered_via tracking
        """
        # Load all crawled pages
        pages = self._load_crawled_pages()

        # Filter out obvious non-character pages (namespace exclusions only)
        filtered_pages = []
        excluded_count = 0
        for page in pages:
            title = page.get("title", "")
            # Only exclude obvious metadata pages (Transcript:, Category:, etc.)
            if self._is_excluded_namespace(title):
                excluded_count += 1
                continue
            filtered_pages.append(page)

        logger.info(f"Excluded {excluded_count} metadata namespace pages, {len(filtered_pages)} remaining for classification")

        # Classify all pages using LLM with tools in batches
        characters = self._classify_pages_batch(filtered_pages, batch_size=10)

        logger.info(f"Total discovered: {len(characters)} characters")
        return characters

    def _deduplicate_characters(
        self,
        characters: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Prepare characters for validation - add standard fields and detect duplicates.

        Since LLM already grouped name variations during discovery, this method
        just adds standard fields and detects duplicate names (different characters
        with the same name).

        Args:
            characters: Character list from discovery (already has name_variations)

        Returns:
            Character list with standard fields and duplicate detection
        """
        # Add standard fields to each character
        for char in characters:
            # Ensure name_variations exists (should already be there from parsing)
            if "name_variations" not in char:
                char["name_variations"] = [char["name"]]

            # Add standard tracking fields
            char["canonical_name"] = char["name"]  # Will be updated after disambiguation

            # Preserve full_name if already set (from page title parsing)
            if "full_name" not in char:
                char["full_name"] = char["name"]

            # Preserve disambiguation if already set (from page title parsing)
            # Don't overwrite with None
            if "disambiguation" not in char:
                char["disambiguation"] = None

            char["requires_disambiguation"] = False
            char["duplicate_names"] = []

        # Detect duplicate names (different characters with same name)
        return self._detect_duplicate_names(characters)

    def _detect_duplicate_names(
        self,
        characters: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Detect and flag characters that share the same canonical name.

        Example: "Bumi" (King Bumi) and "Bumi" (Commander Bumi) are different
        characters with the same name. Both will be flagged with:
        - requires_disambiguation: True
        - duplicate_names: ["Bumi", "Bumi"]

        Args:
            characters: Character list with name field

        Returns:
            Character list with duplicate flags set
        """
        # Count occurrences of each name
        name_counts = {}
        for char in characters:
            name = char["name"]
            name_counts[name] = name_counts.get(name, 0) + 1

        # Flag duplicates
        for char in characters:
            if name_counts[char["name"]] > 1:
                char["requires_disambiguation"] = True
                # Find all other characters with same name
                char["duplicate_names"] = [
                    c["name"] for c in characters
                    if c["name"] == char["name"]
                ]

        return characters

    def _validate_characters(
        self,
        characters: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Validate characters by counting mentions filtered by source URL.

        For characters with the same base name (e.g., two "Bumi" characters),
        this method filters chunks by source_url to ensure we only count mentions
        from the character's own page, preventing false merging of distinct characters.

        For each character:
        1. Query vector store using base name + disambiguation context
        2. Filter chunks to only those from the character's source page
        3. Count high-confidence mentions from filtered chunks
        4. Extract context sample

        Args:
            characters: Deduplicated character list

        Returns:
            Validated list with mentions and confidence scores
        """
        validated = []

        for char in characters:
            name = char["name"]
            disambiguation = char.get("disambiguation")
            source_url = char.get("source_url", "")

            # Build query with disambiguation context if available
            if disambiguation:
                query = f"{name} {disambiguation}"
            else:
                query = f"Information about {name}"

            # Query vector store for this character
            chunks = self.query_engine.retriever.retrieve(
                query=query,
                k=50  # Get more chunks for better analysis
            )

            # Filter chunks by source URL to distinguish characters with same name
            # This ensures "Bumi (King)" and "Bumi (son of Aang)" are counted separately
            url_filtered_chunks = []
            if source_url:
                # Extract page identifier from URL (e.g., "Bumi_(King)" from full URL)
                url_identifier = source_url.split("/wiki/")[-1] if "/wiki/" in source_url else source_url

                url_filtered_chunks = [
                    chunk for chunk in chunks
                    if url_identifier in chunk.get("metadata", {}).get("source_url", "")
                ]

            # Fall back to all chunks if URL filtering produces no results
            # (e.g., if metadata doesn't include source_url)
            chunks_to_count = url_filtered_chunks if url_filtered_chunks else chunks

            # Count high-relevance mentions (distance < 1.0)
            # Note: Embedding similarity is imperfect, typical relevant chunks have distance 0.8-1.0
            relevant_chunks = [
                chunk for chunk in chunks_to_count
                if chunk["distance"] < 1.0
            ]

            char["mentions"] = len(relevant_chunks)

            # Skip characters below minimum mentions
            if char["mentions"] < self.min_mentions:
                continue

            # Calculate confidence score (normalized: mentions/10, capped at 1.0)
            char["confidence"] = min(char["mentions"] / 10.0, 1.0)

            # Extract context sample (first relevant chunk)
            if relevant_chunks:
                char["context_sample"] = relevant_chunks[0]["text"][:200] + "..."
            else:
                char["context_sample"] = "No context available"

            validated.append(char)

        return validated

    def _disambiguate_characters(
        self,
        characters: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Split characters that share names into separate entries.

        Note: Full disambiguation implementation pending. This is a placeholder
        that maintains current behavior.

        Args:
            characters: Validated character list

        Returns:
            List with duplicates split into separate entries (future)
        """
        # TODO: Implement full disambiguation logic
        # For now, just return characters as-is
        return characters

    def save_discovered_characters(
        self,
        characters: List[Dict[str, Any]],
        output_path: Optional[Path] = None
    ) -> Path:
        """
        Save discovered characters to JSON file.

        Args:
            characters: List of discovered characters
            output_path: Optional custom output path

        Returns:
            Path where file was saved
        """
        if output_path is None:
            # Default path: data/projects/<project>/characters/_discovered.json
            output_path = Path("data/projects") / self.project_name / "characters" / "_discovered.json"

        # Ensure directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Build output structure
        output = {
            "discovered_at": datetime.now().isoformat(),
            "project_name": self.project_name,
            "total_characters": len(characters),
            "disambiguation_performed": False,  # TODO: Update when implemented
            "characters": characters,
            "usage_stats": self.query_engine.get_usage_stats()
        }

        # Save to JSON
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved {len(characters)} characters to {output_path}")
        return output_path

    @staticmethod
    def load_discovered_characters(project_name: str) -> Dict[str, Any]:
        """
        Load previously discovered characters from file.

        Args:
            project_name: Name of the wikia project

        Returns:
            Dictionary with discovered characters and metadata

        Raises:
            FileNotFoundError: If discovery file doesn't exist
        """
        path = Path("data/projects") / project_name / "characters" / "_discovered.json"

        if not path.exists():
            raise FileNotFoundError(f"No discovered characters found for project '{project_name}'")

        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
