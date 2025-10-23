# Character Name Normalization Plan

## TL;DR - Recommended Solution

**Problem**: Hardcoded `COMMON_TITLES` list is too Avatar-specific, doesn't generalize to other wikis.

**Solution**: Enhance the existing discovery query to handle BOTH discovery AND variation grouping in a single LLM call.

**Key Changes**:
1. Update prompt to instruct LLM: "Group same character's variations with `|`, list different characters separately"
2. Modify `_parse_character_names()` to split by `|` and track variations
3. Simplify `_deduplicate_characters()` - LLM already did the work
4. Add `_detect_duplicate_names()` to flag characters that share names (the "two Bumis" problem)

**Cost**: Same as current optimized implementation ($0.009 per discovery) - NO increase!

**Benefits**: Works for ANY fictional universe without hardcoded rules.

---

## Problem Statement

**Current Approach - Hardcoded Title List:**
```python
COMMON_TITLES = [
    "Avatar", "Fire Lord", "Chief", "Master", "Commander",
    "General", "King", "Queen", "Prince", "Princess",
    "Lord", "Lady", "Captain", "Lieutenant", "President"
]
```

**Issues:**
1. **Wiki-specific**: Titles like "Avatar" and "Fire Lord" are unique to Avatar universe
2. **Incomplete**: Can't anticipate all titles across different fictional universes
3. **Brittle**: Fails for titles we didn't hardcode (e.g., "Hokage", "Wizard", "Ser", "Dr.")
4. **Maintenance burden**: Must update list for each new wiki domain
5. **False positives**: Common words like "Master" might incorrectly strip valid names
6. **Not generalizable**: Defeats the purpose of a reusable wiki analysis tool

**Examples of Failure:**
- Naruto wiki: "Hokage Naruto", "Sensei Kakashi", "Lord Third"
- Harry Potter: "Professor Dumbledore", "Madam Pomfrey", "Sir Cadogan"
- Game of Thrones: "Ser Jaime Lannister", "Maester Luwin", "Khal Drogo"
- Star Wars: "Darth Vader", "General Grievous", "Emperor Palpatine"

---

## Goal

**Move name normalization from hardcoded rules to LLM-based intelligence**, allowing the system to:
1. Automatically detect title variations across ANY fictional universe
2. Group name variations without domain knowledge
3. Preserve canonical forms intelligently
4. Handle edge cases (nicknames, aliases, partial names)

---

## Proposed Solutions

### Option 5: Combined Discovery + Normalization in Single Query (RECOMMENDED)

**Approach**: Instruct the discovery query to handle both character discovery AND variation grouping in one pass.

**Key Insight**: Instead of discovering raw names and then deduplicating, ask the LLM to group variations during discovery.

**Modified Discovery Query:**
```python
def _get_discovery_query(self) -> str:
    return """List ALL characters mentioned in this wiki, including:
- Main protagonists and antagonists
- Supporting characters and side characters
- Characters in major storylines
- Characters with significant relationships
- Characters mentioned in affiliations, factions, or groups
- Minor characters that appear in the content

IMPORTANT - Name Variations vs Different Characters:
- If you see the SAME character with different titles/names, group them with " | "
- If you see DIFFERENT characters who share a name, list them SEPARATELY
- When grouping, put the most common/canonical name FIRST
- Be CONSERVATIVE - only group if you're CERTAIN they're the same character

Examples:
✓ SAME character, different titles: "Zuko | Fire Lord Zuko" (same person)
✓ DIFFERENT characters, same name: "Bumi" and "Bumi" on separate lines (King Bumi vs Commander Bumi)
✓ Single variation only: "Mako" (no other variations seen)
✓ Nickname variation: "Aang | Twinkle Toes" (if clearly the same character)

Return one character per line. Include all characters regardless of importance."""
```

**Expected LLM Response:**
```
Korra | Avatar Korra
Aang | Avatar Aang | Twinkle Toes
Mako
Bolin
Asami Sato | Asami
Tenzin | Master Tenzin
Lin Beifong | Chief Beifong
Katara | Master Katara
Zuko | Fire Lord Zuko
Toph Beifong
Bumi
Bumi
```

