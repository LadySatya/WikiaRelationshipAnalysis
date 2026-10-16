"""
Knowledge base validation and project status reports.

Reads a project's files (no LLM calls) and reports pipeline progress and
grounding problems: relationships without claims, quotes that are not on the
cited page, self-relationships, dangling character references, likely
duplicate characters, and partly read or unprocessed pages.
"""

import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

from .knowledge_builder import CharacterKnowledgeBuilder


def _load_json_files(directory: Path) -> List[Dict[str, Any]]:
    if not directory.exists():
        return []
    return [
        json.loads(f.read_text(encoding="utf-8"))
        for f in sorted(directory.glob("*.json"))
    ]


def _load_state(project_path: Path) -> Dict[str, Any]:
    state_file = project_path / "cache" / "discovery_state.json"
    if not state_file.exists():
        return {}
    return json.loads(state_file.read_text(encoding="utf-8"))


def _page_texts(project_path: Path) -> Dict[str, str]:
    """Normalized quotable text per crawled page URL (same rule as add_relationship)."""
    texts = {}
    for page in _load_json_files(project_path / "processed"):
        content = page.get("content", {})
        url = content.get("url") or page.get("url")
        if url:
            texts[url] = CharacterKnowledgeBuilder._quotable_text(content)
    return texts


def project_status(project_path: Path) -> Dict[str, Any]:
    """
    Summarize how far a project has got through the pipeline.

    Returns:
        Dict with pages_crawled, indexed, pages_discovered, partly_read_pages,
        characters, relationships
    """
    project_path = Path(project_path)

    def count(sub: str) -> int:
        directory = project_path / sub
        return len(list(directory.glob("*.json"))) if directory.exists() else 0

    state = _load_state(project_path)
    return {
        "pages_crawled": count("processed"),
        "indexed": (project_path / "chroma.sqlite3").exists(),
        "pages_discovered": len(state.get("processed_pages", {})),
        "partly_read_pages": len(state.get("partial_pages", {})),
        "characters": count("characters"),
        "relationships": count("relationships"),
    }


def validate_knowledge_base(project_path: Path) -> Dict[str, Any]:
    """
    Check a project's knowledge base for grounding and consistency problems.

    Returns:
        Dict with counts (characters, relationships, claims, evidence,
        characters_without_relationships), relationship_types, and issues -
        a dict containing only the problem categories that were found:
        relationships_without_claims, quotes_not_on_page,
        quotes_citing_uncrawled_pages, self_relationships,
        relationships_with_unknown_characters, possible_duplicate_characters,
        partly_read_pages, unprocessed_pages
    """
    project_path = Path(project_path)
    characters = _load_json_files(project_path / "characters")
    relationships = _load_json_files(project_path / "relationships")
    page_texts = _page_texts(project_path)
    state = _load_state(project_path)

    known = {(c.get("canon", "main"), c["name"]) for c in characters}
    related = set()
    issues: Dict[str, List[Any]] = {
        "relationships_without_claims": [],
        "quotes_not_on_page": [],
        "quotes_citing_uncrawled_pages": [],
        "self_relationships": [],
        "relationships_with_unknown_characters": [],
        "possible_duplicate_characters": [],
        "partly_read_pages": sorted(state.get("partial_pages", {})),
        "unprocessed_pages": sorted(
            set(page_texts) - set(state.get("processed_pages", {}))
        ),
    }

    claims = evidence = 0
    for rel in relationships:
        a, b = rel["characters"][0], rel["characters"][1]
        canon = rel.get("canon", "main")
        pair = [a, b, canon]
        related.update({(canon, a), (canon, b)})

        if a == b:
            issues["self_relationships"].append(pair)
        if (canon, a) not in known or (canon, b) not in known:
            issues["relationships_with_unknown_characters"].append(pair)
        if not rel.get("claims"):
            issues["relationships_without_claims"].append(pair)

        for claim in rel.get("claims", []):
            claims += 1
            for ev in claim.get("evidence", []):
                evidence += 1
                url = ev.get("evidence_url", "")
                entry = {
                    "characters": [a, b],
                    "claim": claim.get("claim"),
                    "evidence_url": url,
                    "evidence_text": ev.get("evidence_text"),
                }
                if url not in page_texts:
                    issues["quotes_citing_uncrawled_pages"].append(entry)
                elif (
                    CharacterKnowledgeBuilder._normalize_quote(
                        ev.get("evidence_text", "")
                    )
                    not in page_texts[url]
                ):
                    issues["quotes_not_on_page"].append(entry)

    # Likely duplicates: a character's name equals another's name (case-insensitive)
    # or one of its aliases, within the same canon
    by_key: Dict[Any, List[str]] = {}
    for c in characters:
        canon = c.get("canon", "main")
        for label in [c["name"], *c.get("aliases", [])]:
            by_key.setdefault((canon, label.strip().lower()), []).append(c["name"])
    duplicates = set()
    for (canon, _), names in by_key.items():
        unique = sorted(set(names))
        for i, first in enumerate(unique):
            for second in unique[i + 1 :]:
                duplicates.add((first, second, canon))
    issues["possible_duplicate_characters"] = [list(d) for d in sorted(duplicates)]

    return {
        "characters": len(characters),
        "relationships": len(relationships),
        "claims": claims,
        "evidence": evidence,
        "characters_without_relationships": len(known - related),
        "relationship_types": dict(
            Counter(rel.get("type", "unknown") for rel in relationships)
        ),
        "issues": {name: found for name, found in issues.items() if found},
    }
