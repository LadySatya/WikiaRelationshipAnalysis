"""
Tests for knowledge base validation and project status reports.

These read a project's files (no LLM) and report grounding problems and
pipeline progress for `main.py validate` and `main.py status`.
"""

import json

import pytest

from src.processor.analysis.kb_validation import (
    project_status,
    validate_knowledge_base,
)

pytestmark = pytest.mark.unit

URL = "https://avatar.fandom.com/wiki/Aang"


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


@pytest.fixture
def project(tmp_path):
    """Small project: one crawled page, three characters, two relationships."""
    p = tmp_path / "avatar_wiki"
    write(
        p / "processed" / "Aang_20261015.json",
        {
            "url": URL,
            "content": {
                "url": URL,
                "title": "Aang",
                "main_content": "Aang married Katara after the war. Sokka is Katara's brother.",
                "infobox_data": {"Enemies": "Azula,Ozai"},
            },
        },
    )
    for name, aliases in (("Aang", ["Avatar Aang"]), ("Katara", []), ("Sokka", [])):
        write(
            p / "characters" / f"{name}_main.json",
            {"name": name, "canon": "main", "aliases": aliases, "source_urls": [URL]},
        )
    write(
        p / "relationships" / "Aang_Katara_main.json",
        {
            "characters": ["Aang", "Katara"],
            "canon": "main",
            "type": "romantic_partner",
            "claims": [
                {
                    "claim": "Aang married Katara",
                    "evidence": [
                        {
                            "evidence_url": URL,
                            "evidence_text": "Aang married Katara after the war",
                        }
                    ],
                }
            ],
        },
    )
    write(
        p / "relationships" / "Katara_Sokka_main.json",
        {
            "characters": ["Katara", "Sokka"],
            "canon": "main",
            "type": "family",
            "claims": [
                {
                    "claim": "siblings",
                    "evidence": [
                        {
                            "evidence_url": URL,
                            "evidence_text": "Sokka is Katara's brother",
                        }
                    ],
                }
            ],
        },
    )
    write(
        p / "cache" / "discovery_state.json",
        {"processed_pages": {URL: "t"}, "partial_pages": {}},
    )
    return p


def add_relationship(project, a, b, claims, rtype="friend"):
    write(
        project / "relationships" / f"{a}_{b}_main.json",
        {"characters": [a, b], "canon": "main", "type": rtype, "claims": claims},
    )


class TestValidateCleanProject:
    def test_counts(self, project):
        report = validate_knowledge_base(project)

        assert report["characters"] == 3
        assert report["relationships"] == 2
        assert report["claims"] == 2
        assert report["evidence"] == 2
        assert report["relationship_types"] == {"romantic_partner": 1, "family": 1}

    def test_no_issues(self, project):
        report = validate_knowledge_base(project)

        assert report["issues"] == {}

    def test_missing_directories_report_zero(self, tmp_path):
        report = validate_knowledge_base(tmp_path / "empty")

        assert report["characters"] == 0
        assert report["relationships"] == 0


class TestValidateFindsIssues:
    def test_relationship_without_claims(self, project):
        add_relationship(project, "Aang", "Sokka", [])

        issues = validate_knowledge_base(project)["issues"]

        assert issues["relationships_without_claims"] == [["Aang", "Sokka", "main"]]

    def test_quote_not_on_cited_page(self, project):
        add_relationship(
            project,
            "Aang",
            "Sokka",
            [
                {
                    "claim": "x",
                    "evidence": [{"evidence_url": URL, "evidence_text": "made up"}],
                }
            ],
        )

        issues = validate_knowledge_base(project)["issues"]

        assert issues["quotes_not_on_page"][0]["characters"] == ["Aang", "Sokka"]

    def test_quote_matching_ignores_case_whitespace_and_uses_infobox(self, project):
        add_relationship(
            project,
            "Aang",
            "Sokka",
            [
                {
                    "claim": "x",
                    "evidence": [
                        {"evidence_url": URL, "evidence_text": "ENEMIES:  Azula, Ozai"}
                    ],
                }
            ],
        )

        assert "quotes_not_on_page" not in validate_knowledge_base(project)["issues"]

    def test_quote_citing_unknown_page(self, project):
        add_relationship(
            project,
            "Aang",
            "Sokka",
            [
                {
                    "claim": "x",
                    "evidence": [
                        {"evidence_url": "https://other/wiki/X", "evidence_text": "a"}
                    ],
                }
            ],
        )

        issues = validate_knowledge_base(project)["issues"]

        assert len(issues["quotes_citing_uncrawled_pages"]) == 1

    def test_self_relationship(self, project):
        add_relationship(project, "Aang", "Aang", [])

        issues = validate_knowledge_base(project)["issues"]

        assert ["Aang", "Aang", "main"] in issues["self_relationships"]

    def test_relationship_with_unknown_character(self, project):
        add_relationship(project, "Aang", "Zuko", [])

        issues = validate_knowledge_base(project)["issues"]

        assert issues["relationships_with_unknown_characters"] == [
            ["Aang", "Zuko", "main"]
        ]

    def test_possible_duplicate_characters(self, project):
        write(
            project / "characters" / "Avatar_Aang_main.json",
            {"name": "Avatar Aang", "canon": "main", "aliases": []},
        )

        issues = validate_knowledge_base(project)["issues"]

        assert issues["possible_duplicate_characters"] == [
            ["Aang", "Avatar Aang", "main"]
        ]

    def test_partial_and_unprocessed_pages(self, project):
        write(
            project / "processed" / "Zuko_20261015.json",
            {
                "url": "https://avatar.fandom.com/wiki/Zuko",
                "content": {"main_content": "z"},
            },
        )
        write(
            project / "cache" / "discovery_state.json",
            {
                "processed_pages": {URL: "t"},
                "partial_pages": {URL: {"windows_processed": 2, "windows_total": 3}},
            },
        )

        issues = validate_knowledge_base(project)["issues"]

        assert issues["partly_read_pages"] == [URL]
        assert issues["unprocessed_pages"] == ["https://avatar.fandom.com/wiki/Zuko"]

    def test_characters_without_relationships_are_counted(self, project):
        write(
            project / "characters" / "Momo_main.json",
            {"name": "Momo", "canon": "main", "aliases": []},
        )

        report = validate_knowledge_base(project)

        assert report["characters_without_relationships"] == 1


class TestProjectStatus:
    def test_reports_each_stage(self, project):
        (project / "chroma.sqlite3").write_text("")

        status = project_status(project)

        assert status == {
            "pages_crawled": 1,
            "indexed": True,
            "pages_discovered": 1,
            "partly_read_pages": 0,
            "characters": 3,
            "relationships": 2,
        }

    def test_not_indexed_without_chroma_db(self, project):
        assert project_status(project)["indexed"] is False

    def test_empty_project(self, tmp_path):
        status = project_status(tmp_path / "new")

        assert status["pages_crawled"] == 0
        assert status["pages_discovered"] == 0
        assert status["characters"] == 0
