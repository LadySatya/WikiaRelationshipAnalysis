#!/usr/bin/env python3
"""
Flask-based visualization server with project listing and live monitoring.

URL Structure:
    /                         - List all projects
    /<project>                - Relationship graph viewer
    /<project>/logs           - Log file browser
    /<project>/monitor        - Live log streaming
    /api/<project>/relationships - List all relationship files (optional ?canon=<id>)
    /api/<project>/characters    - List all character files (optional ?canon=<id>)
    /api/<project>/characters/<name> - Get single character data
    /api/<project>/relationships/<file> - Relationship details
    /api/<project>/canons        - List available canons with counts
    /api/<project>/logs/stream - Server-Sent Events log stream
"""
from flask import Flask, render_template_string, jsonify, Response, abort, request
from pathlib import Path
import json
import time
import re
from typing import Dict, List, Optional
import webbrowser
import threading

app = Flask(__name__)
PROJECT_DIR = Path("data/projects")


# ============================================================================
# CANON UTILITIES
# ============================================================================

def extract_canon_from_filename(filename: str) -> str:
    """
    Extract canon from a filename like 'Aang_film.json' -> 'film'.

    Filename format: <name>_<canon>.json
    If no underscore found or file predates canon support, returns 'main'.
    """
    # Remove .json extension
    stem = filename.rsplit('.', 1)[0] if '.' in filename else filename

    # Find last underscore (canon is always the last part)
    if '_' in stem:
        parts = stem.rsplit('_', 1)
        # Check if the last part looks like a canon (lowercase, short)
        potential_canon = parts[-1].lower()
        if potential_canon in ('main', 'film', 'netflix', 'legends', 'comics', 'games'):
            return potential_canon

    return 'main'


def get_project_canons(project: str) -> List[Dict]:
    """
    Get list of canons available in a project with counts.

    Returns:
        List of dicts with:
        - id: canon identifier (e.g., 'main', 'film')
        - name: display name (e.g., 'Main', 'Film')
        - character_count: number of characters in this canon
        - relationship_count: number of relationships in this canon
    """
    characters_dir = PROJECT_DIR / project / "characters"
    relationships_dir = PROJECT_DIR / project / "relationships"

    canon_stats: Dict[str, Dict[str, int]] = {}

    # Count characters per canon
    if characters_dir.exists():
        for f in characters_dir.glob("*.json"):
            if f.name.startswith("_"):
                continue
            canon = extract_canon_from_filename(f.name)
            if canon not in canon_stats:
                canon_stats[canon] = {"characters": 0, "relationships": 0}
            canon_stats[canon]["characters"] += 1

    # Count relationships per canon
    if relationships_dir.exists():
        for f in relationships_dir.glob("*.json"):
            if f.name == "graph.json":
                continue
            canon = extract_canon_from_filename(f.name)
            if canon not in canon_stats:
                canon_stats[canon] = {"characters": 0, "relationships": 0}
            canon_stats[canon]["relationships"] += 1

    # Build result list
    canons = []
    for canon_id, stats in sorted(canon_stats.items()):
        canons.append({
            "id": canon_id,
            "name": canon_id.title(),  # 'main' -> 'Main'
            "character_count": stats["characters"],
            "relationship_count": stats["relationships"]
        })

    return canons


# ============================================================================
# PROJECT LISTING
# ============================================================================

def get_all_projects() -> List[Dict]:
    """
    Scan data/projects/ and return list of projects with metadata.

    Returns:
        List of project dicts with:
        - name: project name
        - has_relationships: bool (relationship files exist)
        - has_characters: bool (characters/ dir exists)
        - character_count: number of character files
        - relationship_count: number of relationship files
        - latest_log: path to most recent log file
    """
    if not PROJECT_DIR.exists():
        return []

    projects = []
    for project_path in PROJECT_DIR.iterdir():
        if not project_path.is_dir():
            continue

        name = project_path.name
        relationships_dir = project_path / "relationships"
        chars_dir = project_path / "characters"
        logs_dir = project_path / "logs"

        # Count relationship files (exclude graph.json if it exists from old system)
        relationship_count = 0
        if relationships_dir.exists():
            relationship_count = len([
                f for f in relationships_dir.glob("*.json")
                if f.name != "graph.json"
            ])

        # Count character files
        character_count = 0
        if chars_dir.exists():
            character_count = len([
                f for f in chars_dir.glob("*.json")
                if f.name != "_discovered.json"
            ])

        # Find latest log file (search recursively in subdirectories)
        latest_log = None
        if logs_dir.exists():
            log_files = sorted(
                logs_dir.rglob("*.log"),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )
            if log_files:
                latest_log = str(log_files[0].relative_to(PROJECT_DIR))

        projects.append({
            "name": name,
            "has_relationships": relationship_count > 0,
            "has_characters": chars_dir.exists() and character_count > 0,
            "character_count": character_count,
            "relationship_count": relationship_count,
            "latest_log": latest_log
        })

    return sorted(projects, key=lambda p: p["name"])


