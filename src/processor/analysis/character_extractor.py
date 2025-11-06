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

from ..rag.query_engine import QueryEngine
from ..config import get_config


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

    # System prompt for batch page classification
    CLASSIFICATION_SYSTEM_PROMPT = """You are analyzing wiki page titles to identify which pages are about CHARACTERS.

A character is a person, being, or entity with a personality and agency in the story.

Include:
- People (heroes, villains, supporting characters)
- Anthropomorphic beings with personalities
- Sentient creatures that act as characters

Exclude:
- Locations (Republic City, Ba Sing Se)
- Organizations/Groups (Team Avatar, White Lotus)
- Concepts (Avatar State, Chakra)
- Episodes (The Promise, Sozin's Comet)
- Objects (Appa's saddle, Lion Turtle)
- List/disambiguation pages

Be conservative: if unsure, classify as "no".
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

    # Disambiguation text patterns indicating non-character pages
    DISAMBIGUATION_PATTERNS = [
        "this article is about the episode",
        "this article is about the chapter",
        "this article is about the title",
        "this article is about the political position",
        "for the character, see",
        "for the titular character, see",
    ]

    # Infobox fields that indicate episode/chapter/issue pages (NOT characters)
    EPISODE_INFOBOX_FIELDS = [
        "episode", "series", "book", "season", "chapter", "issue", "volume",
        "original air date", "airdate", "air date", "published", "publication date",
        "written by", "directed by", "animation", "studio", "release date",
        "previous", "next", "production number",
    ]

    # URL patterns that indicate character pages
    CHARACTER_URL_PATTERNS = [
        "/characters/",
        "/character:",
    ]

    # Infobox fields that indicate character pages
    CHARACTER_INFOBOX_FIELDS = [
        "species", "affiliation", "age", "gender", "abilities",
        "weapon", "fighting_style", "love_interest", "family",
        "nationality", "ethnicity", "profession", "status",
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
        print("[INFO] Starting character discovery...")

        # Step 1: Execute multiple discovery queries
        print("[INFO] Executing discovery queries...")
        raw_characters = self._execute_discovery_queries()
        print(f"[INFO] Found {len(raw_characters)} raw character mentions")

        # Step 2: Deduplicate and track variations
        print("[INFO] Deduplicating and tracking name variations...")
        merged_characters = self._deduplicate_characters(raw_characters)
        print(f"[INFO] Merged to {len(merged_characters)} unique characters")

        # Step 3: Validate each character (check mention count + disambiguation detection)
        print("[INFO] Validating characters and detecting duplicates...")
        validated_characters = self._validate_characters(merged_characters)
        print(f"[INFO] {len(validated_characters)} characters passed validation")

        # Step 4: Disambiguate characters with duplicate names
        if enable_disambiguation:
            duplicates = [c for c in validated_characters if c.get("requires_disambiguation", False)]
            if duplicates:
                print(f"[INFO] Disambiguating {len(duplicates)} characters with duplicate names...")
                validated_characters = self._disambiguate_characters(validated_characters)
                print(f"[INFO] After disambiguation: {len(validated_characters)} total characters")

        # Step 5: Filter by confidence threshold
        filtered_characters = [
            char for char in validated_characters
            if char["confidence"] >= self.confidence_threshold
        ]
        print(f"[INFO] {len(filtered_characters)} characters above confidence threshold")

        # Step 6: Sort by confidence (descending)
        sorted_characters = sorted(
            filtered_characters,
            key=lambda x: x["confidence"],
            reverse=True
        )

        # Step 7: Apply max limit if specified
        if max_characters:
            sorted_characters = sorted_characters[:max_characters]
            print(f"[INFO] Limited to top {max_characters} characters")

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

        print(f"[OK] Saved {len(characters)} characters to {output_dir}")

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
                print(f"[WARN] Failed to load page {file_path}: {e}")
                continue

        if not pages:
            raise ValueError(f"No pages found in {processed_dir}")

        print(f"[INFO] Loaded {len(pages)} crawled pages")
        return pages

    # === CLASSIFICATION HELPER METHODS ===

    def _is_excluded_namespace(self, title: str) -> bool:
        """Check if page is in an excluded namespace (Transcript:, Category:, etc.)."""
        return any(title.startswith(ns) for ns in self.EXCLUDED_NAMESPACES)

    def _has_disambiguation_text(self, content: str) -> bool:
        """
        Check if page has disambiguation text indicating it's NOT a character page.

        Examples:
            "This article is about the episode."
            "For the character, see Roku"
        """
        if not content:
            return False

        # Check first 500 characters where disambiguation text usually appears
        first_500 = content[:500].lower()
        return any(pattern in first_500 for pattern in self.DISAMBIGUATION_PATTERNS)

    def _looks_like_episode_page(self, infobox: Dict[str, Any]) -> bool:
        """
        Check if infobox has episode/chapter/issue fields.

        Returns True if page has 2+ episode-specific fields like:
        - "Episode", "Series", "Book"
        - "Original air date", "Written by", "Directed by"
        """
        if not infobox:
            return False

        # Normalize infobox keys to lowercase for comparison
        infobox_lower = {k.lower(): v for k, v in infobox.items()}

        # Count how many episode fields are present
        episode_matches = sum(
            1 for field in self.EPISODE_INFOBOX_FIELDS
            if field in infobox_lower
        )

        # If 2+ episode fields present, likely an episode/chapter page
        return episode_matches >= 2

    def _has_character_namespace(self, page: Dict[str, Any]) -> bool:
        """Check if page is in a character namespace."""
        namespace = page.get("namespace") or ""
        return "character" in namespace.lower()

    def _has_character_url(self, url: str) -> bool:
        """Check if URL indicates a character page (/characters/, /character:)."""
        url_lower = url.lower()
        return any(pattern in url_lower for pattern in self.CHARACTER_URL_PATTERNS)

    def _has_character_infobox(self, infobox: Dict[str, Any]) -> bool:
        """
        Check if infobox has character-specific fields.

        Returns True if page has 2+ character fields like:
        - "species", "age", "gender"
        - "affiliation", "abilities", "weapon"
        """
        if not infobox:
            return False

        # Normalize infobox keys to lowercase
        infobox_lower = {k.lower(): v for k, v in infobox.items()}

        # Count how many character fields are present
        character_matches = sum(
            1 for field in self.CHARACTER_INFOBOX_FIELDS
            if field in infobox_lower
        )

        # If 2+ character fields present, likely a character page
        return character_matches >= 2

    def _classify_by_metadata(self, page: Dict[str, Any]) -> Optional[str]:
        """
        Classify page using metadata only (Tier 1 - FREE, no LLM calls).

        Returns:
            "character" - definitely a character page
            "not_character" - definitely NOT a character (episode, transcript, etc.)
            None - ambiguous, needs LLM classification
        """
        # Extract page data once
        title = page.get("title", "")
        content = page.get("main_content", "")
        url = page.get("url", "")
        infobox = page.get("infobox_data", {})

        # === EXCLUSION CHECKS (if any match, NOT a character) ===

        if self._is_excluded_namespace(title):
            return "not_character"

        if self._has_disambiguation_text(content):
            return "not_character"

        if self._looks_like_episode_page(infobox):
            return "not_character"

        # === INCLUSION CHECKS (if any match, IS a character) ===

        if self._has_character_namespace(page):
            return "character"

        if self._has_character_url(url):
            return "character"

        if self._has_character_infobox(infobox):
            return "character"

        # === AMBIGUOUS (let LLM decide) ===

        return None

    def _classify_by_content(
        self,
        page: Dict[str, Any],
        use_rag: bool = True
    ) -> bool:
        """
        Classify page using content analysis (Tier 2 - SELECTIVE).

        Uses first paragraph + optional RAG query for context.

        Args:
            page: Page dictionary with content
            use_rag: Whether to use RAG for additional context (default: True)

        Returns:
            True if character page, False otherwise
        """
        title = page.get("title", "Unknown")
        content = page.get("main_content", "")

        # Get first 300 characters as snippet
        snippet = content[:300] if content else "No content available"

        # Optional: Use RAG to get additional context
        rag_context = ""
        if use_rag:
            try:
                rag_context = self.query_engine.query(
                    f"What is {title}? Describe it briefly.",
                    k=3,  # Just a few chunks for context
                    system_prompt="Provide a brief 1-2 sentence description."
                )
            except Exception as e:
                print(f"[WARN] RAG query failed for '{title}': {e}")
                rag_context = ""

        # Build classification prompt
        prompt = f"""Is this wiki page about a CHARACTER (a person/being with personality)?