**Note**: The two "Bumi" entries (King Bumi and Commander Bumi) are listed separately because they're different characters. The validation step will detect this and mark them with `requires_disambiguation: true`.

**Updated Parsing:**
```python
def _parse_character_names(self, response: str) -> List[Dict[str, Any]]:
    """
    Parse LLM response with variation groupings.

    Returns:
        List of character dicts with name_variations tracked
    """
    characters = []

    for line in response.strip().split("\n"):
        if not line.strip():
            continue

        # Remove common prefixes (bullets, numbers)
        line = line.strip().lstrip("•-*123456789. ")

        # Split by " | " to get variations
        variations = [v.strip() for v in line.split("|") if v.strip()]

        if variations:
            canonical = variations[0]  # First is canonical
            characters.append({
                "name": canonical,
                "name_variations": variations,
                "discovered_via": ["comprehensive_query"]
            })

    return characters
```

**Benefits:**
- ✅ **Still just 1 LLM query** - No cost increase from current optimized implementation
- ✅ **Generalized** - No hardcoded title lists, works for ANY fictional universe
- ✅ **Variation tracking** - Preserves all name forms for debugging
- ✅ **Handles duplicates** - LLM lists different characters separately
- ✅ **Canonical selection** - LLM intelligently chooses most common form
- ✅ **Simple implementation** - Just enhanced prompt + slightly modified parsing

**Cons:**
- ⚠️ LLM might miss some variations if they don't appear in the same retrieved chunks
- ⚠️ Slightly more complex prompt (but clearer instructions)
- ⚠️ Response parsing is more complex (split by "|" instead of just newlines)

**Cost:**
```
Same as current implementation:
Discovery + Normalization: 1 query × 25 chunks × 350 tokens = ~8,750 input tokens
                          1 response × 80 tokens = ~80 output tokens (slightly higher for variations)
                          Cost: $0.009 input + $0.0004 output = $0.0094

No increase from current optimized approach!
```

**Handling Duplicate Names:**
The LLM will list "Bumi" twice (as separate characters). Then in `_validate_characters()`, we detect duplicates:

```python
def _detect_duplicate_names(self, characters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Flag characters that share the same canonical name."""
    name_counts = {}

    for char in characters:
        name = char["name"]
        name_counts[name] = name_counts.get(name, 0) + 1

    for char in characters:
        if name_counts[char["name"]] > 1:
            char["requires_disambiguation"] = True
            # Find all other characters with same name
            char["duplicate_names"] = [
                c["name"] for c in characters
                if c["name"] == char["name"]
            ]

    return characters
```

---

### Option 1: Post-Discovery Deduplication Query (NOT RECOMMENDED - 2 Queries)

**Approach**: After discovery, send all raw character names to LLM for intelligent grouping.

**Implementation:**
```python
def _deduplicate_characters_with_llm(
    self,
    characters: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Use LLM to intelligently group character name variations.

    Steps:
    1. Extract all discovered names
    2. Send to LLM with deduplication prompt
    3. Parse response to get character groupings
    4. Merge characters based on LLM groupings
    5. Fall back to fuzzy matching for any ungrouped names
    """
    # Extract all names
    all_names = [char["name"] for char in characters]

    # Build deduplication query
    prompt = f"""Given this list of character names from a wiki, identify which names refer to the same character.

Character names:
{chr(10).join(all_names)}

Group variations of the same character together. For each group:
1. List all variations on one line, separated by " | "
2. Put the most common/canonical name FIRST

Example format:
Zuko | Fire Lord Zuko | Lord Zuko
Aang | Avatar Aang
Katara | Master Katara

Return ONLY the groupings, one per line. Single names (no variations) should appear alone."""

    response = self.query_engine.llm_client.generate(
        prompt=prompt,
        system_prompt="You are analyzing character name variations from a fictional wiki.",
        temperature=0.0  # Deterministic output
    )

    # Parse response into groupings
    groupings = self._parse_name_groupings(response)

    # Merge characters based on groupings
    return self._merge_by_groupings(characters, groupings)
```

