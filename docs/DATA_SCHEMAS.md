# Data Schemas

Reference for every JSON structure the pipeline reads or writes. Consult this before writing code that touches these structures - most bugs in this project have been wrong field names.

Examples are trimmed from real files produced by the current code (`data/projects/avatar_wiki/`, October 2026).

## Contents

- [Cheat Sheet](#cheat-sheet) - the field names people get wrong
- [Crawled Page](#crawled-page) - `processed/*.json`
- [RAG Structures](#rag-structures) - chunks, search results, citations
- [Knowledge Base Files](#knowledge-base-files) - characters, relationships, state
- [Discovery Tools](#discovery-tools) - tool inputs and results
- [LLM Logs](#llm-logs) - `prompts.jsonl`, `tool_calls.jsonl`
- [Known Issues](#known-issues)

---

## Cheat Sheet

| Structure | Use | NOT |
|---|---|---|
| Relationship evidence (knowledge base) | `evidence_url`, `evidence_text`, `added_at` | `source_url`, `page_title`, `url`, `quote` |
| Citation evidence (`query_with_citations`) | `cited_text`, `url`, `title` (copied from chunk metadata) | `page_title`, `source_url` |
| Chunk metadata | `url`, `title` | `source_url`, `page_title` |
| Tool calls returned by `generate_with_tools` | `tool`, `input`, `result` | `tool_name`, `params` |
| Tool calls in `logs/llm/tool_calls.jsonl` | `tool_name`, `input`, `result_summary` | `tool` |
| Character sources | `source_urls` (list) | `source_url` |
| Relationship characters | `characters` (list of 2, sorted) | `from` / `to` |
| Relationship type | `type` (in the file); `relationship_type` (tool input) | - |

Knowledge base dictionaries in memory are nested by canon:
`kb["characters"][canon][name]` and `kb["relationships"][canon][(char_a, char_b)]` (tuple key, sorted). Iterate canons first - `len(kb["characters"])` counts canons, not characters.

---

## Crawled Page

**File:** `data/projects/<project>/processed/<CleanTitle>_<YYYYMMDD>.json` (fallback `page_<hash>_<YYYYMMDD>.json`)
**Written by:** `ContentSaver.save_page_content()` (`src/crawler/persistence/content_saver.py`); content from `PageExtractor.extract_content()` (`src/crawler/extraction/page_extractor.py`)

```json
{
  "url": "https://avatar.fandom.com/wiki/Aang",
  "saved_at": "2026-10-15T20:46:25.608825",
  "content": {
    "url": "https://avatar.fandom.com/wiki/Aang",
    "title": "Aang | Avatar Wiki | Fandom",
    "main_content": "This article is about the character in the animated series. ...",
    "links": ["https://avatar.fandom.com/wiki/Imprisoned", "https://avatar.fandom.com/wiki/Fire_Lord"],
    "infobox_data": {
      "Allies": "Team Avatar,Iroh,KingBumi,Gyatso,Hakoda, ...",
      "Enemies": "Azula,Ozai,Zhao,Combustion Man, ..."
    },
    "is_disambiguation": true,
    "namespace": "Main"
  }
}
```

- `saved_at` is local time without a `Z`.
- `main_content` is a single line: paragraph breaks are not preserved.
- `infobox_data` values have the spaces between linked words removed ("KingBumi"). Evidence matching ignores whitespace, so quotes still match.
- There is no `categories` field (the extractor does not collect categories).

---

## RAG Structures

### Content Chunk
**Produced by:** `ContentChunker` (`src/processor/core/content_chunker.py`)

```json
{
  "text": "Aang was born to two Air Nomads in 12 BG. ...",
  "metadata": {
    "url": "https://avatar.fandom.com/wiki/Aang",
    "title": "Aang | Avatar Wiki | Fandom",
    "chunk_index": 0,
    "total_chunks": 277,
    "char_start": 0,
    "char_end": 498,
    "namespace": "Main"
  }
}
```

`namespace` is only present when the page has one. ChromaDB metadata values must be `str`, `int`, `float`, `bool` or `None`.

### Embedded Chunk
**Produced by:** `EmbeddingGenerator.embed_chunks()` (`src/processor/rag/embeddings.py`) - a content chunk plus `"embedding": np.ndarray`. The dimension depends on the model (384 for the default local `all-MiniLM-L6-v2`). `generate_embeddings()` returns plain `List[np.ndarray]`, not chunk dicts.

### Vector Search Result
**Returned by:** `VectorStore.similarity_search()` and `RAGRetriever.retrieve()`

```json
{"id": "uuid", "text": "...", "metadata": {"url": "...", "title": "...", "chunk_index": 3, "...": "..."}, "distance": 0.42}
```

### Query with Citations Result
**Returned by:** `LLMClient.query_with_citations()` / `QueryEngine.query_with_citations()`

```json
{
  "text": "Generated answer...",
  "evidence": [
    {
      "cited_text": "Exact text from the chunk",
      "document_index": 0,
      "location": {"start": 0, "end": 27},
      "url": "https://avatar.fandom.com/wiki/Aang",
      "title": "Aang | Avatar Wiki | Fandom",
      "chunk_index": 3
    }
  ]
}
```

Each evidence entry includes all of the cited chunk's metadata. `location` may be `null`. (`QueryEngine.query_detailed()` returns a different shape: `{query, answer, sources: [{text, url, distance}], usage, evidence?}`.)

---

## Knowledge Base Files

Written by `CharacterKnowledgeBuilder.save()` (`src/processor/analysis/knowledge_builder.py`). Filenames replace spaces and `\ / : * ? " < > |` with `_`.

### Character
**File:** `characters/<name>_<canon>.json`

```json
{
  "name": "Aang",
  "canon": "main",
  "aliases": ["Avatar Aang", "Kuzon"],
  "bio": "Aang is the Air Nomad Avatar who succeeded Avatar Roku and preceded Avatar Korra. ...",
  "source_urls": ["https://avatar.fandom.com/wiki/Earth_Rumble", "https://avatar.fandom.com/wiki/Aang"],
  "created_at": "2026-10-15T22:11:59.817388Z",
  "updated_at": "2026-10-15T22:38:25.246026Z",
  "affiliations": [
    {
      "group": "Air Acolytes",
      "role": "Founder",
      "evidence_url": "https://avatar.fandom.com/wiki/Aang",
      "evidence_text": "Aang reorganized the Official Avatar Aang Fan Club as the first Air Acolytes ."
    }
  ]
}
```

`updated_at` and `affiliations` are optional. Affiliation `role` is optional; groups are matched case-insensitively. Affiliation evidence is **not** verified against the page (only relationship evidence is).

### Relationship
**File:** `relationships/<char_a>_<char_b>_<canon>.json` (characters sorted alphabetically)

```json
{
  "characters": ["Aang", "Appa"],
  "canon": "main",
  "type": "friend",
  "summary": "Aang and Appa share a deep and lifelong friendship that began when Aang offered Appa an apple.",
  "claims": [
    {
      "claim": "Aang's attitude changed dramatically when Appa was captured",
      "evidence": [
        {
          "evidence_url": "https://avatar.fandom.com/wiki/Aang",
          "evidence_text": "Aang's attitude changed dramatically when Appa was captured.",
          "added_at": "2026-10-15T22:20:30.032321Z"
        }
      ]
    }
  ],
  "created_at": "2026-10-15T22:15:31.882109Z",
  "updated_at": "2026-10-15T22:29:17.923883Z"
}
```

- Since the `add_relationship` tool, every relationship has at least one claim, and every `evidence_text` has been verified to appear (ignoring case and whitespace) on `evidence_url`'s page or in its infobox.
- `evidence_text` is stored truncated to 200 characters (still an exact quote).
- `type` is free text from the model; observed values: `enemy`, `family`, `friend`, `complicated`, `mentor`, `ally`, `professional`, `romantic_partner`.

### Discovery State
**File:** `cache/discovery_state.json` - used to resume `discover`

```json
{
  "processed_pages": {
    "https://avatar.fandom.com/wiki/Terra_Team": "2026-10-15T22:11:50.998986Z"
  },
  "partial_pages": {
    "https://example.fandom.com/wiki/Huge_Page": {"windows_processed": 25, "windows_total": 31}
  },
  "last_saved": "2026-10-15T22:46:00.106734Z",
  "total_processed": 20
}
```

A page is added to `processed_pages` only after all its windows succeed. `partial_pages` lists pages that hit `max_windows_per_page` and were only partly read.

### Knowledge Base Metadata
**File:** `knowledge_base_metadata.json`

```json
{
  "project_name": "avatar_wiki",
  "created_at": "2026-10-15T22:11:34.698816Z",
  "pages_processed": 20,
  "last_updated": "2026-10-15T22:45:59.914307Z",
  "canons": ["main"]
}
```

---

## Discovery Tools

The tools Claude calls during `discover`. Definitions sent to the model: `config/llm_tools/schemas/knowledge_building/*.json`. Executors: `_execute_kb_tool()` and the `_tool_*` methods in `knowledge_builder.py`. Failures are returned to the model as `{"error": "...", "success": false}` rather than raised.

| Tool | Input (`?` = optional) | Result |
|---|---|---|
| `determine_canon` | `canon, reasoning` | `{success, canon, message}` |
| `search_characters` | `query, canon?` | `{matches: [{name, canon, aliases, similarity}], count}` |
| `create_character` | `name, canon, source_url, aliases?, bio?` | `{success, existed, name, canon, character?}` - returns the existing record if the name exists |
| `update_character` | `name, canon, add_aliases?, bio?, add_source_url?` | `{success, name, canon, aliases, source_url_count}` |
| `get_character` | `name, canon` | character record or `null` |
| `add_relationship` | `character_a, character_b, canon, relationship_type, claim, evidence_url, evidence_text, summary?` | see below |
| `get_relationship` | `character_a, character_b, canon` | relationship record or `null` |
| `add_affiliation` | `character_name, canon, group, evidence_url, evidence_text, role?` | `{success, character_name, canon, current_affiliations: [{group, role}], affiliation_count, message?}` |
| `search_wiki` | `query, max_results?` | `{results: [{text, url, page_title}], count, answer_summary}` |

**`add_relationship` result** (creates the relationship with this claim, or adds the claim to an existing one):

```json
{
  "success": true,
  "created": false,
  "characters": ["Aang", "Katara"],
  "canon": "main",
  "type": "romantic_partner",
  "summary": "Aang and Katara married.",
  "claims": ["Aang married Katara", "Aang and Katara had three children"],
  "updated_claim": {"claim": "Aang and Katara had three children", "evidence": [{"evidence_url": "...", "evidence_text": "...", "added_at": "..."}]},
  "note": "Relationship already existed with type 'romantic_partner'; type and summary were kept and your claim was added."
}
```

Errors: a missing character returns `{error, success: false, suggestions: {name: [close names]}, hint}`; a quote not found on the page returns `{error, success: false}` and nothing is stored.

**`generate_with_tools` return value** (`src/processor/llm/llm_client.py`):

```json
{
  "final_response": "...",
  "tool_calls": [{"tool": "search_characters", "input": {"query": "Aang"}, "result": {"matches": [], "count": 0}}],
  "usage": {
    "total_input_tokens": 210, "total_output_tokens": 5400,
    "total_cache_read_tokens": 41000, "total_cache_write_tokens": 9000,
    "estimated_cost_usd": 0.0049, "iterations": 5
  }
}
```

---

## LLM Logs

### `logs/llm/prompts.jsonl`
One line per logged LLM call (`LLMLogger.log_prompt()`, `src/utils/logging_config.py`):

```json
{"timestamp": "...", "model": "claude-haiku-5-5", "purpose": "knowledge_building:Aang | Avatar Wiki | Fandom [part 3/18]",
 "prompt_length": 7400, "prompt_preview": "...", "response_length": 120, "response_preview": "...",
 "usage": {"input_tokens": 12, "output_tokens": 5400, "cache_read_input_tokens": 41000, "cache_creation_input_tokens": 9000},
 "cost_usd": 0.0049, "error": null,
 "metadata": {"page_title": "...", "page_url": "...", "window_index": 3, "window_count": 18, "tool_calls_made": 21, "iterations": 5, "estimated_cost": 0.0049}}
```

### `logs/llm/tool_calls.jsonl`
One line per tool call: `{timestamp, tool_name, input, result_summary, error, execution_time_ms}`. `result_summary` is a string (Python repr, up to 500 characters). `execution_time_ms` is currently always `null`.

---

## Known Issues

- **Every discovery LLM call is logged twice** in `prompts.jsonl` (once as `tool_based_generation`, once as `knowledge_building:...`). Summing `cost_usd` over the file double-counts; filter on `purpose` starting with `knowledge_building:`.
- **`search_wiki` results always have an empty `page_title`**: `knowledge_builder.py` reads `evidence["page_title"]` but citation evidence uses `title`.
- **`knowledge_base_metadata.json` `pages_processed`** is the loop index, which includes skipped (already processed) pages.
- **`is_disambiguation`** can be a false positive (the Aang page is flagged because of a "see Aang (disambiguation)" note).
- **No `graph.json` is produced.** The visualizer builds the graph in the browser from the relationship files. `validate` and the `status` command still look for `graph.json`.
