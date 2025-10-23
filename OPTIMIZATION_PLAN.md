# CharacterExtractor Optimization Plan

## Current State

- **5 LLM calls** for discovery (all asking "list characters" in different ways)
- **70-90% overlap** in results between queries
- **No early termination** - always runs all 5 queries
- **High chunk retrieval** - k=15 per query = 75 total retrievals

## Proposed Optimizations

### Priority 1: Reduce Discovery Queries (80% Cost Savings)

**Current Approach:**
```python
queries = [
    "List all major characters...",
    "What characters appear in main storylines...",
    "Who are the protagonists, antagonists...",
    "List characters by affiliations...",
    "What characters have relationships..."
]
# Total: 5 LLM calls
```

**Optimized Approach:**
```python
# OPTION A: Single comprehensive query
query = """List ALL characters mentioned in this wiki, including:
- Main protagonists and antagonists
- Supporting characters
- Characters in major storylines
- Characters with significant relationships
- Characters mentioned in affiliations/factions

Return ONLY character names, one per line."""

# Total: 1 LLM call (80% cost reduction)
```

**OPTION B: Two-stage discovery (90% accuracy, 60% cost reduction)**
```python
# Stage 1: Broad discovery (1 LLM call)
primary_query = "List all characters mentioned in this wiki..."

# Stage 2: Only if needed - gap filling (conditional)
if len(discovered_characters) < min_expected_characters:
    secondary_query = "List any minor or supporting characters not yet mentioned..."

# Total: 1-2 LLM calls (vs 5)
```

**Tradeoffs:**
- ✅ Pro: 60-80% cost reduction
- ✅ Pro: Faster execution
- ⚠️ Con: Might miss 5-10% of characters found by multi-query approach
- ✅ Mitigation: Use higher k value for single query (k=25 vs k=15)

---

### Priority 2: Early Termination (20% Cost Savings)

**Implementation:**
```python
def _execute_discovery_queries(self, max_characters: Optional[int] = None) -> List[Dict[str, Any]]:
    queries = self._get_discovery_queries()
    all_characters = []
    unique_names = set()

    for i, query in enumerate(queries):
        # Early termination check
        if max_characters and len(unique_names) >= max_characters * 1.5:
            print(f"[INFO] Early termination: found {len(unique_names)} unique names (target: {max_characters})")
            break

        # Execute query...
        character_names = self._parse_character_names(response)

        for name in character_names:
            if name not in unique_names:
                all_characters.append({"name": name, "discovered_via": [query_id]})
                unique_names.add(name)

    return all_characters
```

**Benefits:**
- Stops after query #2 if we found 30+ characters (target: 20)
- Saves 3 LLM calls in that scenario

---

### Priority 3: Optimize Chunk Retrieval (Memory Efficiency)

**Current:**
- 5 queries × k=15 = 75 chunk retrievals
- Many duplicate retrievals

**Option A: Shared Chunk Pool**
```python
def _execute_discovery_queries_with_cache(self) -> List[Dict[str, Any]]:
    # Retrieve chunks once, use for all queries
    shared_chunks = self.query_engine.retriever.retrieve(
        query="Characters and storylines in this wiki",
        k=50  # Higher k, but only retrieved once
    )

    # Build context from shared chunks
    shared_context = self.query_engine.retriever.build_context(shared_chunks)

    # Ask LLM comprehensive question with ALL context
    response = self.query_engine.llm_client.generate(
        prompt=f"{shared_context}\n\nList all characters mentioned above.",
        system_prompt=self.DISCOVERY_SYSTEM_PROMPT
    )

    return self._parse_character_names(response)
```

**Benefits:**
- Only 1 vector search + 1 LLM call
- Uses more context per call (better recall)

**Tradeoff:**
- Higher token count per LLM call
- But total cost still much lower (1 call vs 5)

---

### Priority 4: Validation Batching (Minor Improvement)

**Current:**
```python
for char in characters:  # 20 characters
    chunks = self.query_engine.retriever.retrieve(query=f"Information about {name}", k=50)
```

**Optimized:**
```python
# Batch validation using cached results
all_validation_queries = [f"Information about {char['name']}" for char in characters]

# Could potentially batch, but ChromaDB already efficient at single queries
# This is vector search, not LLM calls, so lower priority
```

**Note:** Vector search is cheap compared to LLM calls. Focus on LLM optimization first.

---

## Recommended Implementation Order

### Phase 1: Quick Wins (Implement Now)
1. ✅ **Reduce to 1-2 discovery queries** (80% cost savings)
2. ✅ **Add early termination** (20% savings when applicable)
3. ✅ **Adjust k values** based on corpus size

### Phase 2: Advanced (Later)
4. ⏸️ **Shared chunk pool** (memory optimization)
5. ⏸️ **Validation batching** (minor improvement)

---

## Cost Comparison

**Scenario:** Discovering 20 characters from avatar_test (5 pages, ~50 chunks)

### Current Implementation:
```
Discovery: 5 queries × 15 chunks × 250 tokens = ~18,750 input tokens
           5 responses × 50 tokens = ~250 output tokens
           Cost: $0.019 input + $0.001 output = $0.020

Validation: 20 vector searches (free)

Total: $0.020
```

### Optimized Implementation (1 query):
```
Discovery: 1 query × 25 chunks × 350 tokens = ~8,750 input tokens
           1 response × 60 tokens = ~60 output tokens
           Cost: $0.009 input + $0.0003 output = $0.0093

Validation: 20 vector searches (free)

Total: $0.0093 (53% cost reduction)
```

### Optimized with Shared Chunk Pool:
```
Discovery: 1 vector search + 1 LLM call
           50 chunks × 400 tokens = ~20,000 input tokens
           1 response × 80 tokens = ~80 output tokens
           Cost: $0.020 input + $0.0004 output = $0.0204

Total: $0.0204 (same cost, but 90% fewer operations)
```

---

## Testing Strategy

1. **Implement single-query approach**
2. **Test on avatar_test** (5 pages, known characters)
3. **Compare results:**
   - Current: How many characters discovered?
   - Optimized: How many characters discovered?
   - Delta: Characters missed (should be < 10%)
4. **If delta > 10%:** Fall back to 2-query approach
5. **If delta < 10%:** Ship optimized version

---

## Configuration

Add to `config/processor_config.yaml`:

```yaml
processor:
  character_discovery:
    # Discovery strategy
    discovery_mode: "single_query"  # Options: single_query | dual_query | multi_query (legacy)
    primary_query_k: 25             # Chunks for primary query (increased from 15)
    enable_early_termination: true
    early_termination_threshold: 1.5  # Stop if found 1.5x target characters

    # Validation settings (unchanged)
    min_mentions: 3
    confidence_threshold: 0.7
```

---

## Implementation Checklist

- [ ] Add `discovery_mode` config option
- [ ] Implement `_execute_single_query_discovery()`
- [ ] Implement early termination logic
- [ ] Add tests for optimized discovery
- [ ] Update fixtures for single-query responses
- [ ] Benchmark cost comparison
- [ ] Update documentation

---

## Risk Assessment

**Low Risk:**
- ✅ Single query approach is simpler and faster
- ✅ Easy to A/B test against multi-query
- ✅ Can fall back to multi-query if needed
- ✅ Mocking system allows cost-free testing

**Mitigation:**
- Keep multi-query implementation as fallback
- Add config flag to switch between modes
- Test thoroughly on multiple wikia projects
