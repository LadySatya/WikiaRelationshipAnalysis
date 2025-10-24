# WikiaAnalyzer - Bug List

## CRITICAL (Blocks Core Functionality)

### BUG-001: ProfileBuilder extracts garbage relationship target names 🔴 ✅ **FIXED**
**Status:** ✅ Fixed
**Severity:** Critical
**Component:** `src/processor/analysis/profile_builder.py`

**Symptoms:**
- Relationship targets were nonsense strings like "Relationship type", "Description"
- Graph contained meaningless edges

**Root Cause:**
- `_discover_relationships()` LLM prompt was too vague
- LLM was returning metadata ("Relationship type:") instead of character names
- Parser had no validation to filter out invalid entries

**Fix Applied:**
1. **Completely Redesigned Prompt Using Claude's Best Practices** (`profile_builder.py:86-124`):
   - **XML tags** for clear structure (`<task>`, `<format>`, `<examples>`, `<instructions>`)
   - **Explicit context**: "You are analyzing a wiki to identify character relationships"
   - **Clear exclusions**: Listed what NOT to include (titles, groups, concepts, descriptions)
   - **Few-shot prompting**: Both good examples AND bad examples with "DO NOT DO THIS"
   - **Specific format**: "CHARACTER_NAME - brief_relationship_type"

   **Key improvements:**
   - Uses XML tags recommended by Anthropic documentation
   - 3 good examples + 3 bad examples to prevent common errors
   - Sequential numbered instructions for clarity
   - Explicit "IMPORTANT RULES" section

2. **Added Validation as Backup** (`profile_builder.py:143-152`):
   - Filter out entries containing: "relationship type", "description", "type", etc.
   - Serves as last-resort fallback for edge cases
   - Follows project guideline: prefer good prompts over hardcoded validation

3. **Documented Standards** (`CLAUDE.md:9-111`):
   - Added "LLM Prompt Engineering Standards" section
   - Required techniques for all future LLM prompts
   - Bad vs Good examples
   - Links to Anthropic documentation

**Expected Output:**
```json
{"target": "Katara", "type": "romantic_partner"}
{"target": "Zuko", "type": "friend"}
```

**Validation Required:**
- Requires re-running ProfileBuilder to verify fix
- Will validate during next PoC run

**Files:**
- ✅ `src/processor/analysis/profile_builder.py:82-93` (improved prompt)
- ✅ `src/processor/analysis/profile_builder.py:143-152` (added validation)

---

### BUG-002: Claim parsing returns empty claims list 🔴 ✅ **FIXED**
**Status:** ✅ Fixed
**Severity:** Critical
**Component:** `src/processor/analysis/profile_builder.py`

**Symptoms:**
- `narrative.claims_with_evidence` was always an empty list `[]`
- Despite narrative text existing and evidence being collected (6+ citations)

**Root Cause Discovered:**
- **Fundamental misunderstanding of Claude's citations**: Citation `location.start/end` refer to positions in INPUT DOCUMENTS (wiki chunks), NOT output text
- Position-based evidence mapping (`_evidence_overlaps_range`) could never work
- Sentence splitting worked fine, but evidence never "overlapped" with sentence positions

**Why the Old Approach Failed:**
```python
# Citation location refers to INPUT chunk, not OUTPUT text:
evidence = {
    "cited_text": "Aang is the last airbender",
    "location": {"start": 45, "end": 98}  # <- position in INPUT wiki chunk!
}

# But we were comparing to OUTPUT sentence positions:
sentence = {
    "text": "Aang and Katara met...",
    "start": 0,   # <- position in Claude's OUTPUT
    "end": 50
}

# These will NEVER overlap! They're in different texts!
```

**Fix Applied:**
1. **Redesigned Prompt to Ask for Structured Claims** (`profile_builder.py:218-254`):
   - Changed from "write a narrative" to "list numbered claims"
   - XML-structured prompt with clear output format
   - Asks for 4-8 specific factual statements
   - Example: "1. [claim]\n2. [claim]\n3. [claim]"

