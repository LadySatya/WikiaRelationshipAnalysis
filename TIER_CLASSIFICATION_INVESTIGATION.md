# Tier Classification Investigation Report

**Date:** 2025-10-23  
**Issue:** Tier 1 and Tier 2 classification returning 0 characters, forcing all discovery through expensive Tier 3

## Executive Summary

**Root Cause Found:** The crawler is NOT extracting namespace or infobox data, causing Tier 1 metadata classification to fail completely.

**Impact:** 
- Current cost: $0.01 per 30 pages (100% Tier 3)
- Potential cost with working Tier 1/2: $0.001-0.003 per 30 pages (70-90% reduction)

## Detailed Findings

### Issue 1: Missing `namespace` Field ❌

**Expected:** Crawled pages should have `content.namespace` field (e.g., "Main", "Character", "Location")

**Actual:** Field is completely missing from saved page data

**Why:**
1. `WikiaParser.extract_wikia_content()` DOES extract namespace (line 134)
2. BUT `WikiaCrawler` NEVER CALLS `WikiaParser` 
3. Instead, it only calls `PageExtractor.extract_content()` (line 298)
4. `PageExtractor.extract_content()` does NOT extract namespace

**Code Evidence:**
```python
# src/crawler/core/crawler.py:298
extracted_data = self.page_extractor.extract_content(html, url)

# src/crawler/extraction/page_extractor.py:55-62
result = {
    "url": url,
    "title": self.extract_title(soup),
    "main_content": self.extract_main_content(soup),
    "links": self.extract_links(soup, url),
    "infobox_data": self.extract_infobox_data(soup),  # Returns {}!
    "is_disambiguation": self.is_disambiguation_page(soup),
    # NO NAMESPACE!
}
```

**Verification:**
```bash
$ cat data/projects/avatar_test/processed/Bolin_20251023.json | jq '.content | keys'
[
  "url",
  "title", 
  "main_content",
  "links",
  "infobox_data",  # exists but empty
  "is_disambiguation"
]
# Notice: NO namespace field!
```

---

### Issue 2: Empty `infobox_data` ❌

**Expected:** Character pages should have infobox_data with fields like "species", "affiliation", "age", etc.

**Actual:** infobox_data exists but is ALWAYS empty ({})

**Why:**
1. `PageExtractor.extract_infobox_data()` extracts Wikipedia-style infoboxes
2. Fandom wikis use "Portable Infoboxes" (different HTML structure)
3. `WikiaParser.extract_portable_infobox()` exists to handle Fandom's format
4. BUT `WikiaCrawler` never uses `WikiaParser`, so portable infoboxes are never extracted

**Code Evidence:**
```python
# PageExtractor tries to find Wikipedia infoboxes
def extract_infobox_data(self, soup: BeautifulSoup) -> Dict:
    infobox = soup.find("table", class_="infobox")  # Wikipedia format
    # Fandom uses: <aside class="portable-infobox"> (different!)
```

**Verification:**
```bash
$ cat data/projects/avatar_test/processed/Bolin_20251023.json | jq '.content.infobox_data'
{}  # Always empty!
```

---

### Issue 3: Tier 1 Logic Requires Both Fields

**Tier 1 Classification Logic** (character_extractor.py:422-446):
```python
def _classify_by_metadata(self, page: Dict[str, Any]) -> Optional[str]:
    # Check 1: Namespace (FAILS - field missing)
    namespace = page.get("namespace", "").lower()
    if "character" in namespace:
        return "character"
    
    # Check 2: URL patterns (FAILS - Bolin URL is /wiki/Bolin, not /characters/)
    url = page.get("url", "").lower()
    if any(pattern in url for pattern in ["/characters/", "/character:"]):
        return "character"
    
    # Check 3: Infobox (FAILS - empty dict)
    infobox = page.get("infobox_data", {})
    if infobox:
        character_indicators = ["species", "affiliation", "age", "gender", ...]
        matches = sum(1 for field in character_indicators if field in infobox)
        if matches >= 2:
            return "character"
    
    return None  # Always returns None - no checks pass!
```

**Result:** ALL 28 pages marked as "ambiguous", forcing Tier 2 classification

---

### Issue 4: Why Tier 2 Also Failed? (Hypothesis)

