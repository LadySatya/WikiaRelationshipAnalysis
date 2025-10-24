"""
ProfileBuilder - Build character profiles with relationship extraction.

This module builds comprehensive character profiles by extracting relationships
from wiki content using RAG queries with automatic citation tracking. Each
relationship claim is backed by verifiable evidence.
"""
from typing import Dict, Any, List, Optional
from pathlib import Path
import json
import re
from datetime import datetime, timezone

from ..rag.query_engine import QueryEngine


class ProfileBuilder:
    """
    Build comprehensive character profiles with relationship extraction.

    Focuses on discovering and documenting character relationships using
    RAG queries with automatic citation tracking. Each claim about a
    relationship is backed by cited evidence from wiki pages.

    Args:
        project_name: Name of the wikia project
        min_evidence_count: Minimum citations to confirm relationship (default: 1)
        relationship_confidence_threshold: Min confidence for relationships (default: 0.6)

    Example:
        >>> builder = ProfileBuilder("avatar_wiki")
        >>> characters = load_discovered_characters()
        >>> profiles = builder.build_all_profiles(characters)
        >>> builder.save_profiles(profiles)
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

        # Setup paths
        self.project_dir = Path("data") / "projects" / project_name
        self.characters_dir = self.project_dir / "characters"
        self.relationships_dir = self.project_dir / "relationships"

    def _discover_relationships(
        self,
        character_name: str,
        character_url: str
    ) -> List[Dict[str, Any]]:
        """
        Discover all relationships for a character using RAG.

        Queries the wiki content to find all characters that have relationships
        with the given character.

        Args:
            character_name: Name of the character
            character_url: Source URL of the character's wiki page

        Returns:
            List of relationship candidates with basic info
        """
        # Build discovery query using Claude's best practices
        # - XML tags for structure
        # - Clear context about the task
        # - Specific examples with edge cases
        # - Explicit instructions about what to exclude
        query = f"""<task>
You are analyzing a wiki to identify character relationships.

Your goal: List ONLY the OTHER CHARACTERS (individual people with names) that {character_name} has a relationship with, based on the provided wiki content.
</task>

<critical_rules>
ONLY list NAMED INDIVIDUALS that appear in the wiki content.

DO NOT include:
- Titles or roles (e.g., "Phoenix King", "Tribal Princess")
- Groups or organizations (e.g., "Team Avatar", "The Fire Nation")
- Concepts or abstractions (e.g., "friendship", "rivalry")
- Relationship types (e.g., "mentor", "enemy")
- Generic descriptions (e.g., "his guardian", "the avatar")
- Meta-commentary (e.g., "Additional context", "Background", "Note")
- Your own commentary or explanations

If you cannot find any character relationships in the provided content, output: NONE
</critical_rules>

<format>
For each character found, output EXACTLY this format:
CHARACTER_NAME - brief_relationship_type

Where:
- CHARACTER_NAME is the character's actual name as it appears in the wiki
- brief_relationship_type is 1-3 words describing the relationship
- Each entry on a new line
- No additional commentary, explanations, or notes
</format>

<examples>
✓ CORRECT examples (character names from wiki content):
1. Katara - romantic partner
2. Prince Zuko - former enemy turned ally
3. Monk Gyatso - mentor and father figure
4. Fire Lord Ozai - enemy

✗ INCORRECT examples (DO NOT DO THIS):
1. The Avatar - enemy (title, not a character name)
2. Team Avatar - friends (group, not a character)
3. Mentorship - relationship type (concept, not a character)
4. His guardian - protector (description, not a name)
5. Additional context - background info (meta-commentary, not a character)
6. Note - he was found by Sokka (meta-commentary, not a character)
7. Background - raised by monks (meta-commentary, not a character)
</examples>

<instructions>
1. Read the provided wiki content carefully
2. Identify ONLY character names that are mentioned
3. For each character, determine their relationship to {character_name}
4. Output in the specified format
5. Do not add any notes, context, or explanations
6. If no characters found, output: NONE
</instructions>