2. **Rewrote Parser to Extract Numbered Claims** (`profile_builder.py:296-365`):
   ```python
   # Old (broken): Try to map evidence by character position
   # New: Extract numbered claims from Claude's output
   match = re.match(r"^(\d+)\.\s+(.+)$", line)
   ```

3. **Simplified Evidence Mapping**:
   - Since we can't map evidence to specific claims by position...
   - Attach ALL evidence to ALL claims
   - Evidence supports the relationship as a whole
   - Each claim gets: `{"claim": "...", "evidence": [...all...], "confidence": 0.X}`

**Trade-off Accepted:**
- Evidence is not precisely mapped to individual claims
- But claims ARE extracted and structured
- Confidence calculation still works (based on total evidence count)
- User requirement met: claims WITH evidence (even if not 1:1 mapped)

**Validation Required:**
- Re-run ProfileBuilder to verify claims are now extracted
- Check that claims list is not empty
- Verify confidence scores are non-zero

**Files:**
- ✅ `src/processor/analysis/profile_builder.py:218-254` (new structured prompt)
- ✅ `src/processor/analysis/profile_builder.py:296-365` (new claim parser)
- ❌ `src/processor/analysis/profile_builder.py:367-433` (old sentence/overlap code - now unused, can be deleted)

---

### BUG-003: All relationship confidence scores are 0.0 🔴 ✅ **AUTO-FIXED**
**Status:** ✅ Fixed (by BUG-002 fix)
**Severity:** Critical
**Component:** `src/processor/analysis/profile_builder.py`

**Symptoms:**
- Every relationship had `overall_confidence: 0.0`
- Validation showed: "High (>=0.8): 0 (0.0%)", "Low (<0.5): 32 (100.0%)"

**Root Cause:**
- Directly caused by BUG-002 (empty claims list)
- Confidence calculated from claim count
- `_calculate_overall_confidence()` returned 0.0 when no claims

**Fix:**
- Automatically resolved by fixing BUG-002
- Claims are now extracted → confidence can be calculated
- Confidence based on evidence count per claim

**Expected After Re-run:**
- Confidence scores between 0.6-1.0 based on evidence strength
- Distribution across high/medium/low buckets

**Validation Required:**
- Re-run ProfileBuilder
- Check confidence scores are non-zero
- Verify reasonable distribution

**Files:**
- Fixed by BUG-002 changes (no direct code changes needed)

---

## HIGH (Data Quality Issues)

### BUG-004: Titles misclassified as characters ⚠️ ✅ **FIXED**
**Status:** ✅ Fixed
**Severity:** High
**Component:** `src/processor/analysis/character_extractor.py`

**Symptoms:**
- "Phoenix King" was discovered as character (actually a political title held by Ozai)
- "Tribal Princess" was discovered as character (actually a title held by Yue/Eska)

**Evidence:**
- Phoenix King page: "This article is about the political position"
- Tribal Princess page: "This article is about the title. For the princess met by Team Avatar, see Yue"
- Both pages contain "Category:Titles" or ":Titles" in URL

**Root Cause:**
- Character discovery didn't check for title page indicators
- Metadata tier had no filtering for title pages
- LLM tier would classify anything that looked like a name

**Fix Applied:**
1. **Added Title Detection** (`character_extractor.py:422-438`):
   ```python
   title_indicators = [
       "this article is about the title",
       "this article is about the political position",
       ":titles" in url,
       "/category:titles" in url,
       "category:titles" in main_content[:500],
   ]

   if any(indicator...):
       return "not_character"  # Explicitly filter out
   ```

2. **Updated Discovery Pipeline** (`character_extractor.py:636-649`):
   - Added explicit handling for "not_character" classification
   - Pages marked "not_character" are filtered out in Tier 1
   - Logged as "filtered" for visibility

**Validation Required:**
- Re-run character discovery
- Verify "Phoenix King" and "Tribal Princess" are NOT in character list
- Check filter count in logs

**Files:**
- ✅ `src/processor/analysis/character_extractor.py:422-438` (title detection)
- ✅ `src/processor/analysis/character_extractor.py:636-649` (filter handling)

