#!/usr/bin/env python3
"""
Flask-based visualization server with project listing and live monitoring.

URL Structure:
    /                         - List all projects
    /<project>                - Relationship graph viewer
    /<project>/monitor        - Live log streaming
    /api/<project>/graph      - Graph JSON data
    /api/<project>/relationships/<file> - Relationship details
    /api/<project>/logs/stream - Server-Sent Events log stream
"""
from flask import Flask, render_template_string, jsonify, Response, send_from_directory, abort
from pathlib import Path
import json
import time
import glob
from typing import Dict, List, Optional
import webbrowser
import threading

app = Flask(__name__)
PROJECT_DIR = Path("data/projects")


# ============================================================================
# PROJECT LISTING
# ============================================================================

def get_all_projects() -> List[Dict]:
    """
    Scan data/projects/ and return list of projects with metadata.

    Returns:
        List of project dicts with:
        - name: project name
        - has_graph: bool (graph.json exists)
        - has_characters: bool (characters/ dir exists)
        - character_count: number of character files
        - relationship_count: number from graph.json
        - latest_log: path to most recent log file
    """
    if not PROJECT_DIR.exists():
        return []

    projects = []
    for project_path in PROJECT_DIR.iterdir():
        if not project_path.is_dir():
            continue

        name = project_path.name
        graph_path = project_path / "relationships" / "graph.json"
        chars_dir = project_path / "characters"
        logs_dir = project_path / "logs"

        # Load graph metadata if exists
        relationship_count = 0
        character_count = 0

        if graph_path.exists():
            try:
                with open(graph_path, 'r', encoding='utf-8') as f:
                    graph_data = json.load(f)
                    relationship_count = len(graph_data.get('edges', []))
                    character_count = len(graph_data.get('nodes', []))
            except:
                pass

        # Get character file count if no graph
        if character_count == 0 and chars_dir.exists():
            character_count = len([f for f in chars_dir.glob("*.json") if f.name != "_discovered.json"])

        # Find latest log file (search recursively in subdirectories)
        latest_log = None
        if logs_dir.exists():
            log_files = sorted(logs_dir.rglob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
            if log_files:
                latest_log = str(log_files[0].relative_to(PROJECT_DIR))

        projects.append({
            "name": name,
            "has_graph": graph_path.exists(),
            "has_characters": chars_dir.exists(),
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

        .btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
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
            {% if project.has_graph %}
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
                <a href="/{{ project.name }}" class="btn btn-primary"
                   {% if not project.has_graph %}style="pointer-events: none; opacity: 0.5;"{% endif %}>
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
    graph_path = PROJECT_DIR / project / "relationships" / "graph.json"

    if not graph_path.exists():
        abort(404, f"Project '{project}' has no graph. Run 'python main.py build {project}' first.")

    # Read the viewer.html template
    viewer_path = Path("src/visualizer/viewer.html")
    if not viewer_path.exists():
        abort(500, "viewer.html template not found")

    with open(viewer_path, 'r', encoding='utf-8') as f:
        html = f.read()

    # Inject project name into HTML (replace the query parameter logic)
    html = html.replace('const urlParams = new URLSearchParams(window.location.search);', '')
    html = html.replace("const projectName = urlParams.get('project');", f"const projectName = '{project}';")
    html = html.replace(
        "if (!projectName) {\n            document.body.innerHTML = '<div style=\"padding: 2rem; color: red;\">Error: No project specified. Use ?project=PROJECT_NAME</div>';\n            throw new Error('No project specified');\n        }",
        ""
    )

    # Update API paths to use Flask routes
    html = html.replace(
        'const graphPath = `/data/projects/${projectName}/relationships/graph.json`;',
        'const graphPath = `/api/${projectName}/graph`;'
    )
    html = html.replace(
        'const detailsPath = `/data/projects/${projectName}/relationships/${detailsFile}`;',
        'const detailsPath = `/api/${projectName}/relationships/${detailsFile}`;'
    )

    return render_template_string(html)


# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.route('/api/<project>/graph')
def api_graph(project: str):
    """Serve graph.json for a project."""
    graph_path = PROJECT_DIR / project / "relationships" / "graph.json"

    if not graph_path.exists():
        abort(404, f"Graph not found for project '{project}'")

    with open(graph_path, 'r', encoding='utf-8') as f:
        return jsonify(json.load(f))


@app.route('/api/<project>/relationships/<filename>')
def api_relationship(project: str, filename: str):
    """Serve relationship detail JSON."""
    rel_path = PROJECT_DIR / project / "relationships" / filename

    if not rel_path.exists():
        abort(404, f"Relationship file not found: {filename}")

    with open(rel_path, 'r', encoding='utf-8') as f:
        return jsonify(json.load(f))


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
    log_files = sorted(logs_dir.rglob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)

    # Build log file list with metadata
    logs = []
    for log_file in log_files:
        stat = log_file.stat()
        # Get relative path from logs dir for display (e.g., "crawler/crawler.log" or "main.log")
        rel_path = log_file.relative_to(logs_dir)
        logs.append({
            "name": str(rel_path).replace('\\', '/'),  # Normalize path separators for display
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
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: #f5f5f5;
        }

        .header {
            background: #2c3e50;
            color: white;
            padding: 1rem 2rem;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }

        .header h1 {
            font-size: 1.3rem;
            font-weight: 600;
            margin-bottom: 0.5rem;
        }

        .header .breadcrumb {
            font-size: 0.9rem;
            color: #bdc3c7;
        }

        .header .breadcrumb a {
            color: #3498db;
            text-decoration: none;
        }

        .header .breadcrumb a:hover {
            text-decoration: underline;
        }

        .content {
            padding: 2rem;
            max-width: 1200px;
            margin: 0 auto;
        }

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

        .log-item:hover {
            background: #f8f9fa;
        }

        .log-item:last-child {
            border-bottom: none;
        }

        .log-info {
            flex: 1;
        }

        .log-name {
            font-weight: 600;
            color: #2c3e50;
            margin-bottom: 0.25rem;
        }

        .log-meta {
            font-size: 0.85rem;
            color: #7f8c8d;
        }

        .log-actions {
            display: flex;
            gap: 0.5rem;
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

        .empty-state {
            text-align: center;
            padding: 4rem;
            color: #95a5a6;
        }
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
        # Find most recent log (search recursively)
        log_files = sorted(logs_dir.rglob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not log_files:
            abort(404, f"No log files found for project '{project}'")
        log_file = log_files[0]
        # Get relative path from logs dir for display
        log_name = str(log_file.relative_to(logs_dir)).replace('\\', '/')

    html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ project }} - Live Logs</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

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

        .header h1 {
            font-size: 1.2rem;
            font-weight: 600;
        }

        .header .controls {
            display: flex;
            gap: 0.5rem;
        }

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

        .btn:hover {
            background: #2980b9;
        }

        .btn-secondary {
            background: #95a5a6;
        }

        .btn-secondary:hover {
            background: #7f8c8d;
        }

        .status {
            padding: 0.5rem 1rem;
            border-radius: 4px;
            font-size: 0.85rem;
        }

        .status.connected {
            background: #d4edda;
            color: #155724;
        }

        .status.disconnected {
            background: #f8d7da;
            color: #721c24;
        }

        #log-container {
            flex: 1;
            overflow-y: auto;
            padding: 1rem;
            font-size: 13px;
            line-height: 1.5;
        }

        .log-line {
            padding: 0.25rem 0;
            white-space: pre-wrap;
            word-break: break-word;
        }

        .log-line.info {
            color: #4ec9b0;
        }

        .log-line.warn {
            color: #dcdcaa;
        }

        .log-line.error {
            color: #f48771;
            font-weight: 600;
        }

        .log-line.ok {
            color: #b5cea8;
            font-weight: 600;
        }

        ::-webkit-scrollbar {
            width: 10px;
        }

        ::-webkit-scrollbar-track {
            background: #252526;
        }

        ::-webkit-scrollbar-thumb {
            background: #3e3e42;
        }

        ::-webkit-scrollbar-thumb:hover {
            background: #4e4e52;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>{{ project }} - Live Logs</h1>
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

            // Auto-scroll to bottom
            logContainer.scrollTop = logContainer.scrollHeight;
        }

        function connectStream() {
            const logName = '{{ log_name }}';
            eventSource = new EventSource(`/api/{{ project }}/logs/stream?log=${logName}`);

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

                // Reconnect after 2 seconds
                setTimeout(connectStream, 2000);
            };
        }

        clearBtn.addEventListener('click', function() {
            logContainer.innerHTML = '';
        });

        // Start streaming
        connectStream();
    </script>
</body>
</html>
"""

    return render_template_string(html, project=project, log_name=log_name)


@app.route('/api/<project>/logs/<path:filename>')
def serve_log_file(project: str, filename: str):
    """Serve complete log file (supports subdirectories like crawler/crawler.log)."""
    from flask import request

    logs_dir = PROJECT_DIR / project / "logs"
    log_file = logs_dir / filename

    # Security check: ensure the resolved path is within logs_dir
    try:
        log_file = log_file.resolve()
        logs_dir = logs_dir.resolve()
        if not str(log_file).startswith(str(logs_dir)):
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

    # Get log file from query param or use most recent
    log_name = request.args.get('log')
    if log_name:
        log_file = logs_dir / log_name
        if not log_file.exists():
            abort(404, f"Log file not found: {log_name}")
    else:
        # Find most recent log file (search recursively)
        log_files = sorted(logs_dir.rglob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not log_files:
            # No logs yet, stream waiting message
            def generate():
                yield f"data: [INFO] Waiting for logs...\n\n"
                while True:
                    time.sleep(1)

            return Response(generate(), mimetype='text/event-stream')

        log_file = log_files[0]

    def generate():
        """Show existing content, then tail -f for new lines."""
        with open(log_file, 'r', encoding='utf-8') as f:
            # First, send all existing content
            for line in f:
                yield f"data: {line.rstrip()}\n\n"

            # Then tail for new content
            while True:
                line = f.readline()
                if line:
                    yield f"data: {line.rstrip()}\n\n"
                else:
                    time.sleep(0.5)  # Wait for new data

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