Now, analyze the provided wiki content and list the characters:
"""

        # Query RAG with citations
        result = self.query_engine.query_with_citations(
            query=query,
            k=15,  # Get more chunks for comprehensive coverage
            metadata_filter={"url": character_url}  # Focus on character's page
        )

        # Parse response to extract relationship candidates
        relationships = self._parse_relationship_list(result["text"])

        return relationships

    def _parse_relationship_list(self, text: str) -> List[Dict[str, Any]]:
        """
        Parse relationship discovery response into structured list.

        Extracts character names and relationship types from the LLM response.

        Args:
            text: RAG response text

        Returns:
            List of relationship dictionaries
        """
        relationships = []

        # Split into lines and process each
        lines = text.strip().split("\n")

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Remove list markers (1., 2., -, *, etc.)
            line = re.sub(r"^[\d\.\-\*\)\]\s]+", "", line).strip()

            if not line:
                continue

            # Try to extract character name and relationship type
            # Formats: "Name - type, description" or "Name: type"
            match = re.match(r"^([^-:,]+)[\-:](.+)$", line)

            if match:
                char_name = match.group(1).strip()
                rest = match.group(2).strip()

                # Extract relationship type (first word/phrase before comma or period)
                type_match = re.match(r"^([^,\.]+)", rest)
                rel_type = type_match.group(1).strip() if type_match else rest

                relationships.append({
                    "target_character": char_name,
                    "relationship_type": rel_type,
                    "brief_description": rest
                })

        return relationships

    def _build_relationship_details(
        self,
        from_character: str,
        to_character: str,
        relationship_type: str
    ) -> Dict[str, Any]:
        """
        Build detailed relationship info with evidence citations.

        Queries the wiki for detailed information about the relationship
        between two characters, with automatic citation tracking.

        Args:
            from_character: Source character name
            to_character: Target character name
            relationship_type: Type of relationship

        Returns:
            Detailed relationship dictionary with claims and evidence
        """
        # Build detailed query - ask Claude to structure claims for us
        query = f"""<task>
You are extracting factual claims about the relationship between {from_character} and {to_character} from wiki content.

Your goal: Identify specific, factual statements about their relationship that are supported by the provided text.
</task>

<instructions>
1. Read through the provided wiki content carefully
2. Identify 4-8 specific factual claims about their relationship
3. Each claim should be:
   - A single, clear statement
   - Directly supported by the wiki content
   - Focused on their relationship (not individual character info)

Cover these aspects (if available):
- How they met
- Initial relationship dynamic
- How the relationship evolved
- Key events that affected the relationship
- Final/current state of relationship
</instructions>

<output_format>
List each claim as a numbered statement.
Use complete sentences.
Be specific and factual.

Example format:
1. [First factual claim about their relationship]
2. [Second factual claim]
3. [Third factual claim]
(etc.)

Do NOT add commentary or analysis - just the factual claims.
</output_format>