**Example LLM Response:**
```
Korra | Avatar Korra
Aang | Avatar Aang
Mako
Bolin
Asami Sato | Asami
Tenzin | Master Tenzin
Lin Beifong | Chief Lin Beifong | Chief Beifong
Katara | Master Katara
Zuko | Fire Lord Zuko | Lord Zuko
```

**Pros:**
- ✅ Works for ANY fictional universe without configuration
- ✅ Handles complex variations (titles, nicknames, partial names)
- ✅ LLM understands context (e.g., "Bumi" vs "Commander Bumi" vs "King Bumi" could be 2 different people)
- ✅ Single additional LLM call per discovery session (low cost)
- ✅ Canonical name selection is intelligent (most common form)

**Cons:**
- ⚠️ Adds 1 LLM call per discovery (~$0.001-0.003)
- ⚠️ Requires parsing LLM response (potential for format errors)
- ⚠️ Non-deterministic without temperature=0

**Cost Estimate:**
```
Input: 50 character names × 15 tokens = 750 tokens
Output: 30 groupings × 10 tokens = 300 tokens
Cost: (750 × $1/1M) + (300 × $5/1M) = $0.0022 per discovery

Total cost increase: < 1% of overall discovery cost
```

---

### Option 2: Embedded Normalization in Discovery Query

**Approach**: Instruct discovery query to return canonical names only.

**Implementation:**
```python
DISCOVERY_SYSTEM_PROMPT = """You are analyzing a wiki to extract character names.

Your task:
1. Identify all characters mentioned
2. Return ONLY the MOST COMMON NAME for each character (canonical form)
3. Strip titles/honorifics unless they are essential to the name
4. Format: "Character Name" (no descriptions, bullets, or numbering)

Examples:
- "Fire Lord Zuko" and "Lord Zuko" → return "Zuko"
- "Avatar Aang" → return "Aang"
- "Ser Jaime Lannister" → return "Jaime Lannister" (surname is essential)
- "Darth Vader" → return "Darth Vader" (title is essential/iconic)
- "Master Chief" → return "Master Chief" (this IS the name)

Return one name per line.
"""
```

**Pros:**
- ✅ No additional LLM calls
- ✅ Simpler implementation
- ✅ Works across all wikis