**Tier 2** uses batch LLM title classification. It should have worked on titles like:
- "Bolin | Avatar Wiki | Fandom"
- "Zaheer | Avatar Wiki | Fandom"  
- "Raiko | Avatar Wiki | Fandom"

**Possible reasons it returned 0:**
1. Title suffix " | Avatar Wiki | Fandom" confuses the LLM
2. LLM prompt may be too conservative
3. Need to investigate Tier 2 code and actual LLM response

**Action:** Needs separate investigation (check LLM prompts and responses)

---

## Impact Analysis

### Current State (Broken)
- Tier 1: 0 characters (0%)
- Tier 2: 0 characters (0%)
- Tier 3: 6 characters (100%)
- Cost per 30 pages: $0.0105

### Expected State (Fixed)
- Tier 1: 4-6 characters (67-100%) - FREE
- Tier 2: 0-2 characters (0-33%) - CHEAP (~$0.001)
- Tier 3: 0 characters (0%) - EXPENSIVE (not needed)
- Cost per 30 pages: $0.001-0.003

### Cost Savings
- **Current:** $0.35/1000 pages
- **Fixed:** $0.05-0.10/1000 pages
- **Savings:** 70-85% reduction

---

## Architecture Issues

### Dead Code: WikiaParser Never Used

`WikiaParser` exists and has correct logic for:
- Extracting namespace from URLs
- Extracting portable infoboxes (Fandom format)
- Detecting disambiguation pages

BUT it's never instantiated or called by WikiaCrawler!

**File locations:**
- Defined: `src/crawler/extraction/wikia_parser.py` (311 lines)
- Imported: NOWHERE in crawler.py
- Used: NEVER

**This suggests:**
1. WikiaParser was written for Phase 1 but not integrated
2. PageExtractor was used as quick placeholder
3. Integration was never completed

---

## Recommended Fixes (Do NOT Implement Yet)

### Fix 1: Integrate WikiaParser into Crawler

**Option A: Replace PageExtractor** (breaking change)
- Remove PageExtractor
- Use WikiaParser.extract_wikia_content() instead
- Risk: May break existing data format

**Option B: Merge both** (safe)
- Call both PageExtractor and WikiaParser
- Merge results: `{**page_data, **wikia_data}`
- Preserves existing data, adds new fields

**Option C: Enhance PageExtractor** (recommended)
- Add namespace extraction to PageExtractor
- Add portable infobox extraction to PageExtractor
- Keep single extractor, avoid complexity

### Fix 2: Investigate Tier 2 Failure

- Add debug logging to `_classify_titles_batch()`
- Print actual LLM prompt and response
- Check if title suffix needs cleaning
- Verify prompt is not too conservative

### Fix 3: Add Namespace to Saved Data

Even if extraction works, CharacterExtractor expects:
```python
page.get("namespace", "")  # Gets from content dict
```

But saved format is:
```python
{
  "url": "...",
  "content": {
    "title": "...",
    # namespace should be here!
  }
}
```

Need to ensure namespace is saved inside `content` dict.

---

## Test Data Evidence

### Bolin Page (Character - Should Pass Tier 1)

**URL:** https://avatar.fandom.com/wiki/Bolin

**What we have:**
```json
{
  "content": {
    "title": "Bolin | Avatar Wiki | Fandom",
    "infobox_data": {},  // EMPTY!
    // NO namespace field!
  }
}
```

**What we should have:**
```json
{
  "content": {
    "title": "Bolin",
    "namespace": "Main",  // MISSING
    "infobox_data": {  // SHOULD HAVE DATA
      "species": "Human",
      "affiliation": "Team Avatar",
      "gender": "Male",
      "profession": "Pro-bender",
      ...
    }
  }
}
```

---

## Next Steps

1. **Decide on fix approach** (Option A, B, or C above)
2. **Investigate Tier 2 failure separately** (add logging)
3. **Update CharacterExtractor** if needed (field name compatibility)
4. **Re-crawl test data** after fix to verify
5. **Measure actual cost savings**

---

## Questions for User

1. Should we integrate WikiaParser (option B) or enhance PageExtractor (option C)?
2. Is WikiaParser intended to be used, or was it experimental?
3. Should we prioritize fixing Tier 1 or investigating Tier 2 first?
4. Are there other projects besides avatar_test we should test with?