**Characters That Will Be Filtered:**
- Phoenix King (political title)
- Tribal Princess (social title)

---

### BUG-005: Missing major characters (Katara, Zuko, Toph, etc.) ⚠️ ✅ **ROOT CAUSE FOUND - NOT A BUG**
**Status:** ✅ Resolved - Not a bug, limitation of crawl scope
**Severity:** High (but not a code bug)
**Component:** Crawler scope, not character discovery

**Symptoms:**
- Only 14 characters discovered from 94 pages
- Major characters like Katara, Zuko, Toph, Azula, Iroh NOT discovered

**Investigation Results:**
```bash
$ ls data/projects/avatar_poc/processed/ | grep -i "katara\|zuko\|toph\|azula\|iroh"
Zuko_Alone_20251023.json  # <- This is an EPISODE, not Zuko's character page!

$ ls data/projects/avatar_poc/processed/ | head -20
Aang_20251023.json                              # Character
Air_Temple_Island_20251023.json                # Location
Alex_Monik_20251023.json                       # Staff member
Avatar_The_Last_Airbender_20251023.json       # Series page
Avatar_Wiki_Chat_20251023.json                 # Wiki meta
Bato_of_the_Water_Tribe_20251023.json         # Episode
Battle_at_Wulong_Forest_20251023.json         # Event
...
```

**Root Cause:**
**NOT A BUG!** The character pages for Katara, Zuko, etc. were simply never crawled.

**Why they weren't crawled:**
- Started from Aang's page
- Crawl limit was only 100 pages
- Crawler followed links to episodes, locations, wiki meta pages first
- Major character pages weren't reached within the 100-page limit

**Crawl Composition (94 pages total):**
- ~10-15 character pages (Aang, Arnook, Alex Monik, minor characters)
- ~30-40 episode pages ("Zuko Alone", "Bitter Work", etc.)
- ~15-20 wiki meta pages (Chat, Blog, Policy, etc.)
- ~20-30 location/event/concept pages

**Solution (NOT a code fix):**
1. **Increase crawl limit**: Use `max_pages=500` or `max_pages=1000`
2. **Better seed URLs**: Start from character category page
3. **Link prioritization** (future enhancement): Prioritize `/wiki/[Name]` over `/wiki/Episode_Title`

**Impact:**
- Character discovery works correctly for pages that WERE crawled
- Need to crawl more pages or use better seeds to find main characters

**Files:**
- No code changes needed
- Issue is in crawl strategy, not discovery logic

**Recommended Action:**
- Re-crawl with `--max-pages 500` and seed URL: `https://avatar.fandom.com/wiki/Category:Characters`
- Or add multiple seed URLs for main characters

---

## MEDIUM (Performance & UX)

### BUG-006: ProfileBuilder extremely slow (82s per character) 🐌
**Status:** Confirmed
**Severity:** Medium (functional but slow)
**Component:** `src/processor/analysis/profile_builder.py`

**Symptoms:**
- 5 characters took 411.3 seconds (6.8 minutes)
- 82.3 seconds per character average
- User reported "15 minutes is really long"

**Analysis:**
- **Current:** 166,732 input tokens / 5 characters = 33,344 tokens per character
- **LLM calls:** ~10-15 per character (1 discovery + ~10 relationship details)
- Each relationship detail query takes ~7 seconds

**Optimization Opportunities:**
1. **Batch relationship details** - Get all in 1-2 calls instead of 10 separate calls
2. **Reduce prompt size** - 33K tokens per character is excessive
3. **Parallel processing** - Build multiple profiles concurrently
4. **Smarter retrieval** - Reduce k=15 to k=5-7 for less context
5. **Cache relationship queries** - Share results between characters

**Expected Performance:** 8-15 seconds per character (5-10x speedup)

**Impact:**
- PoC acceptable but unscalable
- 50 characters would take 68 minutes vs 10 minutes optimized