**Cons:**
- ❌ Loses variation tracking (can't see "Fire Lord Zuko" was mentioned)
- ❌ Harder to debug (don't know what raw names were discovered)
- ❌ LLM might make wrong decisions about essential vs non-essential titles
- ❌ Can't validate deduplication logic (it's hidden in discovery)

---

### Option 3: Fuzzy Matching Only (Remove Hardcoded Logic)

**Approach**: Remove `normalize_name()` entirely, rely on SequenceMatcher.

**Implementation:**
```python
def _deduplicate_characters(
    self,
    characters: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Deduplicate using fuzzy matching only."""
    def similarity(name1: str, name2: str) -> float:
        # Direct comparison without normalization
        return SequenceMatcher(
            None,
            name1.lower().strip(),
            name2.lower().strip()
        ).ratio()

    # Same merging logic, but without title stripping
    # ...
```

**Pros:**
- ✅ No hardcoded rules
- ✅ No additional LLM calls
- ✅ Simple implementation

**Cons:**
- ❌ "Zuko" vs "Fire Lord Zuko" = ~0.55 similarity (below 0.85 threshold)
- ❌ Won't detect most title variations
- ❌ Higher threshold = more false positives, lower = missed duplicates
- ❌ Doesn't solve the problem, just removes the broken solution

---

### Option 4: Two-Stage Hybrid Approach

**Approach**: Fuzzy matching for typos, LLM for title variations.

**Implementation:**
```python
def _deduplicate_characters(
    self,
    characters: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Two-stage deduplication."""

    # Stage 1: Fast fuzzy matching for obvious duplicates (typos, case)
    stage1_merged = self._fuzzy_deduplicate(characters, threshold=0.90)

    # Stage 2: LLM-based grouping for title variations
    stage2_merged = self._llm_deduplicate(stage1_merged)

    return stage2_merged
```

**Pros:**
- ✅ Best of both worlds
- ✅ Fuzzy matching catches typos without LLM cost
- ✅ LLM handles complex title variations

**Cons:**
- ⚠️ More complex implementation
- ⚠️ Two passes through data
- ❓ Unclear if fuzzy matching provides enough value to justify complexity

---

## UPDATED Recommended Approach: Option 5 (Combined Discovery + Normalization in ONE Query)

**Why Option 5 is Best:**
1. **Single LLM query** - No cost increase from current optimized implementation ($0.009)
2. **Preserves variation tracking** - We still see "Fire Lord Zuko" was discovered
3. **Debuggable** - name_variations field shows all forms found
4. **Generalizable** - Works for ANY wiki without hardcoded title lists
5. **Handles duplicates** - LLM lists "Bumi" twice if they're different characters
6. **Accurate** - LLM intelligently decides when to group vs separate
7. **Testable** - Can mock LLM responses for deterministic testing
8. **Simple** - Just enhanced prompt + modified parsing (no new methods needed)

**Implementation Strategy:**
```python
class CharacterExtractor:

    def _get_discovery_query(self) -> str:
        """Get comprehensive discovery query with variation grouping."""
        return """List ALL characters mentioned in this wiki, including:
- Main protagonists and antagonists
- Supporting characters and side characters
- Characters in major storylines
- Characters with significant relationships
- Characters mentioned in affiliations, factions, or groups
- Minor characters that appear in the content

IMPORTANT - Name Variations vs Different Characters:
- If you see the SAME character with different titles/names, group them with " | "
- If you see DIFFERENT characters who share a name, list them SEPARATELY
- When grouping, put the most common/canonical name FIRST
- Be CONSERVATIVE - only group if you're CERTAIN they're the same character

Examples:
✓ SAME character, different titles: "Zuko | Fire Lord Zuko" (same person)
✓ DIFFERENT characters, same name: "Bumi" and "Bumi" on separate lines (King Bumi vs Commander Bumi)
✓ Single variation only: "Mako" (no other variations seen)
✓ Nickname variation: "Aang | Twinkle Toes" (if clearly the same character)

Return one character per line. Include all characters regardless of importance."""

    def _parse_character_names(self, response: str) -> List[Dict[str, Any]]:
        """
        Parse LLM response with variation groupings.

        Returns:
            List of character dicts with name_variations tracked
        """
        characters = []

        for line in response.strip().split("\n"):
            if not line.strip():
                continue

            # Remove common prefixes (bullets, numbers)
            line = line.strip().lstrip("•-*123456789. ")

            # Split by " | " to get variations
            variations = [v.strip() for v in line.split("|") if v.strip()]

            if variations:
                canonical = variations[0]  # First is canonical
                characters.append({
                    "name": canonical,
                    "name_variations": variations,
                    "discovered_via": ["comprehensive_query"]
                })

        return characters

    def _deduplicate_characters(
        self,
        characters: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Deduplicate characters - now simpler since LLM already grouped variations.

        Just adds the standard fields and detects duplicate names.
        """
        # LLM already did the heavy lifting - just add standard fields
        for char in characters:
            char["canonical_name"] = char["name"]
            char["disambiguation"] = None
            char["requires_disambiguation"] = False
            char["duplicate_names"] = []

        # Detect duplicate names (different characters with same name)
        return self._detect_duplicate_names(characters)

    def _detect_duplicate_names(self, characters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Flag characters that share the same canonical name."""
        name_counts = {}

        for char in characters:
            name = char["name"]
            name_counts[name] = name_counts.get(name, 0) + 1

        for char in characters:
            if name_counts[char["name"]] > 1:
                char["requires_disambiguation"] = True
                # Find all other characters with same name
                char["duplicate_names"] = [
                    c["name"] for c in characters
                    if c["name"] == char["name"]
                ]

        return characters

    def _llm_deduplicate(
        self,
        characters: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Use LLM to group character name variations."""
        # Implementation as shown in Option 1
        pass

    def _fuzzy_deduplicate(
        self,
        characters: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Fallback: fuzzy matching without title normalization."""
        # Remove COMMON_TITLES logic
        # Keep similarity-based merging
        pass

    def _parse_name_groupings(self, response: str) -> Dict[str, List[str]]:
        """
        Parse LLM response into name groupings.

        Input:
            "Zuko | Fire Lord Zuko | Lord Zuko\\n"
            "Aang | Avatar Aang\\n"
            "Mako\\n"

        Output:
            {
                "Zuko": ["Zuko", "Fire Lord Zuko", "Lord Zuko"],
                "Aang": ["Aang", "Avatar Aang"],
                "Mako": ["Mako"]
            }
        """
        groupings = {}

        for line in response.strip().split("\\n"):
            if not line.strip():
                continue

            # Split by " | " delimiter
            variations = [v.strip() for v in line.split("|")]

            if variations:
                canonical = variations[0]  # First name is canonical
                groupings[canonical] = variations

        return groupings

    def _merge_by_groupings(
        self,
        characters: List[Dict[str, Any]],
        groupings: Dict[str, List[str]]
    ) -> List[Dict[str, Any]]:
        """
        Merge characters based on LLM groupings.

        Args:
            characters: Raw character list from discovery
            groupings: LLM-provided name groupings

        Returns:
            Merged character list with variations tracked
        """
        merged = []
        processed = set()

        for canonical, variations in groupings.items():
            # Find all characters matching any variation
            matching_chars = []
            for char in characters:
                if char["name"] in variations and char["name"] not in processed:
                    matching_chars.append(char)
                    processed.add(char["name"])

            if matching_chars:
                # Merge into single character entry
                merged_char = {
                    "name": canonical,
                    "canonical_name": canonical,
                    "name_variations": variations,
                    "discovered_via": [],
                    "requires_disambiguation": False,
                    "duplicate_names": []
                }

                # Merge discovered_via from all matches
                for char in matching_chars:
                    for query in char.get("discovered_via", []):
                        if query not in merged_char["discovered_via"]:
                            merged_char["discovered_via"].append(query)

                merged.append(merged_char)

        # Handle any unprocessed characters (LLM missed them)
        for char in characters:
            if char["name"] not in processed:
                merged.append({
                    "name": char["name"],
                    "canonical_name": char["name"],
                    "name_variations": [char["name"]],
                    "discovered_via": char.get("discovered_via", []),
                    "requires_disambiguation": False,
                    "duplicate_names": []
                })

        return merged
```

---

## LLM Prompt Design

### Deduplication System Prompt
```python
DEDUPLICATION_SYSTEM_PROMPT = """You are analyzing character names from a fictional wiki to identify variations.

Your task:
1. Group names that refer to the SAME character
2. Each line should contain all variations of ONE character, separated by " | "
3. Put the MOST COMMON or SIMPLEST name FIRST (canonical form)
4. Be conservative - only group if you're confident they're the same character
5. Consider context:
   - Titles/honorifics (Fire Lord Zuko = Zuko)
   - Nicknames (Twinkle Toes = Aang)
   - Full vs partial names (Lin Beifong = Chief Beifong, if clearly the same)
   - DO NOT merge if names could be different characters (e.g., King Bumi ≠ Commander Bumi)

Format:
CanonicalName | Variation1 | Variation2
AnotherName | Its Variation
StandaloneName

Return ONLY the groupings, no explanations."""
```

### User Prompt Template
```python
def _build_deduplication_prompt(self, names: List[str]) -> str:
    """Build deduplication prompt from character names."""
    return f"""Given this list of character names from a wiki, identify which names refer to the same character.

Character names:
{chr(10).join(names)}

Group variations of the same character together. Put the most common name first in each group.
Separate variations with " | ". One group per line."""
```

---

## Testing Strategy

### Mock LLM Response for Tests
```python
# tests/fixtures/llm_responses/character_discovery/deduplication.json
{
  "query": "Given this list of character names from a wiki",
  "pattern": "group variations.*same character",
  "response": "Korra | Avatar Korra\nAang | Avatar Aang\nMako\nBolin\nAsami Sato | Asami\nTenzin | Master Tenzin\nLin Beifong | Chief Beifong | Chief Lin Beifong\nKatara | Master Katara\nZuko | Fire Lord Zuko\nToph Beifong | Toph\nBumi | King Bumi\nBumi | Commander Bumi",
  "usage": {
    "input_tokens": 750,
    "output_tokens": 300
  },
  "metadata": {
    "purpose": "Character name deduplication - variation grouping",
    "notes": "Shows both Bumis as SEPARATE entries (different characters, same name)"
  }
}
```

### Test Cases
```python
class TestCharacterExtractorLLMDeduplication:
    """Test LLM-based name deduplication."""

    def test_llm_deduplicate_groups_title_variations(self):
        """Test that LLM groups title variations correctly."""
        extractor = CharacterExtractor(project_name="test")

        characters = [
            {"name": "Zuko", "discovered_via": ["comprehensive_query"]},
            {"name": "Fire Lord Zuko", "discovered_via": ["comprehensive_query"]}
        ]

        # Mock LLM to return: "Zuko | Fire Lord Zuko"
        result = extractor._llm_deduplicate(characters)

        assert len(result) == 1
        assert result[0]["name"] == "Zuko"
        assert "Fire Lord Zuko" in result[0]["name_variations"]

    def test_llm_deduplicate_preserves_distinct_characters(self):
        """Test that LLM doesn't merge different characters with same name."""
        extractor = CharacterExtractor(project_name="test")

        characters = [
            {"name": "Bumi", "discovered_via": ["comprehensive_query"]},
            {"name": "King Bumi", "discovered_via": ["comprehensive_query"]},
            {"name": "Commander Bumi", "discovered_via": ["comprehensive_query"]}
        ]

        # Mock LLM to return TWO groups:
        # "Bumi | King Bumi"
        # "Bumi | Commander Bumi"
        # (LLM recognizes these are different characters!)

        result = extractor._llm_deduplicate(characters)

        # Should have 2 distinct characters, both named "Bumi"
        assert len(result) == 2
        # Both should be flagged for disambiguation
        assert result[0].get("requires_disambiguation") == True
        assert result[1].get("requires_disambiguation") == True

    def test_llm_deduplicate_fallback_on_error(self):
        """Test fallback to fuzzy matching if LLM fails."""
        extractor = CharacterExtractor(project_name="test")

        # Mock LLM to raise exception
        extractor.query_engine.llm_client.generate = Mock(side_effect=Exception("API Error"))

        characters = [{"name": "Korra", "discovered_via": ["comprehensive_query"]}]

        # Should not crash, should fall back to fuzzy matching
        result = extractor._deduplicate_characters(characters)

        assert len(result) == 1
        assert result[0]["name"] == "Korra"

    def test_parse_name_groupings_simple(self):
        """Test parsing LLM grouping response."""
        extractor = CharacterExtractor(project_name="test")

        response = """Zuko | Fire Lord Zuko
Aang | Avatar Aang
Mako"""

        groupings = extractor._parse_name_groupings(response)

        assert groupings["Zuko"] == ["Zuko", "Fire Lord Zuko"]
        assert groupings["Aang"] == ["Aang", "Avatar Aang"]
        assert groupings["Mako"] == ["Mako"]

    def test_merge_by_groupings(self):
        """Test merging characters based on groupings."""
        extractor = CharacterExtractor(project_name="test")

        characters = [
            {"name": "Zuko", "discovered_via": ["comprehensive_query"]},
            {"name": "Fire Lord Zuko", "discovered_via": ["comprehensive_query"]}
        ]

        groupings = {
            "Zuko": ["Zuko", "Fire Lord Zuko"]
        }

        result = extractor._merge_by_groupings(characters, groupings)

        assert len(result) == 1
        assert result[0]["name"] == "Zuko"
        assert result[0]["canonical_name"] == "Zuko"
        assert set(result[0]["name_variations"]) == {"Zuko", "Fire Lord Zuko"}
```

---

## Implementation Checklist

### Phase 1: Core LLM Deduplication
- [ ] Remove `COMMON_TITLES` hardcoded list
- [ ] Implement `_llm_deduplicate()` method
- [ ] Implement `_parse_name_groupings()` helper
- [ ] Implement `_merge_by_groupings()` helper
- [ ] Create `DEDUPLICATION_SYSTEM_PROMPT`
- [ ] Update `_deduplicate_characters()` to call LLM version

### Phase 2: Fallback Logic
- [ ] Implement `_fuzzy_deduplicate()` (without title normalization)
- [ ] Add try/except in `_deduplicate_characters()`
- [ ] Add logging for fallback usage

### Phase 3: Testing
- [ ] Create deduplication.json fixture
- [ ] Update MockLLMClient to handle deduplication pattern
- [ ] Write 8-10 test cases for LLM deduplication
- [ ] Update existing variation tracking tests
- [ ] Test fallback behavior

### Phase 4: Configuration
- [ ] Add config option: `enable_llm_deduplication` (default: true)
- [ ] Add config option: `fuzzy_similarity_threshold` (default: 0.85)
- [ ] Add config option: `deduplication_temperature` (default: 0.0)

### Phase 5: Documentation
- [ ] Update CLAUDE.md with LLM deduplication approach
- [ ] Update mock fixture guidelines
- [ ] Add cost estimation notes

---

## Cost Impact Analysis

### Current Approach
```
Discovery: 1 LLM call × ~8,750 tokens = $0.009
Deduplication: 0 LLM calls (hardcoded logic)
Total: $0.009 per discovery
```

### Proposed Approach
```
Discovery: 1 LLM call × ~8,750 tokens = $0.009
Deduplication: 1 LLM call × ~1,050 tokens = $0.002
Total: $0.011 per discovery

Cost increase: 22% ($0.002)
```

**Is this worth it?**
- ✅ YES - Generalizability to any wiki is worth $0.002
- ✅ Small absolute cost increase (less than 1 cent)
- ✅ Eliminates maintenance burden of updating title lists
- ✅ Higher accuracy than hardcoded rules

---

## Alternative: Configuration-Based Title Lists (NOT RECOMMENDED)

**Idea**: Instead of hardcoded list, load from config per project.

```yaml
# config/projects/avatar_wiki.yaml
character_extraction:
  common_titles:
    - Avatar
    - Fire Lord
    - Chief
    - Master

# config/projects/naruto_wiki.yaml
character_extraction:
  common_titles:
    - Hokage
    - Sensei
    - Lord
```

**Why NOT Recommended:**
- ❌ Still requires manual configuration per wiki
- ❌ User must know titles before analyzing wiki (defeats automation)
- ❌ Doesn't handle edge cases (nicknames, partial names)
- ❌ LLM approach is only $0.002 more expensive

---

## Migration Path

### Step 1: Implement alongside existing code
- Add new `_llm_deduplicate()` method
- Keep old `normalize_name()` as fallback
- Add feature flag in config

### Step 2: Test on multiple wikis
- Avatar wiki (current test data)
- Naruto wiki (different title system)
- Harry Potter wiki (different title system)
- Verify accuracy vs current approach

### Step 3: Deprecate hardcoded logic
- Remove `COMMON_TITLES`
- Remove `normalize_name()`
- Keep only LLM + fuzzy fallback

### Step 4: Update documentation
- CLAUDE.md
- Mock maintenance guidelines
- Cost estimates

---

## Success Criteria

✅ **Generalizability**: Works on wikis from ANY fictional universe without configuration
✅ **Accuracy**: Groups variations correctly (>95% accuracy on test cases)
✅ **Cost**: Adds <$0.01 per discovery session
✅ **Maintainability**: No hardcoded domain-specific logic
✅ **Debuggability**: Can inspect LLM groupings vs raw names
✅ **Testability**: Mock-friendly, deterministic with temperature=0
✅ **Fallback**: Graceful degradation if LLM fails

---

## Risk Assessment

**Low Risk:**
- ✅ Small cost increase (<1 cent per discovery)
- ✅ Easy to test with mocks
- ✅ Fallback to fuzzy matching on failure
- ✅ Can A/B test vs current approach
- ✅ Reversible (feature flag)

**Moderate Risk:**
- ⚠️ LLM might make grouping mistakes (mitigated by temperature=0 and conservative prompt)
- ⚠️ Response parsing could fail (mitigated by robust parser + fallback)
- ⚠️ Need to update mocks for new LLM call pattern

**Mitigation:**
- Comprehensive testing on multiple wikis
- Clear logging of LLM decisions
- Fallback to fuzzy matching
- User can review `name_variations` in output
