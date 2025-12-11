"""
Tests for Flask visualization server utilities and API endpoints.

Tests cover:
- Canon extraction utilities
- Project listing functions
- API endpoints for characters and relationships
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


class TestExtractCanonFromFilename:
    """Test canon extraction from filenames."""

    def test_extract_main_canon(self):
        """Should extract 'main' canon from filename."""
        from src.visualizer.server import extract_canon_from_filename

        assert extract_canon_from_filename("Aang_main.json") == "main"

    def test_extract_film_canon(self):
        """Should extract 'film' canon from filename."""
        from src.visualizer.server import extract_canon_from_filename

        assert extract_canon_from_filename("Katara_film.json") == "film"

    def test_extract_netflix_canon(self):
        """Should extract 'netflix' canon from filename."""
        from src.visualizer.server import extract_canon_from_filename

        assert extract_canon_from_filename("Sokka_netflix.json") == "netflix"

    def test_extract_legends_canon(self):
        """Should extract 'legends' canon from filename."""
        from src.visualizer.server import extract_canon_from_filename

        assert extract_canon_from_filename("Character_legends.json") == "legends"

    def test_extract_comics_canon(self):
        """Should extract 'comics' canon from filename."""
        from src.visualizer.server import extract_canon_from_filename

        assert extract_canon_from_filename("Hero_comics.json") == "comics"

    def test_extract_games_canon(self):
        """Should extract 'games' canon from filename."""
        from src.visualizer.server import extract_canon_from_filename

        assert extract_canon_from_filename("Player_games.json") == "games"

    def test_no_underscore_defaults_to_main(self):
        """Should default to 'main' if no underscore in filename."""
        from src.visualizer.server import extract_canon_from_filename

        assert extract_canon_from_filename("Aang.json") == "main"

    def test_unknown_suffix_defaults_to_main(self):
        """Should default to 'main' if suffix is not a known canon."""
        from src.visualizer.server import extract_canon_from_filename

        assert extract_canon_from_filename("Character_unknown.json") == "main"

    def test_multiple_underscores_uses_last(self):
        """Should use the last underscore for canon detection."""
        from src.visualizer.server import extract_canon_from_filename

        assert extract_canon_from_filename("Fire_Lord_Ozai_film.json") == "film"

    def test_handles_no_extension(self):
        """Should handle filenames without .json extension."""
        from src.visualizer.server import extract_canon_from_filename

        assert extract_canon_from_filename("Aang_main") == "main"

    def test_case_insensitive_canon(self):
        """Canon detection should be case-insensitive."""
        from src.visualizer.server import extract_canon_from_filename

        assert extract_canon_from_filename("Aang_MAIN.json") == "main"
        assert extract_canon_from_filename("Aang_Film.json") == "film"


class TestGetProjectCanons:
    """Test project canon listing."""

    def test_empty_project_returns_empty_list(self, tmp_path):
        """Should return empty list for project with no characters or relationships."""
        from src.visualizer.server import get_project_canons

        project_dir = tmp_path / "empty_project"
        project_dir.mkdir()

        with patch("src.visualizer.server.PROJECT_DIR", tmp_path):
            canons = get_project_canons("empty_project")

        assert canons == []

    def test_counts_characters_per_canon(self, tmp_path):
        """Should count characters per canon correctly."""
        from src.visualizer.server import get_project_canons

        project_dir = tmp_path / "test_project"
        chars_dir = project_dir / "characters"
        chars_dir.mkdir(parents=True)

        # Create character files
        (chars_dir / "Aang_main.json").write_text("{}")
        (chars_dir / "Katara_main.json").write_text("{}")
        (chars_dir / "Aang_film.json").write_text("{}")

        with patch("src.visualizer.server.PROJECT_DIR", tmp_path):
            canons = get_project_canons("test_project")

        main_canon = next((c for c in canons if c["id"] == "main"), None)
        film_canon = next((c for c in canons if c["id"] == "film"), None)

        assert main_canon["character_count"] == 2
        assert film_canon["character_count"] == 1

    def test_counts_relationships_per_canon(self, tmp_path):
        """Should count relationships per canon correctly."""
        from src.visualizer.server import get_project_canons

        project_dir = tmp_path / "test_project"
        rels_dir = project_dir / "relationships"
        rels_dir.mkdir(parents=True)

        # Create relationship files
        (rels_dir / "Aang_Katara_main.json").write_text("{}")
        (rels_dir / "Aang_Sokka_main.json").write_text("{}")
        (rels_dir / "Aang_Katara_film.json").write_text("{}")

        with patch("src.visualizer.server.PROJECT_DIR", tmp_path):
            canons = get_project_canons("test_project")

        main_canon = next((c for c in canons if c["id"] == "main"), None)
        assert main_canon["relationship_count"] == 2

    def test_excludes_graph_json(self, tmp_path):
        """Should exclude legacy graph.json from relationship counts."""
        from src.visualizer.server import get_project_canons

        project_dir = tmp_path / "test_project"
        rels_dir = project_dir / "relationships"
        rels_dir.mkdir(parents=True)

        (rels_dir / "Aang_Katara_main.json").write_text("{}")
        (rels_dir / "graph.json").write_text("{}")  # Legacy file, should be excluded

        with patch("src.visualizer.server.PROJECT_DIR", tmp_path):
            canons = get_project_canons("test_project")

        main_canon = next((c for c in canons if c["id"] == "main"), None)
        assert main_canon["relationship_count"] == 1

    def test_excludes_underscore_prefixed_files(self, tmp_path):
        """Should exclude internal files starting with underscore."""
        from src.visualizer.server import get_project_canons

        project_dir = tmp_path / "test_project"
        chars_dir = project_dir / "characters"
        chars_dir.mkdir(parents=True)

        (chars_dir / "Aang_main.json").write_text("{}")
        (chars_dir / "_metadata.json").write_text("{}")  # Internal file

        with patch("src.visualizer.server.PROJECT_DIR", tmp_path):
            canons = get_project_canons("test_project")

        main_canon = next((c for c in canons if c["id"] == "main"), None)
        assert main_canon["character_count"] == 1

    def test_returns_sorted_canons(self, tmp_path):
        """Should return canons sorted alphabetically by id."""
        from src.visualizer.server import get_project_canons

        project_dir = tmp_path / "test_project"
        chars_dir = project_dir / "characters"
        chars_dir.mkdir(parents=True)

        (chars_dir / "A_netflix.json").write_text("{}")
        (chars_dir / "B_film.json").write_text("{}")
        (chars_dir / "C_main.json").write_text("{}")

        with patch("src.visualizer.server.PROJECT_DIR", tmp_path):
            canons = get_project_canons("test_project")

        canon_ids = [c["id"] for c in canons]
        assert canon_ids == sorted(canon_ids)

    def test_canon_name_is_titlecased(self, tmp_path):
        """Canon name should be titlecased version of id."""
        from src.visualizer.server import get_project_canons

        project_dir = tmp_path / "test_project"
        chars_dir = project_dir / "characters"
        chars_dir.mkdir(parents=True)

        (chars_dir / "Aang_main.json").write_text("{}")

        with patch("src.visualizer.server.PROJECT_DIR", tmp_path):
            canons = get_project_canons("test_project")

        assert canons[0]["name"] == "Main"


class TestGetAllProjects:
    """Test project listing function."""

    def test_empty_directory_returns_empty_list(self, tmp_path):
        """Should return empty list if no projects exist."""
        from src.visualizer.server import get_all_projects

        with patch("src.visualizer.server.PROJECT_DIR", tmp_path):
            projects = get_all_projects()

        assert projects == []

    def test_nonexistent_directory_returns_empty_list(self, tmp_path):
        """Should return empty list if PROJECT_DIR doesn't exist."""
        from src.visualizer.server import get_all_projects

        fake_path = tmp_path / "nonexistent"

        with patch("src.visualizer.server.PROJECT_DIR", fake_path):
            projects = get_all_projects()

        assert projects == []

    def test_counts_characters_and_relationships(self, tmp_path):
        """Should count character and relationship files."""
        from src.visualizer.server import get_all_projects

        project_dir = tmp_path / "test_project"
        chars_dir = project_dir / "characters"
        rels_dir = project_dir / "relationships"
        chars_dir.mkdir(parents=True)
        rels_dir.mkdir(parents=True)

        (chars_dir / "Aang_main.json").write_text("{}")
        (chars_dir / "Katara_main.json").write_text("{}")
        (rels_dir / "Aang_Katara_main.json").write_text("{}")

        with patch("src.visualizer.server.PROJECT_DIR", tmp_path):
            projects = get_all_projects()

        assert len(projects) == 1
        assert projects[0]["name"] == "test_project"
        assert projects[0]["character_count"] == 2
        assert projects[0]["relationship_count"] == 1

    def test_excludes_non_directories(self, tmp_path):
        """Should only include directories, not files."""
        from src.visualizer.server import get_all_projects

        (tmp_path / "not_a_project.txt").write_text("test")
        project_dir = tmp_path / "real_project"
        project_dir.mkdir()

        with patch("src.visualizer.server.PROJECT_DIR", tmp_path):
            projects = get_all_projects()

        assert len(projects) == 1
        assert projects[0]["name"] == "real_project"


