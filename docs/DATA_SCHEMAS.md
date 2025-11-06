# WikiaAnalyzer Data Schemas Reference

This document defines all JSON data structures used throughout the WikiaAnalyzer system to prevent KeyError bugs and improve code maintainability.

---

## Table of Contents

1. [Crawler Schemas](#crawler-schemas)
2. [Processor Schemas](#processor-schemas)
3. [RAG Schemas](#rag-schemas)
4. [Character & Relationship Schemas](#character--relationship-schemas)
5. [LLM Tool Schemas](#llm-tool-schemas)

---

## Crawler Schemas

### Crawled Page Content

**File:** `data/projects/<project>/processed/<page>.json`

```json
{
  "url": "https://avatar.fandom.com/wiki/Aang",
  "saved_at": "2025-11-05T12:34:56Z",
  "content": {
    "url": "https://avatar.fandom.com/wiki/Aang",
    "title": "Aang | Avatar Wiki | Fandom",
    "main_content": "...",
    "links": ["https://...", "https://..."],
    "infobox_data": {...},
    "namespace": "Main",
    "is_disambiguation": false
  }
}
```

**Key Fields:**
- `url` (string): Page URL
- `saved_at` (ISO 8601 string): Timestamp
- `content.title` (string): Page title
- `content.main_content` (string): Extracted text
- `content.namespace` (string): Wikia namespace
- `content.is_disambiguation` (bool): Disambiguation page flag

---

## Processor Schemas

### Content Chunk (after chunking)

**Created by:** `ContentChunker`

```json
{
  "text": "Chunk of page content...",
  "metadata": {
    "url": "https://avatar.fandom.com/wiki/Aang",
    "title": "Aang | Avatar Wiki | Fandom",
    "chunk_index": 0,
    "total_chunks": 10,
    "char_start": 0,
    "char_end": 500,
    "namespace": "Main"
  }
}
```

**IMPORTANT:** Metadata uses `url` and `title` (NOT `source_url` or `page_title`)

**Key Fields:**
- `text` (string): Chunk content
- `metadata.url` (string): Source page URL
- `metadata.title` (string): Source page title
- `metadata.chunk_index` (int): Index in page
- `metadata.namespace` (string): Page namespace

### Embedded Chunk (with vector)

**Created by:** `EmbeddingGenerator.generate_embeddings()`

```json
{
  "text": "Chunk of page content...",
  "embedding": [0.123, -0.456, ...],  // numpy array or list
  "metadata": {
    "url": "https://avatar.fandom.com/wiki/Aang",
    "title": "Aang | Avatar Wiki | Fandom",
    "chunk_index": 0,
    "namespace": "Main"
  }
}
```

**Key Fields:**
- `embedding` (array): Vector embedding (384 or 1024 dimensions)
- All fields from Content Chunk

---

## RAG Schemas

### Vector Search Result

**Returned by:** `VectorStore.similarity_search()` and `RAGRetriever.retrieve()`

```json
{
  "id": "uuid-string",
  "text": "Chunk of page content...",
  "metadata": {
    "url": "https://avatar.fandom.com/wiki/Aang",
    "title": "Aang | Avatar Wiki | Fandom",
    "chunk_index": 0,
    "namespace": "Main"
  },
  "distance": 0.345  // Lower = more similar
}
```

**Key Fields:**
- `id` (string): Document UUID in ChromaDB
- `text` (string): Chunk content
- `metadata` (object): Same as Content Chunk metadata
- `distance` (float): Similarity score (0.0 = perfect match)

### Query with Citations Result

**Returned by:** `QueryEngine.query_with_citations()` and `LLMClient.query_with_citations()`

```json
{
  "text": "Generated answer from LLM",
  "evidence": [
    {
      "cited_text": "Exact quote from document",
      "document_index": 0,
      "location": {
        "start": 0,
        "end": 27
      },
      // Plus all metadata from the source chunk
      "url": "https://avatar.fandom.com/wiki/Aang",
      "title": "Aang | Avatar Wiki | Fandom",
      "chunk_index": 5
    }
  ]
}
```

**Key Fields:**
- `text` (string): LLM response
- `evidence` (array): Citations from Claude
- `evidence[].cited_text` (string): Quoted text
- `evidence[].url` (string): Source URL
- `evidence[].title` (string): Source page title

---

## Character & Relationship Schemas

### Discovered Character

**File:** `data/projects/<project>/characters/<character>.json`

```json
{
  "name": "Aang",
  "full_name": "Aang",
  "disambiguation": null,
  "name_variations": ["Aang", "Avatar Aang"],
  "discovered_via": ["metadata", "title_llm"],
  "source_url": "https://avatar.fandom.com/wiki/Aang",
  "source_page": {
    "url": "https://avatar.fandom.com/wiki/Aang",
    "title": "Aang | Avatar Wiki | Fandom",
    "main_content": "..."
  },
  "mentions": 45,
  "confidence": 0.92,
  "saved_at": "2025-11-05T14:30:00Z",
  "project_name": "avatar_wiki",

  // Added by ProfileBuilder after building profile
  "profile": {
    "relationships": [...],
    "total_relationships": 4,
    "tool_calls_made": 7,
    "profile_built_at": "2025-11-05T15:00:00Z"
  },
  "metadata": {
    "tool_usage": [...],
    "usage_stats": {...}
  }
}
```

**Key Fields:**
- `name` (string): Base name without disambiguation
- `full_name` (string): Display name with disambiguation
- `disambiguation` (string|null): Disambiguator text
- `source_url` (string): Primary wiki page
- `profile` (object): Added after ProfileBuilder runs
- `metadata` (object): LLM tool usage and stats

### Character Profile Relationship Entry

**In:** `<character>.json` → `profile.relationships[]`

```json
{
  "target": "Katara",
  "type": "romantic_partner",
  "summary": "Aang's primary love interest who becomes his wife",
  "narrative": {
    "claims": [
      "Aang developed a crush on Katara early",
      "They married after the war"
    ],
    "claims_with_evidence": [
      {
        "claim": "Aang developed a crush on Katara early",
        "confidence": 1.0,
        "evidence": [
          {
            "cited_text": "Katara and Aang, known as 'Kataang'...",
            "source_url": "https://avatar.fandom.com/wiki/Katara",
            "page_title": "Katara | Avatar Wiki | Fandom",
            "chunk_index": 22,
            "namespace": "Main",
            "relevance_score": 0.34
          }
        ]
      }
    ]
  },
  "confidence": 1.0,
  "evidence_count": 15,
  "verified_with": "verify_relationship"
}
```

**Key Fields:**
- `target` (string): Other character's name
- `type` (string): Relationship type
- `narrative.claims` (array): List of claim strings
- `narrative.claims_with_evidence` (array): Claims with citations
- `narrative.claims_with_evidence[].evidence` (array): Evidence entries

### Relationship Detail File

**File:** `data/projects/<project>/relationships/<char1>_<char2>.json`

```json
{
  "from": "Aang",
  "to": "Katara",
  "type": "romantic_partner",
  "summary": "Aang's primary love interest who becomes his wife",
  "narrative": {
    "claims": [...],
    "claims_with_evidence": [...]
  },
  "confidence": 1.0,
  "evidence_count": 15,
  "total_evidence_count": 15,
  "overall_confidence": 1.0,
  "built_at": "2025-11-05T22:53:19.662167Z"
}
```

**Key Fields:** Same as Character Profile Relationship Entry

### Relationship Graph (graph.json)

**File:** `data/projects/<project>/relationships/graph.json`

```json
{
  "nodes": [
    {
      "id": "Aang",
      "full_name": "Aang",
      "disambiguation": null,
      "source_url": "https://avatar.fandom.com/wiki/Aang",
      "total_relationships": 4
    }
  ],
  "edges": [
    {
      "from": "Aang",
      "to": "Katara",
      "type": "romantic_partner",
      "summary": "One-sentence description",
      "confidence": 1.0,
      "evidence_count": 15,
      "details_file": "Aang_Katara.json"
    }
  ],
  "metadata": {
    "project_name": "avatar_wiki",
    "total_characters": 5,
    "total_relationships": 19,
    "built_at": "2025-11-05T22:08:48Z"
  }
}
```

**Key Fields:**
- `nodes` (array): Character nodes
- `edges` (array): Relationship edges
- `edges[].details_file` (string): Filename for full details
- `metadata` (object): Graph statistics

---

## LLM Tool Schemas

### Tool Call (in LLM conversation)

**Stored in:** `<character>.json` → `metadata.tool_usage[]`

```json
{
  "tool": "verify_relationship",
  "input": {
    "character_a": "Aang",
    "character_b": "Katara"
  },
  "result": {
    "relationship_exists": true,
    "confidence": 1.0,
    "evidence_count": 15,
    "summary": "Brief description...",
    "evidence": [
      {
        "cited_text": "Quote from wiki...",
        "source_url": "https://avatar.fandom.com/wiki/Katara",
        "page_title": "Katara | Avatar Wiki | Fandom",
        "chunk_index": 22,
        "namespace": "Main",
        "relevance_score": 0.34
      }
    ]
  }
}
```

**CRITICAL:** Tool calls use `tool` and `input` (NOT `tool_name` and `params`)

**Key Fields:**
- `tool` (string): Tool name
- `input` (object): Tool parameters
- `result` (object): Tool return value

### Evidence Entry (in tool results)

**Returned by:** `RelationshipVerifyTool.execute()`

```json
{
  "cited_text": "First 300 chars of chunk...",
  "source_url": "https://avatar.fandom.com/wiki/Katara",
  "page_title": "Katara | Avatar Wiki | Fandom",
  "chunk_index": 22,
  "namespace": "Main",
  "relevance_score": 0.34
}
```

**IMPORTANT:** Uses `source_url` and `page_title` (even though metadata uses `url` and `title`)

**Key Fields:**
- `cited_text` (string): Text excerpt (max 300 chars)
- `source_url` (string): Wiki page URL
- `page_title` (string): Page title
- `chunk_index` (int): Chunk number in page
- `relevance_score` (float): Similarity score

---

## Schema Cheat Sheet

### Common KeyError Bugs

| **Context** | **WRONG Key** | **CORRECT Key** |
|-------------|---------------|-----------------|
| Tool calls | `tool_name` | `tool` |
| Tool calls | `params` | `input` |
| Chunk metadata | `source_url` | `url` |
| Chunk metadata | `page_title` | `title` |
| Evidence entries | `url` | `source_url` |
| Evidence entries | `title` | `page_title` |

### Quick Reference

```python
# Chunk metadata (from ContentChunker, VectorStore)
chunk["metadata"]["url"]       # ✅ Correct
chunk["metadata"]["title"]     # ✅ Correct

# Evidence entries (in tool results)
evidence["source_url"]         # ✅ Correct
evidence["page_title"]         # ✅ Correct

# Tool calls (in tool_usage)
call["tool"]                   # ✅ Correct
call["input"]                  # ✅ Correct

# Character entries
character["source_url"]        # ✅ Correct (primary page)
```

---

## Version History

- **2025-11-05**: Initial schema documentation
- Fixed evidence extraction bugs by documenting metadata key differences

---

## Contributing

When adding new data structures:
1. Add schema definition here
2. Include example JSON
3. List key fields with types
4. Note any naming inconsistencies
5. Update cheat sheet if needed