Extract the relationship claims:
"""

        # Query RAG with citations (more chunks for comprehensive coverage)
        result = self.query_engine.query_with_citations(
            query=query,
            k=20,  # Get many chunks for relationship context
            temperature=0.3
        )

        # Parse narrative into claims with evidence
        parsed = self._parse_narrative_into_claims(result)

        # Build final relationship structure
        relationship = {
            "from": from_character,
            "to": to_character,
            "type": relationship_type,
            "summary": self._generate_summary(parsed["narrative"]["text"]),
            "narrative": parsed["narrative"],
            "overall_confidence": parsed["overall_confidence"],
            "total_evidence_count": parsed["total_evidence_count"],
            "bidirectional": False  # Will be updated during bidirectional check
        }

        return relationship

    def _generate_summary(self, narrative_text: str) -> str:
        """
        Generate a brief summary from narrative text.

        Args:
            narrative_text: Full narrative text

        Returns:
            Brief summary (first sentence or ~100 chars)
        """
        # Get first sentence or first 100 characters
        sentences = re.split(r'[.!?]\s+', narrative_text)
        if sentences:
            return sentences[0].strip() + "."
        return narrative_text[:100].strip() + "..."

    def _parse_narrative_into_claims(
        self,
        rag_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Parse Claude's structured response to extract numbered claims.

        Since Claude's citation locations refer to INPUT documents (not output text),
        we cannot map evidence to specific claims by character position.
        Instead, we distribute all evidence across the claims.

        Args:
            rag_result: Result from query_with_citations with text and evidence

        Returns:
            Dictionary with structured narrative, claims, and evidence
        """
        text = rag_result["text"]
        all_evidence = rag_result["evidence"]

        # Extract numbered claims from Claude's output
        # Format: "1. Claim text\n2. Next claim\n3. Another claim"
        claims_with_evidence = []

        lines = text.strip().split("\n")
        current_claim = ""

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check if this is a numbered claim (starts with "1.", "2.", etc.)
            match = re.match(r"^(\d+)\.\s+(.+)$", line)

            if match:
                # Save previous claim if exists
                if current_claim:
                    claims_with_evidence.append({
                        "claim": current_claim.strip(),
                        "evidence": all_evidence,  # All evidence supports all claims
                        "confidence": self._calculate_claim_confidence(len(all_evidence))
                    })

                # Start new claim
                current_claim = match.group(2)
            else:
                # Continuation of current claim
                if current_claim:
                    current_claim += " " + line

        # Add final claim
        if current_claim:
            claims_with_evidence.append({
                "claim": current_claim.strip(),
                "evidence": all_evidence,
                "confidence": self._calculate_claim_confidence(len(all_evidence))
            })

        # Calculate overall confidence based on evidence count
        overall_confidence = self._calculate_overall_confidence(claims_with_evidence)

        return {
            "narrative": {
                "text": text,
                "claims_with_evidence": claims_with_evidence
            },
            "overall_confidence": overall_confidence,
            "total_evidence_count": len(all_evidence)
        }

    def _split_into_sentences(self, text: str) -> List[Dict[str, Any]]:
        """
        Split text into sentences with character positions.

        Args:
            text: Text to split

        Returns:
            List of sentence dictionaries with text, start, and end positions
        """
        sentences = []

        # Split on sentence boundaries
        pattern = r'([.!?]+)\s+'
        parts = re.split(pattern, text)

        position = 0
        current_sentence = ""

        for i, part in enumerate(parts):
            if re.match(r'^[.!?]+$', part):
                # This is punctuation, add to current sentence
                current_sentence += part
                # Create sentence entry
                if current_sentence.strip():
                    sentences.append({
                        "text": current_sentence.strip(),
                        "start": position,
                        "end": position + len(current_sentence)
                    })
                    position += len(current_sentence)
                    # Account for whitespace
                    if i + 1 < len(parts):
                        position += 1  # Space after punctuation
                    current_sentence = ""
            else:
                # This is text content
                current_sentence += part

        # Add final sentence if exists
        if current_sentence.strip():
            sentences.append({
                "text": current_sentence.strip(),
                "start": position,
                "end": position + len(current_sentence)
            })

        return sentences

    def _evidence_overlaps_range(
        self,
        evidence: Dict[str, Any],
        start: int,
        end: int
    ) -> bool:
        """
        Check if evidence location overlaps with a character range.

        Args:
            evidence: Evidence dict with location info
            start: Range start position
            end: Range end position

        Returns:
            True if evidence overlaps with range
        """
        if "location" not in evidence:
            return False

        location = evidence["location"]
        # Handle None location (no citation position data)
        if location is None:
            return False

        ev_start = location.get("start", 0)
        ev_end = location.get("end", 0)

        # Check for overlap
        return not (ev_end <= start or ev_start >= end)

    def _calculate_claim_confidence(self, evidence_count: int) -> float:
        """
        Calculate confidence score for a single claim based on evidence count.

        Args:
            evidence_count: Number of citations supporting the claim

        Returns:
            Confidence score between 0.0 and 1.0
        """
        # More evidence = higher confidence
        # Cap at 1.0 for 3+ pieces of evidence
        return min(1.0, evidence_count / 3.0)

    def _calculate_overall_confidence(
        self,
        claims_with_evidence: List[Dict[str, Any]]
    ) -> float:
        """
        Calculate overall confidence from individual claim confidences.

        Args:
            claims_with_evidence: List of claims with confidence scores

        Returns:
            Overall confidence score between 0.0 and 1.0
        """
        if not claims_with_evidence:
            return 0.0

        # Average confidence across all claims
        total = sum(claim["confidence"] for claim in claims_with_evidence)
        return total / len(claims_with_evidence)

    def build_profile(
        self,
        character: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Build detailed profile for a single character.

        Discovers relationships and builds detailed evidence-backed
        descriptions for each relationship.

        Args:
            character: Character dict from CharacterExtractor

        Returns:
            Enhanced character profile with relationships
        """
        character_name = character["name"]
        character_url = character["source_url"]

        # Step 1: Discover relationships
        relationship_candidates = self._discover_relationships(
            character_name,
            character_url
        )

        # Step 2: Build details for each relationship
        relationships = []

        for candidate in relationship_candidates:
            target_char = candidate["target_character"]
            rel_type = candidate["relationship_type"]

            # Build detailed relationship with citations
            details = self._build_relationship_details(
                from_character=character_name,
                to_character=target_char,
                relationship_type=rel_type
            )

            # Rename 'from' and 'to' to 'source' and 'target' for clarity
            relationship = {
                "target": details["to"],
                "type": details["type"],
                "summary": details["summary"],
                "narrative": details["narrative"],
                "overall_confidence": details["overall_confidence"],
                "total_evidence_count": details["total_evidence_count"],
                "bidirectional": details["bidirectional"]
            }

            relationships.append(relationship)

        # Build enhanced profile
        profile = {
            **character,  # Include all original character fields
            "profile": {
                "relationships": relationships,
                "total_relationships": len(relationships),
                "profile_built_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            }
        }

        return profile

    def build_all_profiles(
        self,
        characters: List[Dict[str, Any]],
        save: bool = True
    ) -> Dict[str, Dict[str, Any]]:
        """
        Build profiles for all discovered characters.

        Args:
            characters: List of character dicts from CharacterExtractor
            save: Auto-save profiles after building (default: True)

        Returns:
            Dict mapping character name -> enhanced profile
        """
        profiles = {}

        for character in characters:
            char_name = character["name"]
            print(f"Building profile for {char_name}...")

            profile = self.build_profile(character)
            profiles[char_name] = profile

        # Save if requested
        if save:
            self.save_profiles(profiles)

        return profiles

    def save_profiles(
        self,
        profiles: Dict[str, Dict[str, Any]]
    ) -> None:
        """
        Save enhanced character profiles and relationship graph.

        Saves:
        1. Individual character files (updated)
        2. Relationship graph file (new)

        Args:
            profiles: Dict mapping character name -> profile
        """
        # Ensure directories exist
        self.characters_dir.mkdir(parents=True, exist_ok=True)
        self.relationships_dir.mkdir(parents=True, exist_ok=True)

        # Save individual character files
        for char_name, profile in profiles.items():
            # Create safe filename (consistent with character_extractor)
            safe_name = profile.get("full_name", char_name)
            safe_name = safe_name.replace("/", "_").replace("\\", "_").replace(" ", "_")
            filename = f"{safe_name}.json"
            filepath = self.characters_dir / filename

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(profile, f, indent=2, ensure_ascii=False)

        # Build and save relationship graph
        graph = self._build_relationship_graph(profiles)
        graph_path = self.relationships_dir / "graph.json"

        with open(graph_path, "w", encoding="utf-8") as f:
            json.dump(graph, f, indent=2, ensure_ascii=False)

        print(f"Saved {len(profiles)} character profiles to {self.characters_dir}")
        print(f"Saved relationship graph to {graph_path}")

    def _build_relationship_graph(
        self,
        profiles: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Build relationship graph from character profiles.

        Args:
            profiles: Dict mapping character name -> profile

        Returns:
            Graph dictionary with nodes and edges
        """
        nodes = []
        edges = []

        # Build nodes (characters)
        for char_name, profile in profiles.items():
            node = {
                "id": char_name,
                "full_name": profile.get("full_name", char_name),
                "source_url": profile.get("source_url", ""),
                "total_relationships": profile["profile"]["total_relationships"]
            }
            nodes.append(node)

        # Build edges (relationships)
        for char_name, profile in profiles.items():
            relationships = profile["profile"]["relationships"]

            for rel in relationships:
                edge = {
                    "from": char_name,
                    "to": rel["target"],
                    "type": rel["type"],
                    "summary": rel["summary"],
                    "confidence": rel["overall_confidence"],
                    "evidence_count": rel["total_evidence_count"]
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