class TestFlaskApp:
    """Test Flask routes and API endpoints."""

    @pytest.fixture
    def client(self):
        """Create Flask test client."""
        from src.visualizer.server import app

        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client

    @pytest.fixture
    def setup_test_project(self, tmp_path):
        """Create a test project structure."""
        project_dir = tmp_path / "test_project"
        chars_dir = project_dir / "characters"
        rels_dir = project_dir / "relationships"
        chars_dir.mkdir(parents=True)
        rels_dir.mkdir(parents=True)

        # Create test character
        char_data = {
            "name": "Aang",
            "canon": "main",
            "bio": "The Avatar",
            "affiliations": [],
        }
        (chars_dir / "Aang_main.json").write_text(json.dumps(char_data))

        # Create test relationship
        rel_data = {
            "characters": ["Aang", "Katara"],
            "canon": "main",
            "type": "friend",
            "claims": [],
        }
        (rels_dir / "Aang_Katara_main.json").write_text(json.dumps(rel_data))

        return tmp_path

    def test_api_list_canons(self, client, setup_test_project):
        """Test /api/<project>/canons endpoint."""
        with patch("src.visualizer.server.PROJECT_DIR", setup_test_project):
            response = client.get("/api/test_project/canons")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "canons" in data
        assert isinstance(data["canons"], list)

    def test_api_list_characters(self, client, setup_test_project):
        """Test /api/<project>/characters endpoint."""
        with patch("src.visualizer.server.PROJECT_DIR", setup_test_project):
            response = client.get("/api/test_project/characters")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "files" in data
        assert isinstance(data["files"], list)

    def test_api_list_relationships(self, client, setup_test_project):
        """Test /api/<project>/relationships endpoint."""
        with patch("src.visualizer.server.PROJECT_DIR", setup_test_project):
            response = client.get("/api/test_project/relationships")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "files" in data
        assert isinstance(data["files"], list)

    def test_api_get_character(self, client, setup_test_project):
        """Test /api/<project>/characters/<name> endpoint."""
        with patch("src.visualizer.server.PROJECT_DIR", setup_test_project):
            response = client.get("/api/test_project/characters/Aang_main")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["name"] == "Aang"

    def test_api_get_character_not_found(self, client, setup_test_project):
        """Test 404 for nonexistent character."""
        with patch("src.visualizer.server.PROJECT_DIR", setup_test_project):
            response = client.get("/api/test_project/characters/NonExistent_main")

        assert response.status_code == 404

    def test_api_get_relationship(self, client, setup_test_project):
        """Test /api/<project>/relationships/<file> endpoint."""
        with patch("src.visualizer.server.PROJECT_DIR", setup_test_project):
            response = client.get(
                "/api/test_project/relationships/Aang_Katara_main.json"
            )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["characters"] == ["Aang", "Katara"]

    def test_homepage_returns_html(self, client, setup_test_project):
        """Test homepage returns HTML."""
        with patch("src.visualizer.server.PROJECT_DIR", setup_test_project):
            response = client.get("/")

        assert response.status_code == 200
        assert b"<!DOCTYPE html>" in response.data or b"<html" in response.data
