"""
ProfileBuilder - Build character profiles with relationship extraction.

This module builds comprehensive character profiles by extracting relationships
from wiki content using tool-enabled LLM queries. Claude autonomously gathers
information using available tools.

Key features:
- Tool-based information gathering (Claude decides what to search)
- Automatic citation tracking (evidence for all claims)
- Structured relationship profiles
- Cross-validation (verify bidirectional relationships)
"""
from typing import Dict, Any, List, Optional
from pathlib import Path
import json
import re
from datetime import datetime, timezone
import logging

from ..rag.query_engine import QueryEngine
from .tools import ToolRegistry
from src.utils.logging_config import get_logger

logger = get_logger("processor.profiles")


class ProfileBuilder:
    """
    Build comprehensive character profiles with relationship extraction.

    Uses tool-enabled LLM to autonomously gather relationship information.
    Claude can make multiple tool calls to search wiki, verify relationships,
    and gather context as needed.

    Args:
        project_name: Name of the wikia project
        min_evidence_count: Minimum citations to confirm relationship (default: 1)
        relationship_confidence_threshold: Min confidence for relationships (default: 0.6)

    Example:
        >>> builder = ProfileBuilder("avatar_wiki")
        >>> characters = CharacterExtractor.load_discovered_characters("avatar_wiki")
        >>>
        >>> # Build single profile
        >>> profile = builder.build_profile(characters["characters"][0])
        >>>
        >>> # Build all profiles
        >>> profiles = builder.build_all_profiles(characters["characters"], max_characters=10)
    """

    def __init__(
        self,
        project_name: str,
        min_evidence_count: int = 1,
        relationship_confidence_threshold: float = 0.6
    ) -> None:
        """
        Initialize ProfileBuilder for a specific project.

        Args:
            project_name: Name of the wikia project
            min_evidence_count: Minimum citations required per relationship
            relationship_confidence_threshold: Minimum confidence score for relationships
        """
        self.project_name = project_name
        self.min_evidence_count = min_evidence_count
        self.confidence_threshold = relationship_confidence_threshold

        # Initialize query engine for RAG queries
        self.query_engine = QueryEngine(project_name=project_name)

        # Initialize tool registry
        self.tools = ToolRegistry(self.query_engine)

        # Setup paths
        self.project_dir = Path("data") / "projects" / project_name
        self.characters_dir = self.project_dir / "characters"
        self.relationships_dir = self.project_dir / "relationships"

        print(f"[INFO] ProfileBuilder initialized with {len(self.tools.list_tools())} tools:")
        print(self.tools.get_tool_descriptions())

    def build_profile(
        self,
        character: Dict[str, Any],
        verbose: bool = True
    ) -> Dict[str, Any]:
        """
        Build detailed profile for a single character using tool-enabled LLM.

        Claude autonomously:
        1. Searches for character relationships
        2. Verifies relationship claims
        3. Gathers context about related characters
        4. Structures findings into profile

        Args:
            character: Character dict from CharacterExtractor
            verbose: Print progress messages (default: True)

        Returns:
            Enhanced character profile with relationships:
            {
                ...character fields...,
                "profile": {
                    "relationships": [
                        {
                            "target": "Character Name",
                            "type": "relationship_type",
                            "summary": "Brief description",
                            "claims": ["Claim 1", "Claim 2", ...],
                            "confidence": 0.85,
                            "evidence_count": 5
                        },
                        ...
                    ],
                    "total_relationships": N,
                    "tool_calls_made": M,
                    "profile_built_at": "2025-10-26T..."
                },
                "metadata": {
                    "tool_usage": [...],
                    "usage_stats": {...}
                }
            }
        """
        character_name = character["name"]
        character_url = character.get("source_url", "")
        disambiguation = character.get("disambiguation")

        if verbose:
            print(f"\n[INFO] Building profile for: {character['full_name']}")

        # Build system prompt (static instructions, sent once)
        system_prompt = self._build_system_prompt()

        # Build task prompt (character-specific, minimal)
        task_prompt = self._build_task_prompt(character)

        # Get tools in Anthropic format
        anthropic_tools = self.tools.to_anthropic_format()

        # Execute with tools
        if verbose:
            print(f"[INFO] Starting tool-enabled LLM query...")

        result = self.query_engine.llm_client.generate_with_tools(
            prompt=task_prompt,
            tools=anthropic_tools,
            tool_executor=self.tools.execute,
            max_iterations=20,  # Increased from 10 to allow more tool calls
            system_prompt=system_prompt,  # NEW: Pass system prompt
            temperature=0.3,
            prune_history=False  # IMPORTANT: Keep full context within character profile building
        )

        if verbose:
            print(f"[INFO] LLM completed after {result['usage']['iterations']} iterations")
            print(f"[INFO] Tool calls made: {len(result['tool_calls'])}")
            print(f"[INFO] Cost: ${result['usage']['estimated_cost_usd']:.4f}")

        # Parse final response into structured profile
        profile = self._parse_profile_result(character, result, verbose=verbose)

        return profile

    def _build_system_prompt(self) -> str:
        """
        Build system prompt with static instructions.

        System prompt contains all static content that doesn't change
        between characters:
        - Goal explanation
        - Tool usage guidelines
        - Output format specification
        - Examples (good and bad)
        - Critical rules

        This is sent once per character instead of being repeated
        in every tool iteration, significantly reducing token usage.

        Returns:
            System prompt string
        """
        return """You are an expert at analyzing fictional wikis to extract character relationships.

<goal>
Your goal: Discover and document ALL significant relationships a character has with OTHER CHARACTERS.

A "relationship" means any meaningful connection:
- Friends, allies, companions
- Romantic partners, love interests
- Family members (parents, siblings, children)
- Enemies, rivals, antagonists
- Mentors, students, teachers
- Professional relationships (teammates, commanders, etc.)
</goal>

<tool_usage_guidelines>
Use the available tools to gather comprehensive information:

1. START by using search_wiki to discover who this character has relationships with
   - Search broadly: "Who does [character] have relationships with?"
   - Search for specific types: "Who are [character]'s friends/enemies/family?"

2. FOR EACH relationship you find:
   - Use search_wiki to get details about the relationship
   - Use verify_relationship to measure evidence strength
   - Focus on relationships with confidence >=0.6 (moderate to strong evidence)
   - If you encounter an unfamiliar character, use get_character_context

3. GATHER specific claims for each relationship:
   - How they met
   - Nature of their relationship
   - Key events affecting the relationship
   - Current state of relationship

4. FILTER relationships:
   - Only include relationships with clear evidence (confidence >=0.6)
   - Prioritize important relationships (high evidence count)
   - Skip vague or speculative relationships

5. When you have gathered enough information, provide your final structured response
</tool_usage_guidelines>

<output_format>
When you're done researching, provide ONLY a JSON response with this EXACT structure:

{
  "relationships": [
    {
      "target": "Exact character name as it appears in wiki",
      "type": "relationship_type (e.g., friend, enemy, romantic_partner, mentor, family)",
      "summary": "One sentence summary of the relationship",
      "narrative": {
        "claims": [
          "Specific factual claim 1 about their relationship",
          "Specific factual claim 2",
          "Specific factual claim 3"
        ]
      },
      "confidence": 0.85,
      "evidence_count": 5,
      "verified_with": "Name of tool call used (e.g., verify_relationship)"
    }
  ]
}

Requirements:
- Use EXACT character names from wiki (not descriptions or titles)
- Each claim must be specific and factual
- Include confidence and evidence_count from verify_relationship tool
- Include "verified_with" field to reference which tool call verified this relationship
- Sort relationships by confidence (highest first)
- Only include relationships with confidence >=0.6

Note: Evidence citations will be automatically attached from your verify_relationship tool calls during post-processing.
</output_format>

<examples>
GOOD relationship entry:
{
  "target": "Katara",
  "type": "romantic_partner",
  "summary": "Aang's love interest who he eventually marries",
  "narrative": {
    "claims": [
      "Katara was the first person to believe in Aang as the Avatar",
      "They developed romantic feelings during their journey to defeat the Fire Lord",
      "Aang and Katara married after the war and had three children together"
    ]
  },
  "confidence": 0.95,
  "evidence_count": 12,
  "verified_with": "verify_relationship"
}

BAD relationship entry (DO NOT DO THIS):
{
  "target": "The Water Tribe warrior",  // WRONG: Use actual name "Sokka"
  "type": "friendship",  // Too generic
  "summary": "They are friends",  // Too vague
  "narrative": {
    "claims": [
      "They get along well"  // Not specific enough
    ]
  },
  "confidence": 0.3,  // Too low - should be filtered out
  "evidence_count": 1,
  "verified_with": "verify_relationship"
}
</examples>

<critical_rules>
1. Only include NAMED CHARACTERS (not titles, groups, or concepts)
2. Only include relationships with confidence >=0.6
3. Be specific in claims (avoid vague statements)
4. Use tools to verify uncertain relationships
5. Provide ONLY JSON in your final response (no extra commentary)
</critical_rules>"""

    def _build_task_prompt(self, character: Dict[str, Any]) -> str:
        """
        Build minimal task prompt with character-specific information.

        This contains ONLY character-specific details that change
        between characters. All static instructions are in the
        system prompt to reduce token usage.

        Args:
            character: Character dict

        Returns:
            Minimal task prompt string
        """
        character_name = character["name"]
        character_url = character.get("source_url", "")
        disambiguation = character.get("disambiguation")

        prompt = f"""Build a comprehensive relationship profile for: {character['full_name']}

<character_context>
Character: {character_name}
"""

        if disambiguation:
            prompt += f"""Disambiguation: {disambiguation}
IMPORTANT: We are analyzing {character['full_name']}, specifically the one who is {disambiguation}.
NOT other characters named "{character_name}".

When searching, use the character_url parameter to filter results to this specific character's page.
Character URL: {character_url}
"""

        prompt += """</character_context>

Begin your research using the available tools."""

        return prompt

    def _parse_profile_result(
        self,
        character: Dict[str, Any],
        llm_result: Dict[str, Any],
        verbose: bool = True
    ) -> Dict[str, Any]:
        """
        Parse LLM result into structured profile.

        Args:
            character: Original character dict
            llm_result: Result from generate_with_tools()
            verbose: Print parsing progress

        Returns:
            Enhanced character profile
        """
        # Extract final response
        final_response = llm_result["final_response"]

        # Parse JSON response
        try:
            # Claude may wrap JSON in markdown code blocks
            json_match = re.search(r'```json\s*(\{.*\})\s*```', final_response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to find JSON object directly
                json_match = re.search(r'\{.*\}', final_response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    raise ValueError("No JSON found in LLM response")

            profile_data = json.loads(json_str)

        except Exception as e:
            if verbose:
                logger.error(f"Failed to parse LLM response as JSON: {e}")
                logger.error(f"Response: {final_response[:500]}...")

            # Return empty profile on parse failure
            profile_data = {"relationships": []}

        # Filter relationships by confidence
        relationships = [
            rel for rel in profile_data.get("relationships", [])
            if rel.get("confidence", 0.0) >= self.confidence_threshold
        ]

        if verbose:
            print(f"[INFO] Parsed {len(relationships)} relationships (filtered by confidence >={self.confidence_threshold})")

        # Merge evidence from tool calls into relationships
        relationships = self._merge_evidence_from_tools(
            character_name=character.get("name", ""),
            relationships=relationships,
            tool_calls=llm_result["tool_calls"],
            verbose=verbose
        )

        # Build enhanced profile
        profile = {
            **character,  # Include all original character fields
            "profile": {
                "relationships": relationships,
                "total_relationships": len(relationships),
                "tool_calls_made": len(llm_result["tool_calls"]),
                "profile_built_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            },
            "metadata": {
                "tool_usage": llm_result["tool_calls"],
                "usage_stats": llm_result["usage"]
            }
        }

        return profile

    def _match_evidence_to_claim(
        self,
        claim_text: str,
        all_evidence: List[Dict[str, Any]],
        max_evidence: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Match relevant evidence to a specific claim using text similarity.

        Uses simple keyword matching to score evidence chunks and return
        the most relevant ones for this claim.

        Args:
            claim_text: The claim to find evidence for
            all_evidence: All available evidence chunks
            max_evidence: Maximum number of evidence chunks to return

        Returns:
            List of most relevant evidence chunks
        """
        if not all_evidence:
            return []

        # Extract significant words from claim (lowercase, filter common words)
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                      'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been',
                      'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
                      'could', 'should', 'may', 'might', 'their', 'they', 'them', 'this',
                      'that', 'these', 'those', 'his', 'her', 'him'}

        claim_words = set(word.lower() for word in claim_text.split()
                         if len(word) > 2 and word.lower() not in stop_words)

        # Score each evidence chunk
        scored_evidence = []
        for ev in all_evidence:
            cited_text = ev.get("cited_text", "").lower()

            # Count keyword matches
            matches = sum(1 for word in claim_words if word in cited_text)
            score = matches / len(claim_words) if claim_words else 0

            # Boost score if evidence is from a highly relevant source
            if score > 0:
                scored_evidence.append((score, ev))

        # Sort by score and return top N
        scored_evidence.sort(reverse=True, key=lambda x: x[0])
        return [ev for score, ev in scored_evidence[:max_evidence] if score > 0]

    def _merge_evidence_from_tools(
        self,
        character_name: str,
        relationships: List[Dict[str, Any]],
        tool_calls: List[Dict[str, Any]],
        verbose: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Merge evidence from verify_relationship tool calls into relationship narratives.

        This transforms:
            narrative.claims: ["claim 1", "claim 2"]
        Into:
            narrative.claims_with_evidence: [
                {"claim": "claim 1", "confidence": 0.9, "evidence": [...]},
                {"claim": "claim 2", "confidence": 0.8, "evidence": [...]}
            ]

        Args:
            character_name: Name of character being profiled
            relationships: List of relationship dicts from LLM
            tool_calls: Tool call history from LLM
            verbose: Print merge progress

        Returns:
            Enhanced relationships with evidence merged in
        """
        # Build mapping: target_name -> evidence
        evidence_map = {}
        for call in tool_calls:
            if call.get("tool") == "verify_relationship":
                params = call.get("input", {})  # Tool calls use "input" not "params"
                result = call.get("result", {})

                # Figure out which character is the target (not the source character)
                char_a = params.get("character_a", "")
                char_b = params.get("character_b", "")

                # The target is whichever one isn't the source character
                if char_a.lower() == character_name.lower():
                    target = char_b
                elif char_b.lower() == character_name.lower():
                    target = char_a
                else:
                    # Can't determine target, skip
                    continue

                # Store evidence for this relationship
                evidence_map[target.lower()] = result.get("evidence", [])

        # Merge evidence into relationships
        for rel in relationships:
            target = rel.get("target", "").lower()

            # Get narrative claims (may be nested or flat)
            narrative = rel.get("narrative", {})
            claims = narrative.get("claims", [])

            if not claims:
                continue

            # Get evidence for this relationship
            evidence = evidence_map.get(target, [])

            # Transform claims into claims_with_evidence
            # Match relevant evidence to each claim using text similarity
            claims_with_evidence = []
            for claim_text in claims:
                # Find evidence relevant to this specific claim
                relevant_evidence = self._match_evidence_to_claim(claim_text, evidence)

                claim_obj = {
                    "claim": claim_text,
                    "confidence": rel.get("confidence", 0.0),  # Use relationship confidence
                    "evidence": relevant_evidence  # Only relevant evidence for this claim
                }
                claims_with_evidence.append(claim_obj)

            # Update narrative structure
            rel["narrative"]["claims_with_evidence"] = claims_with_evidence
            # Keep original claims for backwards compatibility
            # rel["narrative"]["claims"] stays as-is

        if verbose and evidence_map:
            print(f"[INFO] Merged evidence from {len(evidence_map)} verify_relationship calls")

        return relationships

    def build_all_profiles(
        self,
        characters: List[Dict[str, Any]],
        max_characters: Optional[int] = None,
        save: bool = True
    ) -> Dict[str, Dict[str, Any]]:
        """
        Build profiles for all discovered characters.

        Implements optimizations:
        - Query caching: Caches repeated search queries across characters
        - Token usage reset: Clears stats between characters for accurate per-character tracking

        Args:
            characters: List of character dicts from CharacterExtractor
            max_characters: Optional limit (default: None = all)
            save: Auto-save profiles after building (default: True)

        Returns:
            Dict mapping character name -> enhanced profile
        """
        # Limit if specified
        if max_characters:
            characters = characters[:max_characters]
            print(f"[INFO] Limited to {max_characters} characters")

        profiles = {}
        total_cost = 0.0

        print(f"\n[INFO] Building profiles for {len(characters)} characters...")
        print(f"[INFO] Query caching enabled - repeated queries will be cached")

        for i, character in enumerate(characters, 1):
            char_name = character["name"]

            print(f"\n{'='*60}")
            print(f"[{i}/{len(characters)}] Building profile for: {char_name}")
            print(f"{'='*60}")

            # Reset LLM token usage stats for clean per-character tracking
            # Note: Conversation history is automatically isolated per build_profile call
            self.query_engine.llm_client.reset_usage_stats()

            try:
                profile = self.build_profile(character, verbose=True)
                profiles[char_name] = profile

                # Track cumulative cost
                cost = profile["metadata"]["usage_stats"]["estimated_cost_usd"]
                total_cost += cost

                print(f"[OK] Profile complete. Relationships: {profile['profile']['total_relationships']}")
                print(f"[OK] Total cost so far: ${total_cost:.4f}")

            except Exception as e:
                logger.error(f"Failed to build profile for {char_name}: {e}")
                continue

        # Print cache statistics
        self._print_cache_statistics()

        print(f"\n{'='*60}")
        print(f"[OK] Completed {len(profiles)}/{len(characters)} profiles")
        print(f"[OK] Total cost: ${total_cost:.4f}")
        print(f"{'='*60}\n")

        # Save if requested
        if save:
            self.save_profiles(profiles)

        return profiles

    def _print_cache_statistics(self) -> None:
        """
        Print query cache performance statistics.

        Shows cache hit rate and potential cost savings from caching.
        """
        # Get cache stats from WikiSearchTool
        wiki_search_tool = None
        for tool in self.tools._tools.values():
            if tool.name == "search_wiki":
                wiki_search_tool = tool
                break

        if wiki_search_tool and hasattr(wiki_search_tool, 'get_cache_stats'):
            stats = wiki_search_tool.get_cache_stats()

            print(f"\n{'='*60}")
            print("[INFO] Query Cache Statistics:")
            print(f"  - Cache size: {stats['cache_size']} unique queries")
            print(f"  - Cache hits: {stats['cache_hits']}")
            print(f"  - Cache misses: {stats['cache_misses']}")
            print(f"  - Hit rate: {stats['hit_rate']:.1%}")

            if stats['cache_hits'] > 0:
                print(f"\n[INFO] Cache saved ~{stats['cache_hits']} redundant RAG queries!")
            print(f"{'='*60}\n")

    def save_profiles(
        self,
        profiles: Dict[str, Dict[str, Any]]
    ) -> None:
        """
        Save enhanced character profiles and relationship graph.

        Saves:
        1. Individual character files (updated with profiles)
        2. Relationship graph file (nodes + edges)

        Args:
            profiles: Dict mapping character name -> profile
        """
        # Ensure directories exist
        self.characters_dir.mkdir(parents=True, exist_ok=True)
        self.relationships_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n[INFO] Saving {len(profiles)} profiles...")

        # Save individual character files
        for char_name, profile in profiles.items():
            # Generate safe filename (consistent with character_extractor)
            safe_name = profile.get("full_name", char_name)
            safe_name = re.sub(r'[\\/:*?"<>|]', '_', safe_name)  # Replace unsafe chars
            safe_name = safe_name.replace(" ", "_")
            filename = f"{safe_name}.json"
            filepath = self.characters_dir / filename

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(profile, f, indent=2, ensure_ascii=False)

        print(f"[OK] Saved character profiles to {self.characters_dir}")

        # Save detailed relationship files
        self._save_relationship_details(profiles)

        # Load ALL characters with profiles (not just newly built ones)
        all_profiles = self._load_all_profiles_with_relationships()
        print(f"[INFO] Building graph from {len(all_profiles)} total characters with profiles")

        # Build and save relationship graph from ALL profiles
        graph = self._build_relationship_graph(all_profiles)
        graph_path = self.relationships_dir / "graph.json"

        with open(graph_path, "w", encoding="utf-8") as f:
            json.dump(graph, f, indent=2, ensure_ascii=False)

        print(f"[OK] Saved relationship graph to {graph_path}")
        print(f"[OK] Graph contains {len(graph['nodes'])} nodes and {len(graph['edges'])} edges")

    def _load_all_profiles_with_relationships(self) -> Dict[str, Dict[str, Any]]:
        """
        Load all character files that have completed relationship profiles.

        Returns:
            Dict mapping character name -> complete profile data
        """
        all_profiles = {}

        # Iterate through all character JSON files
        for char_file in self.characters_dir.glob("*.json"):
            if char_file.name == "_discovered.json":
                continue  # Skip discovery metadata file

            try:
                with open(char_file, "r", encoding="utf-8") as f:
                    character = json.load(f)

                # Only include characters that have completed profiles with relationships
                if "profile" in character and "relationships" in character["profile"]:
                    char_name = character.get("name", char_file.stem)
                    all_profiles[char_name] = character

            except (json.JSONDecodeError, KeyError) as e:
                print(f"[WARNING] Skipping invalid character file {char_file.name}: {e}")
                continue

        return all_profiles

    def _save_relationship_details(
        self,
        profiles: Dict[str, Dict[str, Any]]
    ) -> None:
        """
        Save detailed relationship files.

        Creates individual JSON files for each relationship with full evidence,
        claims, and metadata. Files are saved as:
            relationships/{from}_{to}.json

        Args:
            profiles: Dict mapping character name -> profile
        """
        relationship_count = 0
        saved_pairs = set()  # Track to avoid duplicates

        for char_name, profile in profiles.items():
            relationships = profile["profile"]["relationships"]

            for rel in relationships:
                target = rel["target"]

                # Create canonical pair key (alphabetically sorted to avoid duplicates)
                pair = tuple(sorted([char_name, target]))
                if pair in saved_pairs:
                    continue  # Already saved this relationship

                # Generate safe filename
                from_safe = re.sub(r'[\\/:*?"<>|]', '_', char_name).replace(" ", "_")
                to_safe = re.sub(r'[\\/:*?"<>|]', '_', target).replace(" ", "_")
                filename = f"{from_safe}_{to_safe}.json"
                filepath = self.relationships_dir / filename

                # Build detailed relationship object
                relationship_detail = {
                    "from": char_name,
                    "to": target,
                    "type": rel.get("type", ""),
                    "summary": rel.get("summary", ""),
                    "narrative": rel.get("narrative", {}),
                    "confidence": rel.get("confidence", 0.0),
                    "evidence_count": rel.get("evidence_count", 0),
                    "total_evidence_count": rel.get("total_evidence_count", rel.get("evidence_count", 0)),
                    "overall_confidence": rel.get("overall_confidence", rel.get("confidence", 0.0)),
                    "built_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                }

                # Save relationship file
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(relationship_detail, f, indent=2, ensure_ascii=False)

                saved_pairs.add(pair)
                relationship_count += 1

        print(f"[OK] Saved {relationship_count} detailed relationship files to {self.relationships_dir}")

    def _build_relationship_graph(
        self,
        profiles: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Build relationship graph from character profiles.

        Creates a graph structure suitable for visualization:
        - Nodes: Characters
        - Edges: Relationships (directed)

        Args:
            profiles: Dict mapping character name -> profile

        Returns:
            Graph dictionary:
            {
                "nodes": [{"id": "Aang", "full_name": "Aang", ...}],
                "edges": [{"from": "Aang", "to": "Katara", "type": "romantic", ...}],
                "metadata": {...}
            }
        """
        nodes = []
        edges = []

        # Build nodes (characters)
        for char_name, profile in profiles.items():
            node = {
                "id": char_name,
                "full_name": profile.get("full_name", char_name),
                "disambiguation": profile.get("disambiguation"),
                "source_url": profile.get("source_url", ""),
                "total_relationships": profile["profile"]["total_relationships"]
            }
            nodes.append(node)

        # Build edges (relationships)
        for char_name, profile in profiles.items():
            relationships = profile["profile"]["relationships"]

            for rel in relationships:
                target = rel["target"]

                # Generate details file reference
                from_safe = re.sub(r'[\\/:*?"<>|]', '_', char_name).replace(" ", "_")
                to_safe = re.sub(r'[\\/:*?"<>|]', '_', target).replace(" ", "_")
                details_file = f"{from_safe}_{to_safe}.json"

                edge = {
                    "from": char_name,
                    "to": target,
                    "type": rel["type"],
                    "summary": rel["summary"],
                    "confidence": rel["confidence"],
                    "evidence_count": rel["evidence_count"],
                    "details_file": details_file  # Reference to detailed relationship file
                }
                edges.append(edge)

        # Build metadata
        metadata = {
            "project_name": self.project_name,
            "total_characters": len(nodes),
            "total_relationships": len(edges),
            "built_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        }

        return {
            "nodes": nodes,
            "edges": edges,
            "metadata": metadata
        }