@app.route('/')
def index():
    """Project listing homepage."""
    projects = get_all_projects()

    html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WikiaAnalysis - Projects</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: #f5f5f5;
            padding: 2rem;
        }

        .header {
            background: #2c3e50;
            color: white;
            padding: 2rem;
            border-radius: 8px;
            margin-bottom: 2rem;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }

        .header h1 {
            font-size: 2rem;
            margin-bottom: 0.5rem;
        }

        .header p {
            color: #bdc3c7;
        }

        .project-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            gap: 1.5rem;
        }

        .project-card {
            background: white;
            border-radius: 8px;
            padding: 1.5rem;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            transition: transform 0.2s, box-shadow 0.2s;
        }

        .project-card:hover {
            transform: translateY(-4px);
            box-shadow: 0 4px 16px rgba(0,0,0,0.15);
        }

        .project-name {
            font-size: 1.3rem;
            font-weight: 600;
            color: #2c3e50;
            margin-bottom: 1rem;
        }

        .project-stats {
            display: flex;
            gap: 1rem;
            margin-bottom: 1rem;
        }

        .stat {
            background: #ecf0f1;
            padding: 0.5rem 0.75rem;
            border-radius: 4px;
            font-size: 0.85rem;
        }

        .stat strong {
            color: #3498db;
        }

        .project-actions {
            display: flex;
            gap: 0.5rem;
            margin-top: 1rem;
        }

        .btn {
            padding: 0.5rem 1rem;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.9rem;
            text-decoration: none;
            display: inline-block;
            transition: background 0.2s;
        }

        .btn-primary {
            background: #3498db;
            color: white;
        }

        .btn-primary:hover {
            background: #2980b9;
        }

        .btn-secondary {
            background: #95a5a6;
            color: white;
        }

        .btn-secondary:hover {
            background: #7f8c8d;
        }

        .btn:disabled, .btn-disabled {
            opacity: 0.5;
            cursor: not-allowed;
            pointer-events: none;
        }

        .status-badge {
            display: inline-block;
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
            margin-bottom: 0.5rem;
        }

        .status-ready {
            background: #d4edda;
            color: #155724;
        }

        .status-building {
            background: #fff3cd;
            color: #856404;
        }

        .status-incomplete {
            background: #f8d7da;
            color: #721c24;
        }

        .empty-state {
            text-align: center;
            padding: 4rem;
            color: #95a5a6;
        }

        .empty-state h2 {
            font-size: 1.5rem;
            margin-bottom: 1rem;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>WikiaAnalysis Projects</h1>
        <p>{{ project_count }} project(s) found</p>
    </div>

    {% if projects %}
    <div class="project-grid">
        {% for project in projects %}
        <div class="project-card">
            {% if project.has_relationships %}
                <span class="status-badge status-ready">Ready</span>
            {% elif project.has_characters %}
                <span class="status-badge status-building">Building</span>
            {% else %}
                <span class="status-badge status-incomplete">Incomplete</span>
            {% endif %}

            <div class="project-name">{{ project.name }}</div>

            <div class="project-stats">
                <div class="stat">
                    <strong>{{ project.character_count }}</strong> characters
                </div>
                {% if project.relationship_count > 0 %}
                <div class="stat">
                    <strong>{{ project.relationship_count }}</strong> relationships
                </div>
                {% endif %}
            </div>

            <div class="project-actions">
                <a href="/{{ project.name }}" class="btn btn-primary{% if not project.has_relationships %} btn-disabled{% endif %}">
                    View Graph
                </a>
                {% if project.latest_log %}
                <a href="/{{ project.name }}/logs" class="btn btn-secondary">
                    Logs
                </a>
                {% endif %}
            </div>
        </div>
        {% endfor %}
    </div>
    {% else %}
    <div class="empty-state">
        <h2>No projects found</h2>
        <p>Run <code>python main.py crawl &lt;project&gt; &lt;url&gt;</code> to create a project</p>
    </div>
    {% endif %}
</body>
</html>
"""

    return render_template_string(html, projects=projects, project_count=len(projects))


# ============================================================================
# GRAPH VIEWER
# ============================================================================

@app.route('/<project>')
def view_graph(project: str):
    """Relationship graph viewer for a project."""
    relationships_dir = PROJECT_DIR / project / "relationships"

    # Check if project has relationship files
    if not relationships_dir.exists():
        abort(404, f"Project '{project}' not found.")

    rel_files = [f for f in relationships_dir.glob("*.json") if f.name != "graph.json"]
    if not rel_files:
        abort(404, f"Project '{project}' has no relationships. Run 'python main.py discover {project}' first.")

    # Serve the embedded viewer with client-side graph building
    html = _get_viewer_html(project)
    return render_template_string(html)


def _get_viewer_html(project: str) -> str:
    """Generate the viewer HTML with client-side graph building."""
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{project} - Character Relationship Graph</title>
    <script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            height: 100vh;
            overflow: hidden;
            background: #f5f5f5;
        }}

        #header {{
            background: #2c3e50;
            color: white;
            padding: 1rem 2rem;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        #header h1 {{
            font-size: 1.5rem;
            font-weight: 600;
        }}

        #header .stats {{
            font-size: 0.9rem;
            color: #bdc3c7;
        }}

        .header-actions {{
            display: flex;
            gap: 0.5rem;
        }}

        .btn {{
            padding: 0.5rem 1rem;
            background: #3498db;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.85rem;
            text-decoration: none;
        }}

        .btn:hover {{
            background: #2980b9;
        }}

        .btn-secondary {{
            background: #95a5a6;
        }}

        .btn-secondary:hover {{
            background: #7f8c8d;
        }}

        .canon-filter {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}

        .canon-filter label {{
            color: #bdc3c7;
            font-size: 0.9rem;
        }}

        .canon-filter select {{
            padding: 0.4rem 0.75rem;
            border: none;
            border-radius: 4px;
            font-size: 0.85rem;
            background: #34495e;
            color: white;
            cursor: pointer;
        }}

        .canon-filter select:hover {{
            background: #3d566e;
        }}

        .canon-badge {{
            display: inline-block;
            padding: 0.15rem 0.5rem;
            border-radius: 3px;
            font-size: 0.75rem;
            font-weight: 600;
            margin-left: 0.5rem;
            text-transform: uppercase;
        }}

        .canon-main {{ background: #3498db; color: white; }}
        .canon-film {{ background: #e74c3c; color: white; }}
        .canon-netflix {{ background: #e91e63; color: white; }}
        .canon-legends {{ background: #9b59b6; color: white; }}
        .canon-comics {{ background: #f39c12; color: white; }}
        .canon-games {{ background: #27ae60; color: white; }}

        #container {{
            display: flex;
            height: calc(100vh - 60px);
        }}

        #graph {{
            flex: 1;
            background: white;
            border-right: 1px solid #ddd;
        }}

        #details {{
            width: 400px;
            background: white;
            overflow-y: auto;
            padding: 1.5rem;
        }}

        #details.empty {{
            display: flex;
            align-items: center;
            justify-content: center;
            color: #95a5a6;
            font-style: italic;
        }}

        .detail-section {{
            margin-bottom: 1.5rem;
        }}

        .detail-section h2 {{
            font-size: 1.2rem;
            color: #2c3e50;
            margin-bottom: 0.5rem;
            border-bottom: 2px solid #3498db;
            padding-bottom: 0.25rem;
        }}

        .detail-section h3 {{
            font-size: 1rem;
            color: #34495e;
            margin: 1rem 0 0.5rem 0;
        }}

        .relationship-type {{
            display: inline-block;
            padding: 0.25rem 0.75rem;
            background: #3498db;
            color: white;
            border-radius: 12px;
            font-size: 0.85rem;
            margin: 0.5rem 0;
        }}

        .confidence {{
            color: #27ae60;
            font-weight: 600;
        }}

        .claim {{
            background: #ecf0f1;
            padding: 0.75rem;
            margin: 0.5rem 0;
            border-radius: 4px;
            border-left: 3px solid #3498db;
        }}

        .evidence {{
            font-size: 0.85rem;
            color: #7f8c8d;
            margin-top: 0.5rem;
            padding-left: 1rem;
            border-left: 2px solid #bdc3c7;
        }}

        .evidence-item {{
            margin: 0.5rem 0;
            padding: 0.5rem;
            background: #f8f9fa;
            border-radius: 3px;
        }}

        .evidence-source {{
            color: #3498db;
            font-size: 0.8rem;
            margin-top: 0.25rem;
        }}

        .evidence-source a {{
            color: #3498db;
            text-decoration: none;
        }}

        .evidence-source a:hover {{
            text-decoration: underline;
        }}

        .stats-badge {{
            display: inline-block;
            background: #ecf0f1;
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
            font-size: 0.85rem;
            margin-right: 0.5rem;
            margin-bottom: 0.5rem;
        }}

        .bio {{
            color: #555;
            font-size: 0.9rem;
            line-height: 1.5;
            margin: 0.5rem 0;
        }}

        .aliases {{
            color: #7f8c8d;
            font-size: 0.85rem;
            font-style: italic;
        }}

        .legend {{
            position: absolute;
            top: 80px;
            right: 420px;
            background: white;
            padding: 1rem;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            font-size: 0.85rem;
        }}

        .legend-title {{
            font-weight: 600;
            margin-bottom: 0.5rem;
            color: #2c3e50;
        }}

        .legend-item {{
            display: flex;
            align-items: center;
            margin: 0.25rem 0;
        }}

        .legend-color {{
            width: 20px;
            height: 20px;
            border-radius: 50%;
            margin-right: 0.5rem;
            border: 2px solid #333;
        }}

        .loading {{
            display: flex;
            align-items: center;
            justify-content: center;
            height: 100%;
            color: #95a5a6;
            font-size: 1.2rem;
        }}

        .error {{
            color: #e74c3c;
            padding: 2rem;
            text-align: center;
        }}
    </style>
</head>
<body>
    <div id="header">
        <div>
            <h1>{project} - Character Relationship Graph</h1>
            <div class="stats" id="stats">Loading...</div>
        </div>
        <div class="header-actions">
            <div class="canon-filter">
                <label for="canon-select">Canon:</label>
                <select id="canon-select">
                    <option value="">All Canons</option>
                </select>
            </div>
            <a href="/{project}/logs" class="btn btn-secondary">Logs</a>
            <a href="/" class="btn btn-secondary">Projects</a>
        </div>
    </div>

    <div id="container">
        <div id="graph">
            <div class="loading">Loading relationships...</div>
        </div>
        <div id="details" class="empty">
            Click a character or relationship to see details
        </div>
    </div>

    <div class="legend" id="legend-relationships">
        <div class="legend-title">Relationship Types</div>
        <div class="legend-item">
            <div class="legend-color" style="background: #e74c3c;"></div>
            <span>Romantic</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #3498db;"></div>
            <span>Family</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #2ecc71;"></div>
            <span>Friend</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #f39c12;"></div>
            <span>Mentor</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #9b59b6;"></div>
            <span>Enemy</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #95a5a6;"></div>
            <span>Other</span>
        </div>
    </div>

    <div class="legend" id="legend-canons" style="top: 280px;">
        <div class="legend-title">Canon (Node Borders)</div>
        <div class="legend-item">
            <div class="legend-color" style="background: #34495e; border-color: #3498db;"></div>
            <span>Main</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #34495e; border-color: #e74c3c;"></div>
            <span>Film</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #34495e; border-color: #e91e63;"></div>
            <span>Netflix</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #34495e; border-color: #9b59b6;"></div>
            <span>Legends</span>
        </div>
    </div>

    <script>
        const projectName = '{project}';

        // Global data
        let graphData = null;
        let characterCache = {{}};
        let currentCanon = '';  // Empty = all canons
        let availableCanons = [];

        // Canon border colors (visual distinction)
        const canonColors = {{
            'main': '#3498db',
            'film': '#e74c3c',
            'netflix': '#e91e63',
            'legends': '#9b59b6',
            'comics': '#f39c12',
            'games': '#27ae60',
            'default': '#3498db'
        }};

        // Color mapping for relationship types
        const typeColors = {{
            'romantic_partner': '#e74c3c',
            'romantic': '#e74c3c',
            'ex_romantic_partner': '#e74c3c',
            'family': '#3498db',
            'parent': '#3498db',
            'sibling': '#3498db',
            'child': '#3498db',
            'friend': '#2ecc71',
            'mentor': '#f39c12',
            'mentor_supporter': '#f39c12',
            'student': '#f39c12',
            'enemy': '#9b59b6',
            'rival': '#9b59b6',
            'adversary': '#9b59b6',
            'ally': '#2ecc71',
            'companion': '#2ecc71',
            'default': '#95a5a6'
        }};

        // Load canon dropdown options
        async function loadCanons() {{
            try {{
                const response = await fetch(`/api/${{projectName}}/canons`);
                if (response.ok) {{
                    const data = await response.json();
                    availableCanons = data.canons || [];

                    const select = document.getElementById('canon-select');
                    availableCanons.forEach(canon => {{
                        const option = document.createElement('option');
                        option.value = canon.id;
                        option.textContent = `${{canon.name}} (${{canon.relationship_count}})`;
                        select.appendChild(option);
                    }});

                    // Listen for changes
                    select.addEventListener('change', (e) => {{
                        currentCanon = e.target.value;
                        loadRelationships();
                    }});
                }}
            }} catch (e) {{
                console.log('Could not load canons:', e);
            }}
        }}

        // Load relationships (with optional canon filter)
        async function loadRelationships() {{
            try {{
                document.getElementById('graph').innerHTML =
                    '<div class="loading">Loading relationships...</div>';

                // Build URL with optional canon filter
                let url = `/api/${{projectName}}/relationships`;
                if (currentCanon) {{
                    url += `?canon=${{currentCanon}}`;
                }}

                const relsResponse = await fetch(url);
                if (!relsResponse.ok) throw new Error('Failed to load relationships list');
                const relsData = await relsResponse.json();

                if (relsData.count === 0) {{
                    const msg = currentCanon
                        ? `No relationships found in "${{currentCanon}}" canon.`
                        : 'No relationships found. Run discovery first.';
                    document.getElementById('graph').innerHTML =
                        `<div class="error">${{msg}}</div>`;
                    document.getElementById('stats').textContent = '0 characters, 0 relationships';
                    return;
                }}

                // Fetch all relationship files in parallel
                const relPromises = relsData.files.map(file =>
                    fetch(`/api/${{projectName}}/relationships/${{file.filename}}`)
                        .then(r => r.json())
                        .then(data => ({{...data, _filename: file.filename, _canon: file.canon}}))
                        .catch(err => {{
                            console.error(`Failed to load ${{file.filename}}:`, err);
                            return null;
                        }})
                );

                const relationships = (await Promise.all(relPromises)).filter(r => r !== null);

                // Build graph from relationships
                graphData = buildGraphFromRelationships(relationships);

                // Update header stats
                const canonLabel = currentCanon ? ` (${{currentCanon}})` : '';
                document.getElementById('stats').textContent =
                    `${{graphData.nodes.length}} characters, ${{graphData.edges.length}} relationships${{canonLabel}}`;

                // Build visualization
                buildGraph();

            }} catch (error) {{
                console.error('Error loading graph:', error);
                document.getElementById('graph').innerHTML =
                    `<div class="error">Error loading graph: ${{error.message}}</div>`;
            }}
        }}

        // Initialize visualization
        async function init() {{
            await loadCanons();
            await loadRelationships();
        }}

        function buildGraphFromRelationships(relationships) {{
            // Extract unique characters from relationships (track canon for each)
            const characterMap = {{}};  // name -> {{ canon, relCount }}

            relationships.forEach(rel => {{
                if (rel.characters && Array.isArray(rel.characters)) {{
                    const canon = rel._canon || rel.canon || 'main';
                    rel.characters.forEach(char => {{
                        if (!characterMap[char]) {{
                            characterMap[char] = {{ canon: canon, relCount: 0 }};
                        }}
                        characterMap[char].relCount++;
                    }});
                }}
            }});

            // Build nodes
            const nodes = Object.entries(characterMap).map(([name, data]) => {{
                return {{
                    id: name,
                    label: name,
                    title: `${{name}}\\n${{data.relCount}} relationship(s)\\nCanon: ${{data.canon}}`,
                    total_relationships: data.relCount,
                    canon: data.canon
                }};
            }});

            // Build edges
            const edges = relationships.map(rel => {{
                const chars = rel.characters || [];
                const char_a = chars[0] || 'Unknown';
                const char_b = chars[1] || 'Unknown';

                // Count evidence
                const evidenceCount = (rel.claims || []).reduce(
                    (sum, claim) => sum + (claim.evidence || []).length,
                    0
                );

                // Calculate confidence from evidence count
                const confidence = Math.min(0.5 + (evidenceCount * 0.1), 1.0);

                return {{
                    from: char_a,
                    to: char_b,
                    type: rel.type || 'other',
                    summary: rel.summary || '',
                    confidence: confidence,
                    evidence_count: evidenceCount,
                    _filename: rel._filename,
                    _data: rel
                }};
            }});

            return {{ nodes, edges }};
        }}

        function buildGraph() {{
            // Prepare nodes for vis.js with canon-based colors
            const visNodes = graphData.nodes.map(node => {{
                const borderColor = canonColors[node.canon] || canonColors.default;
                // Darken border color for highlight
                const highlightBorder = borderColor;

                return {{
                    id: node.id,
                    label: node.label,
                    title: node.title,
                    color: {{
                        background: '#34495e',
                        border: borderColor,
                        highlight: {{
                            background: '#2c3e50',
                            border: highlightBorder
                        }}
                    }},
                    font: {{
                        color: '#fff',
                        size: 14
                    }},
                    shape: 'box',
                    margin: 10,
                    borderWidth: 3,
                    borderWidthSelected: 5
                }};
            }});

            // Prepare edges for vis.js
            const visEdges = graphData.edges.map((edge, index) => ({{
                id: `edge_${{index}}`,
                from: edge.from,
                to: edge.to,
                label: edge.type.replace(/_/g, ' '),
                title: edge.summary,
                color: {{
                    color: typeColors[edge.type] || typeColors.default,
                    highlight: typeColors[edge.type] || typeColors.default
                }},
                width: Math.max(1, Math.min(edge.evidence_count, 5)),
                font: {{
                    align: 'top',
                    size: 10
                }}
            }}));

            // Create network
            const container = document.getElementById('graph');
            container.innerHTML = '';

            const data = {{
                nodes: new vis.DataSet(visNodes),
                edges: new vis.DataSet(visEdges)
            }};

            const options = {{
                physics: {{
                    stabilization: {{
                        iterations: 200
                    }},
                    barnesHut: {{
                        gravitationalConstant: -2000,
                        springLength: 200,
                        springConstant: 0.04
                    }}
                }},
                interaction: {{
                    hover: true,
                    tooltipDelay: 100
                }},
                nodes: {{
                    borderWidth: 2,
                    borderWidthSelected: 3
                }},
                edges: {{
                    smooth: {{
                        type: 'continuous'
                    }}
                }}
            }};

            const network = new vis.Network(container, data, options);

            // Handle clicks
            network.on('click', function(params) {{
                if (params.nodes.length > 0) {{
                    const nodeId = params.nodes[0];
                    const node = graphData.nodes.find(n => n.id === nodeId);
                    showNodeDetails(node);
                }} else if (params.edges.length > 0) {{
                    const edgeId = params.edges[0];
                    const edgeIndex = parseInt(edgeId.replace('edge_', ''));
                    const edge = graphData.edges[edgeIndex];
                    showEdgeDetails(edge);
                }}
            }});
        }}

        async function showNodeDetails(node) {{
            const detailsDiv = document.getElementById('details');
            detailsDiv.classList.remove('empty');

            // Find all relationships for this character
            const relationships = graphData.edges.filter(e =>
                e.from === node.id || e.to === node.id
            );

            // Try to fetch character data
            let charData = characterCache[node.id];
            if (!charData) {{
                try {{
                    const response = await fetch(`/api/${{projectName}}/characters/${{encodeURIComponent(node.id)}}`);
                    if (response.ok) {{
                        charData = await response.json();
                        characterCache[node.id] = charData;
                    }}
                }} catch (e) {{
                    console.log(`Could not load character data for ${{node.id}}`);
                }}
            }}

            let html = `
                <div class="detail-section">
                    <h2>${{node.id}}</h2>
            `;

            if (charData) {{
                if (charData.aliases && charData.aliases.length > 0) {{
                    html += `<div class="aliases">Also known as: ${{charData.aliases.join(', ')}}</div>`;
                }}
                if (charData.bio) {{
                    html += `<div class="bio">${{charData.bio}}</div>`;
                }}
                if (charData.source_urls && charData.source_urls.length > 0) {{
                    html += `<div class="stats-badge">
                        <a href="${{charData.source_urls[0]}}" target="_blank">Wiki Page</a>
                    </div>`;
                }}
            }}

            html += `<div class="stats-badge">${{node.total_relationships}} relationship(s)</div></div>`;

            if (relationships.length > 0) {{
                html += '<div class="detail-section"><h3>Relationships</h3>';
                relationships.forEach(edge => {{
                    const otherChar = edge.from === node.id ? edge.to : edge.from;
                    const direction = edge.from === node.id ? 'with' : 'from';
                    html += `
                        <div class="claim">
                            <strong>${{otherChar}}</strong>
                            <span class="relationship-type">${{edge.type.replace(/_/g, ' ')}}</span>
                            <div>${{edge.summary || 'No summary available'}}</div>
                            <div style="margin-top: 0.5rem; font-size: 0.85rem;">
                                Confidence: <span class="confidence">${{(edge.confidence * 100).toFixed(0)}}%</span>
                                | Evidence: ${{edge.evidence_count}} citation(s)
                            </div>
                        </div>
                    `;
                }});
                html += '</div>';
            }}

            detailsDiv.innerHTML = html;
        }}

        function showEdgeDetails(edge) {{
            const detailsDiv = document.getElementById('details');
            detailsDiv.classList.remove('empty');

            const details = edge._data;

            let html = `
                <div class="detail-section">
                    <h2>${{edge.from}} & ${{edge.to}}</h2>
                    <span class="relationship-type">${{edge.type.replace(/_/g, ' ')}}</span>
                    <div style="margin-top: 1rem;">${{edge.summary || 'No summary available'}}</div>
                    <div style="margin-top: 0.5rem;">
                        <span class="stats-badge">Confidence: <span class="confidence">${{(edge.confidence * 100).toFixed(0)}}%</span></span>
                        <span class="stats-badge">Evidence: ${{edge.evidence_count}} citation(s)</span>
                    </div>
                </div>
            `;

            if (details && details.claims && details.claims.length > 0) {{
                html += '<div class="detail-section"><h3>Detailed Claims</h3>';

                details.claims.forEach((claimObj, idx) => {{
                    const evidenceList = claimObj.evidence || [];
                    html += `
                        <div class="claim">
                            <strong>Claim ${{idx + 1}}:</strong> ${{claimObj.claim}}
                            <div class="evidence">
                                <strong>Evidence (${{evidenceList.length}} source(s)):</strong>
                    `;

                    // Show first 3 evidence sources
                    const evidenceToShow = evidenceList.slice(0, 3);
                    evidenceToShow.forEach(ev => {{
                        const text = ev.evidence_text || ev.cited_text || '';
                        const url = ev.evidence_url || ev.source_url || '';
                        const displayText = text.length > 200 ? text.substring(0, 200) + '...' : text;

                        html += `
                            <div class="evidence-item">
                                "${{displayText}}"
                                <div class="evidence-source">
                                    ${{url ? `<a href="${{url}}" target="_blank">Source</a>` : 'No source URL'}}
                                </div>
                            </div>
                        `;
                    }});

                    if (evidenceList.length > 3) {{
                        html += `
                            <div style="margin-top: 0.5rem; font-style: italic;">
                                + ${{evidenceList.length - 3}} more source(s)
                            </div>
                        `;
                    }}

                    html += '</div></div>';
                }});

                html += '</div>';
            }}

            detailsDiv.innerHTML = html;
        }}

        // Initialize on page load
        init();
    </script>
</body>
</html>'''


# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.route('/api/<project>/relationships')
def api_list_relationships(project: str):
    """Return list of all relationship files for a project.

    Query params:
        canon: Optional filter to show only relationships from a specific canon
    """
    relationships_dir = PROJECT_DIR / project / "relationships"
    canon_filter = request.args.get('canon')

    if not relationships_dir.exists():
        return jsonify({"error": "No relationships found", "files": [], "count": 0}), 404

    files = []
    for f in relationships_dir.glob("*.json"):
        # Skip old graph.json if it exists
        if f.name == "graph.json":
            continue

        # Apply canon filter if specified
        if canon_filter:
            file_canon = extract_canon_from_filename(f.name)
            if file_canon != canon_filter.lower():
                continue

        files.append({
            "filename": f.name,
            "canon": extract_canon_from_filename(f.name),
            "modified": f.stat().st_mtime
        })

    # Sort by filename for consistent ordering
    files.sort(key=lambda x: x["filename"])

    return jsonify({"files": files, "count": len(files), "canon_filter": canon_filter})


@app.route('/api/<project>/characters')
def api_list_characters(project: str):
    """Return list of all character files for a project.

    Query params:
        canon: Optional filter to show only characters from a specific canon
    """
    characters_dir = PROJECT_DIR / project / "characters"
    canon_filter = request.args.get('canon')

    if not characters_dir.exists():
        return jsonify({"error": "No characters found", "files": [], "count": 0}), 404

    files = []
    for f in characters_dir.glob("*.json"):
        # Skip internal files
        if f.name.startswith("_"):
            continue

        # Apply canon filter if specified
        file_canon = extract_canon_from_filename(f.name)
        if canon_filter and file_canon != canon_filter.lower():
            continue

        # Extract character name (remove canon suffix)
        stem = f.stem
        if '_' in stem:
            parts = stem.rsplit('_', 1)
            if parts[-1].lower() in ('main', 'film', 'netflix', 'legends', 'comics', 'games'):
                char_name = parts[0]
            else:
                char_name = stem
        else:
            char_name = stem

        files.append({
            "filename": f.name,
            "name": char_name,
            "canon": file_canon,
            "modified": f.stat().st_mtime
        })

    # Sort by name
    files.sort(key=lambda x: x["name"])

    return jsonify({"files": files, "count": len(files), "canon_filter": canon_filter})


@app.route('/api/<project>/characters/<name>')
def api_get_character(project: str, name: str):
    """Return single character data."""
    characters_dir = PROJECT_DIR / project / "characters"

    # Try exact filename first
    char_file = characters_dir / f"{name}.json"

    if not char_file.exists():
        # Try URL-decoded name
        import urllib.parse
        decoded_name = urllib.parse.unquote(name)
        char_file = characters_dir / f"{decoded_name}.json"

    if not char_file.exists():
        return jsonify({"error": f"Character not found: {name}"}), 404

    with open(char_file, 'r', encoding='utf-8') as f:
        return jsonify(json.load(f))


@app.route('/api/<project>/relationships/<filename>')
def api_relationship(project: str, filename: str):
    """Serve relationship detail JSON."""
    rel_path = PROJECT_DIR / project / "relationships" / filename

    if not rel_path.exists():
        return jsonify({"error": f"Relationship file not found: {filename}"}), 404

    with open(rel_path, 'r', encoding='utf-8') as f:
        return jsonify(json.load(f))


@app.route('/api/<project>/canons')
def api_list_canons(project: str):
    """Return list of canons available in this project with counts."""
    canons = get_project_canons(project)
    return jsonify({"canons": canons, "count": len(canons)})


# ============================================================================
# LOG MONITORING & BROWSING
# ============================================================================

@app.route('/<project>/logs')
def browse_logs(project: str):
    """Browse all log files for a project."""
    logs_dir = PROJECT_DIR / project / "logs"

    if not logs_dir.exists():
        abort(404, f"No logs found for project '{project}'")

    # Get all log files recursively, sorted by modification time (newest first)
    log_files = sorted(
        logs_dir.rglob("*.log"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )

    # Build log file list with metadata
    logs = []
    for log_file in log_files:
        stat = log_file.stat()
        rel_path = log_file.relative_to(logs_dir)
        logs.append({
            "name": str(rel_path).replace('\\', '/'),
            "size": stat.st_size,
            "modified": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stat.st_mtime)),
            "modified_ts": stat.st_mtime
        })

    html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ project }} - Log Files</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f5f5;
        }
        .header {
            background: #2c3e50;
            color: white;
            padding: 1rem 2rem;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .header h1 { font-size: 1.3rem; font-weight: 600; margin-bottom: 0.5rem; }
        .header .breadcrumb { font-size: 0.9rem; color: #bdc3c7; }
        .header .breadcrumb a { color: #3498db; text-decoration: none; }
        .header .breadcrumb a:hover { text-decoration: underline; }
        .content { padding: 2rem; max-width: 1200px; margin: 0 auto; }
        .log-list {
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .log-item {
            padding: 1rem 1.5rem;
            border-bottom: 1px solid #ecf0f1;
            display: flex;
            justify-content: space-between;
            align-items: center;
            transition: background 0.2s;
        }
        .log-item:hover { background: #f8f9fa; }
        .log-item:last-child { border-bottom: none; }
        .log-info { flex: 1; }
        .log-name { font-weight: 600; color: #2c3e50; margin-bottom: 0.25rem; }
        .log-meta { font-size: 0.85rem; color: #7f8c8d; }
        .log-actions { display: flex; gap: 0.5rem; }
        .btn {
            padding: 0.5rem 1rem;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.9rem;
            text-decoration: none;
            display: inline-block;
        }
        .btn-primary { background: #3498db; color: white; }
        .btn-primary:hover { background: #2980b9; }
        .btn-secondary { background: #95a5a6; color: white; }
        .btn-secondary:hover { background: #7f8c8d; }
        .empty-state { text-align: center; padding: 4rem; color: #95a5a6; }
    </style>
</head>
<body>
    <div class="header">
        <h1>{{ project }} - Log Files</h1>
        <div class="breadcrumb">
            <a href="/">Projects</a> /
            <a href="/{{ project }}">{{ project }}</a> /
            Logs
        </div>
    </div>
    <div class="content">
        {% if logs %}
        <div class="log-list">
            {% for log in logs %}
            <div class="log-item">
                <div class="log-info">
                    <div class="log-name">{{ log.name }}</div>
                    <div class="log-meta">
                        {{ log.modified }} &bull; {{ "%.1f"|format(log.size / 1024) }} KB
                    </div>
                </div>
                <div class="log-actions">
                    <a href="/{{ project }}/monitor?log={{ log.name }}" class="btn btn-primary">
                        Monitor Live
                    </a>
                    <a href="/api/{{ project }}/logs/{{ log.name }}" class="btn btn-secondary" target="_blank">
                        View Full
                    </a>
                </div>
            </div>
            {% endfor %}
        </div>
        {% else %}
        <div class="empty-state">
            <h2>No log files found</h2>
        </div>
        {% endif %}
    </div>
</body>
</html>
"""

    return render_template_string(html, project=project, logs=logs)


@app.route('/<project>/monitor')
def monitor(project: str):
    """Live log monitoring page."""
    from flask import request

    logs_dir = PROJECT_DIR / project / "logs"

    if not logs_dir.exists():
        abort(404, f"No logs found for project '{project}'")

    # Get log file from query param or use most recent
    log_name = request.args.get('log')
    if log_name:
        log_file = logs_dir / log_name
        if not log_file.exists():
            abort(404, f"Log file not found: {log_name}")
    else:
        log_files = sorted(
            logs_dir.rglob("*.log"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        if not log_files:
            abort(404, f"No log files found for project '{project}'")
        log_file = log_files[0]
        log_name = str(log_file.relative_to(logs_dir)).replace('\\', '/')

    html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ project }} - Live Logs</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            background: #1e1e1e;
            color: #d4d4d4;
            height: 100vh;
            display: flex;
            flex-direction: column;
        }
        .header {
            background: #2c3e50;
            color: white;
            padding: 1rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        }
        .header h1 { font-size: 1.2rem; font-weight: 600; }
        .header .controls { display: flex; gap: 0.5rem; }
        .btn {
            padding: 0.5rem 1rem;
            background: #3498db;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.85rem;
            text-decoration: none;
        }
        .btn:hover { background: #2980b9; }
        .btn-secondary { background: #95a5a6; }
        .btn-secondary:hover { background: #7f8c8d; }
        .status {
            padding: 0.5rem 1rem;
            border-radius: 4px;
            font-size: 0.85rem;
        }
        .status.connected { background: #d4edda; color: #155724; }
        .status.disconnected { background: #f8d7da; color: #721c24; }
        #log-container {
            flex: 1;
            overflow-y: auto;
            padding: 1rem;
            font-size: 13px;
            line-height: 1.5;
        }
        .log-line { padding: 0.25rem 0; white-space: pre-wrap; word-break: break-word; }
        .log-line.info { color: #4ec9b0; }
        .log-line.warn { color: #dcdcaa; }
        .log-line.error { color: #f48771; font-weight: 600; }
        .log-line.ok { color: #b5cea8; font-weight: 600; }
    </style>
</head>
<body>
    <div class="header">
        <h1>{{ project }} - Live Logs ({{ log_name }})</h1>
        <div class="controls">
            <span id="status" class="status disconnected">Disconnected</span>
            <button id="clearBtn" class="btn btn-secondary">Clear</button>
            <a href="/{{ project }}" class="btn">View Graph</a>
            <a href="/" class="btn btn-secondary">Projects</a>
        </div>
    </div>
    <div id="log-container"></div>
    <script>
        const logContainer = document.getElementById('log-container');
        const statusEl = document.getElementById('status');
        const clearBtn = document.getElementById('clearBtn');
        let eventSource = null;

        function classifyLogLine(line) {
            if (line.includes('[ERROR]')) return 'error';
            if (line.includes('[WARN]')) return 'warn';
            if (line.includes('[OK]')) return 'ok';
            if (line.includes('[INFO]')) return 'info';
            return '';
        }

        function appendLog(line) {
            const logLine = document.createElement('div');
            logLine.className = 'log-line ' + classifyLogLine(line);
            logLine.textContent = line;
            logContainer.appendChild(logLine);
            logContainer.scrollTop = logContainer.scrollHeight;
        }

        function connectStream() {
            const logName = '{{ log_name }}';
            eventSource = new EventSource(`/api/{{ project }}/logs/stream?log=${encodeURIComponent(logName)}`);

            eventSource.onopen = function() {
                statusEl.textContent = 'Connected';
                statusEl.className = 'status connected';
            };

            eventSource.onmessage = function(e) {
                appendLog(e.data);
            };

            eventSource.onerror = function() {
                statusEl.textContent = 'Disconnected';
                statusEl.className = 'status disconnected';
                eventSource.close();
                setTimeout(connectStream, 2000);
            };
        }

        clearBtn.addEventListener('click', function() {
            logContainer.innerHTML = '';
        });

        connectStream();
    </script>
</body>
</html>
"""

    return render_template_string(html, project=project, log_name=log_name)


@app.route('/api/<project>/logs/<path:filename>')
def serve_log_file(project: str, filename: str):
    """Serve complete log file."""
    logs_dir = PROJECT_DIR / project / "logs"
    log_file = logs_dir / filename

    # Security check
    try:
        log_file = log_file.resolve()
        logs_dir_resolved = logs_dir.resolve()
        if not str(log_file).startswith(str(logs_dir_resolved)):
            abort(403, "Access denied")
    except Exception:
        abort(400, "Invalid path")

    if not log_file.exists():
        abort(404, f"Log file not found: {filename}")

    with open(log_file, 'r', encoding='utf-8') as f:
        content = f.read()

    return Response(content, mimetype='text/plain')


@app.route('/api/<project>/logs/stream')
def stream_logs(project: str):
    """Server-Sent Events endpoint for streaming logs."""
    from flask import request

    logs_dir = PROJECT_DIR / project / "logs"

    if not logs_dir.exists():
        abort(404, f"No logs directory for project '{project}'")

    log_name = request.args.get('log')
    if log_name:
        log_file = logs_dir / log_name
        if not log_file.exists():
            abort(404, f"Log file not found: {log_name}")
    else:
        log_files = sorted(
            logs_dir.rglob("*.log"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        if not log_files:
            def generate():
                yield "data: [INFO] Waiting for logs...\n\n"
                while True:
                    time.sleep(1)
            return Response(generate(), mimetype='text/event-stream')
        log_file = log_files[0]

    def generate():
        """Show existing content, then tail for new lines."""
        with open(log_file, 'r', encoding='utf-8') as f:
            for line in f:
                yield f"data: {line.rstrip()}\n\n"
            while True:
                line = f.readline()
                if line:
                    yield f"data: {line.rstrip()}\n\n"
                else:
                    time.sleep(0.5)

    return Response(generate(), mimetype='text/event-stream')


# ============================================================================
# SERVER STARTUP
# ============================================================================

def start_server(port: int = 8000, open_browser: bool = True):
    """Start the Flask server."""
    if open_browser:
        def open_browser_delayed():
            time.sleep(1)
            webbrowser.open(f"http://localhost:{port}/")

        thread = threading.Thread(target=open_browser_delayed, daemon=True)
        thread.start()

    print(f"[INFO] WikiaAnalysis server starting at http://localhost:{port}/")
    print(f"[INFO] Press Ctrl+C to stop")

    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)


if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    start_server(port=port)