Page title: {title}
First paragraph: {snippet}
"""

        if rag_context:
            prompt += f"\nAdditional context: {rag_context}"

        prompt += "\n\nAnswer with ONLY 'yes' or 'no'."

        try:
            response = self.query_engine.llm_client.generate(
                prompt=prompt,
                system_prompt=self.CLASSIFICATION_SYSTEM_PROMPT,
                temperature=0.0,
                max_tokens=10
            )

            return "yes" in response.lower()

        except Exception as e:
            print(f"[ERROR] Content classification failed for '{title}': {e}")
            return False

    def _execute_discovery_queries(self) -> List[Dict[str, Any]]:
        """
        Execute page-based character discovery using two-tier classification.

        Tier 1 (FREE): Metadata filtering (namespace, URL, infobox, disambiguation, episode detection)
        Tier 2 (SELECTIVE): Content-based LLM classification for ambiguous pages

        Returns:
            List of character dictionaries with name and discovered_via tracking
        """
        # Load all crawled pages
        pages = self._load_crawled_pages()

        # Tier 1: Metadata classification
        characters = []
        ambiguous_pages = []

        print("[INFO] Tier 1: Classifying by metadata...")
        filtered_count = 0
        for page in pages:
            classification = self._classify_by_metadata(page)

            if classification == "character":
                characters.append(self._create_character_entry(page, tier="metadata"))
            elif classification == "not_character":
                # Explicitly filtered out (transcripts, episodes, categories, etc.)
                filtered_count += 1
            else:
                # Ambiguous - needs LLM classification
                ambiguous_pages.append(page)

        print(f"[INFO] Tier 1 classified {len(characters)} characters, {filtered_count} filtered, {len(ambiguous_pages)} ambiguous")

        # Tier 2: Content-based classification for ambiguous pages
        # Only run if we have ambiguous pages and it's worth the cost
        if ambiguous_pages and (len(characters) < 50 or len(ambiguous_pages) < 100):
            print(f"[INFO] Tier 2: Content-classifying {len(ambiguous_pages)} remaining pages...")

            for page in ambiguous_pages:
                is_character = self._classify_by_content(page, use_rag=False)  # RAG is expensive, disable by default

                if is_character:
                    characters.append(self._create_character_entry(page, tier="content_llm"))

            tier2_count = sum(1 for c in characters if "content_llm" in c["discovered_via"])
            print(f"[INFO] Tier 2 classified {tier2_count} more characters")

        print(f"[INFO] Total discovered: {len(characters)} characters")
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

        print(f"[INFO] Saved {len(characters)} characters to {output_path}")
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