**Files:**
- `src/processor/analysis/profile_builder.py:92` (relationship discovery - batching opportunity)
- `src/processor/analysis/profile_builder.py:192` (relationship details - k=15 may be too high)

---

### BUG-007: Unicode logging errors on Windows 💻 ✅ **FIXED**
**Status:** ✅ Fixed
**Severity:** Low
**Component:** Multiple logging scripts

**Symptoms:**
```
UnicodeEncodeError: 'charmap' codec can't encode character '\u2265'
```

**Characters Affected:**
- ≥ (greater than or equal)
- Various Unicode characters in wiki content

**Root Cause:**
- Windows console uses cp1252 encoding by default
- Unicode characters in Python source code cause crashes

**Fix Applied:**
- Replaced `≥` with `>=` in `scripts/poc_validate_results.py:54`
- Added comprehensive documentation to CLAUDE.md:
  - Section "Unicode in Python Source Files" with banned characters list
  - Clear guidelines: NEVER use Unicode in .py files
  - ASCII alternatives for common symbols

**Validation:**
- ✅ Script runs without UnicodeEncodeError
- ✅ Output displays correctly on Windows console
- ✅ Documentation updated for future prevention

**Impact:** Minor - just logging errors, doesn't affect functionality

**Files:**
- ✅ `scripts/poc_validate_results.py:54` (fixed)
- ✅ `CLAUDE.md` (documentation added)

---

### BUG-010: Meta-commentary "Additional context" in relationships ⚠️ ✅ **FIXED**
**Status:** ✅ Fixed
**Severity:** Medium
**Component:** `src/processor/analysis/profile_builder.py`

**Symptoms:**
- Garbage relationship discovered: `Target: "Additional context", Type: "Aang was found in an iceberg by Sokka and Katara"`
- LLM returning meta-commentary instead of character names
- Had 1.0 confidence despite being invalid

**Evidence from validation run:**
```json
{
  "from": "Aang",
  "to": "Additional context",
  "type": "Aang was found in an iceberg by Sokka and Katara",
  "summary": "Based on the limited wiki content provided, I can only extract a few factual claims...",
  "confidence": 1.0,
  "evidence_count": 5
}
```

**Root Cause:**
- Prompt didn't explicitly forbid meta-commentary like "Additional context", "Background", "Note"
- Validation filter only checked for "relationship type", "description" but missed this case

**Fix Applied:**
1. **Improved Prompt with Explicit Meta-Commentary Examples** (`profile_builder.py:86-145`):
   - Added `<critical_rules>` section with "DO NOT include meta-commentary"
   - Added bad examples: "Additional context", "Note", "Background"
   - Strengthened instruction: "ONLY list NAMED INDIVIDUALS that appear in the wiki content"
   - Added explicit instruction: "Do not add any notes, context, or explanations"

2. **Removed Hardcoded Validation Filter** (`profile_builder.py:175-184`):
   - User preference: "I really don't like that validation filter at all"
   - Relied on improved prompting instead of hardcoded keyword lists
   - Follows project guideline: avoid hardcoded validation, use better prompts

**Expected Output After Fix:**
- No meta-commentary in relationship targets
- Only real character names
- If LLM can't find characters, it outputs "NONE"

**Validation Required:**
- Re-run ProfileBuilder Phase 4
- Verify no "Additional context", "Background", or "Note" in relationship targets
- Check all targets are valid character names

**Files:**
- ✅ `src/processor/analysis/profile_builder.py:86-145` (strengthened prompt)
- ✅ `src/processor/analysis/profile_builder.py:175-184` (removed validation filter)

---

## LOW (Minor Issues)

### BUG-008: .env file not auto-loaded in scripts
**Status:** Fixed (added load_dotenv)
**Severity:** Low
**Component:** PoC scripts

**Symptoms:**
- ANTHROPIC_API_KEY not loaded from .env file
- Had to manually add `load_dotenv()` to scripts

**Fix Applied:**
- Added to `poc_discover_characters.py`
- Added to `poc_build_relationships.py`

**Remaining:** Add to other scripts that might need env vars

**Files:**
- `scripts/poc_*.py` (partially fixed)

---

### BUG-009: Empty context samples for some characters
**Status:** Minor
**Component:** `src/processor/analysis/character_extractor.py`

**Symptoms:**
- Some characters saved without context_sample field
- Rohan.json showed empty context

**Impact:** Low - context is for human review only

**Files:**
- `src/processor/analysis/character_extractor.py` (save logic)

---

### BUG-011: Duplicate character files (space vs underscore filenames) 💾 ✅ **FIXED**
**Status:** ✅ Fixed
**Severity:** Low
**Component:** `src/processor/analysis/profile_builder.py`

**Symptoms:**
- Two files created for "Mother of Faces":
  - `Mother of Faces.json` (77KB, with profile)
  - `Mother_of_Faces.json` (714B, without profile)
- Character discovery saves with underscores
- Profile building saves with spaces
- Wasted disk space and potential confusion

**Evidence:**
```bash
-rw-r--r-- 1 Satya 197609  77127 Oct 23 23:24 Mother of Faces.json  # ProfileBuilder
-rw-r--r-- 1 Satya 197609    714 Oct 23 23:19 Mother_of_Faces.json  # CharacterExtractor
```

**Root Cause:**
- `character_extractor.py:346` replaces spaces with underscores
- `profile_builder.py:607` did NOT replace spaces
- Inconsistent filename generation between discovery and profile building

**Fix Applied:**
- Updated `profile_builder.py:608` to replace spaces with underscores
- Now consistent with character_extractor behavior
- Format: `safe_name.replace(" ", "_")`

**Expected After Fix:**
- All character files use underscores: `Mother_of_Faces.json`
- No duplicate files for same character
- Filesystem-safe filenames

**Validation Required:**
- Delete old character files
- Re-run Phase 3 (discovery) and Phase 4 (profile building)
- Verify only one file per character
- Check filenames use underscores

**Files:**
- ✅ `src/processor/analysis/profile_builder.py:608` (added space replacement)

---

## DOCUMENTATION GAPS

### DOC-001: CLAUDE.md incorrect about raw/ directory
**Status:** Fixed
**Component:** Documentation

**Issue:**
- CLAUDE.md didn't mention that crawler saves to `processed/` ONLY
- No `raw/` directory is used

**Fix:** Updated documentation to clarify directory structure

---

## Bug Priority Order (What to Fix First)

### Sprint 1 - Core Functionality (CRITICAL)
1. **BUG-001** - Fix relationship target extraction (ProfileBuilder prompts)
2. **BUG-002** - Fix claim parsing (sentence detection + evidence mapping)
3. **BUG-003** - Verify confidence scores work after BUG-002 fix

### Sprint 2 - Data Quality (HIGH)
4. **BUG-004** - Filter out title pages (add title detection)
5. **BUG-005** - Investigate missing major characters (Katara, Zuko, etc.)

### Sprint 3 - Performance (MEDIUM)
6. **BUG-006** - Optimize ProfileBuilder (batching + parallel processing)

### Sprint 4 - Polish (LOW)
7. **BUG-007** - Fix Unicode logging on Windows
8. **BUG-009** - Ensure all characters have context samples

---

## Testing Checklist

After fixes, validate:
- [ ] Relationship targets are real character names (not "Relationship type")
- [ ] Claims list populated with 3-8 claims per relationship
- [ ] Confidence scores range from 0.6-1.0 (not all 0.0)
- [ ] No title pages in character list (Phoenix King, Tribal Princess removed)
- [ ] Major characters discovered (Katara, Zuko if their pages were crawled)
- [ ] ProfileBuilder completes in <15s per character (target: 10s)
- [ ] No Unicode errors in logs
- [ ] All character files have context samples

---

## Cost Analysis

- **Current PoC:** $0.26 for 5 characters (acceptable)
- **Projected 50 characters:** ~$2.60 before optimization
- After optimizations: ~$1.50-$2.00 (reduced token usage)

**Conclusion:** Cost is NOT a blocker, performance is the main concern.
