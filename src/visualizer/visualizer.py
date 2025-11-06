"""
Graph Visualizer - Interactive HTML visualization with local server.
"""
import http.server
import socketserver
import threading
import json
from pathlib import Path
from typing import Optional
import webbrowser
import time


def start_visualization_server(
    project_name: str,
    port: int = 8000,
    open_browser: bool = True
) -> None:
    """
    Start a local HTTP server to serve the visualization.

    Args:
        project_name: Name of the project
        port: Port to run server on (default: 8000)
        open_browser: Whether to open browser automatically

    Raises:
        FileNotFoundError: If graph.json doesn't exist
    """
    # Validate project exists
    project_dir = Path("data/projects") / project_name
    graph_path = project_dir / "relationships" / "graph.json"

    if not graph_path.exists():
        raise FileNotFoundError(
            f"Graph file not found: {graph_path}\n"
            f"Run 'python main.py build {project_name}' first."
        )

    # Create HTML template if it doesn't exist
    _ensure_html_template()

    # Change to data directory for serving
    import os
    original_dir = os.getcwd()

    class CustomHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=original_dir, **kwargs)

        def log_message(self, format, *args):
            # Suppress server logs for cleaner output
            pass

    # Start server in background thread
    def run_server():
        with socketserver.TCPServer(("", port), CustomHandler) as httpd:
            print(f"[INFO] Visualization server running at http://localhost:{port}")
            print(f"[INFO] Serving project: {project_name}")
            print(f"[INFO] Press Ctrl+C to stop the server")
            httpd.serve_forever()

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # Give server time to start
    time.sleep(0.5)

    # Open browser
    url = f"http://localhost:{port}/src/visualizer/viewer.html?project={project_name}"
    if open_browser:
        print(f"[INFO] Opening browser...")
        webbrowser.open(url)
    else:
        print(f"[INFO] Open manually: {url}")

    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[INFO] Server stopped")


def _ensure_html_template() -> None:
    """
    Ensure the viewer.html template exists in src/visualizer/.
    Creates it if missing.
    """
    template_path = Path("src/visualizer/viewer.html")

    if template_path.exists():
        return  # Already exists

    # Create template
    html_content = _get_html_template()

    with open(template_path, "w", encoding="utf-8") as f:
        f.write(html_content)


def _get_html_template() -> str:
    """
    Get HTML template that fetches graph data dynamically.
    """
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Character Relationship Graph</title>
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
        }}

        #header h1 {{
            font-size: 1.5rem;
            font-weight: 600;
        }}

        #header .stats {{
            font-size: 0.9rem;
            color: #bdc3c7;
            margin-top: 0.25rem;
        }}

        #container {{
            display: flex;
            height: calc(100vh - 80px);
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
        }}

        .legend {{
            position: absolute;
            top: 100px;
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
    </style>
</head>
<body>
    <div id="header">
        <h1>Character Relationship Graph</h1>
        <div class="stats">Loading...</div>
    </div>

    <div id="container">
        <div id="graph"></div>
        <div id="details" class="empty">
            Click a character or relationship to see details
        </div>
    </div>

    <div class="legend">
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

    <script>
        // Get project name from URL parameter
        const urlParams = new URLSearchParams(window.location.search);
        const projectName = urlParams.get('project');

        if (!projectName) {{
            document.body.innerHTML = '<div style="padding: 2rem; color: red;">Error: No project specified. Use ?project=PROJECT_NAME</div>';
            throw new Error('No project specified');
        }}

        // Global data
        let graphData = null;
        let relationshipDetailsCache = {{}};

        // Color mapping for relationship types
        const typeColors = {{
            'romantic_partner': '#e74c3c',
            'ex_romantic_partner': '#e74c3c',
            'family': '#3498db',
            'friend': '#2ecc71',
            'mentor': '#f39c12',
            'mentor_supporter': '#f39c12',
            'enemy': '#9b59b6',
            'rival': '#9b59b6',
            'ally': '#2ecc71',
            'default': '#95a5a6'
        }};

        // Initialize visualization
        async function init() {{
            try {{
                // Fetch graph data
                const graphPath = `/data/projects/${{projectName}}/relationships/graph.json`;
                const response = await fetch(graphPath);

                if (!response.ok) {{
                    throw new Error(`Failed to load graph: ${{response.statusText}}`);
                }}

                graphData = await response.json();

                // Update header
                document.querySelector('#header h1').textContent = `${{projectName}} - Character Relationship Graph`;
                document.querySelector('.stats').textContent = `${{graphData.nodes.length}} characters, ${{graphData.edges.length}} relationships`;

                // Build visualization
                buildGraph();

            }} catch (error) {{
                console.error('Error loading graph:', error);
                document.body.innerHTML = `<div style="padding: 2rem; color: red;">Error loading graph: ${{error.message}}</div>`;
            }}
        }}

        function buildGraph() {{
            // Prepare nodes
            const nodes = graphData.nodes.map(node => ({{
            id: node.id,
            label: node.full_name || node.id,
            title: `${{node.full_name || node.id}}\\n${{node.total_relationships}} relationships`,
            color: {{
                background: '#3498db',
                border: '#2980b9',
                highlight: {{
                    background: '#2980b9',
                    border: '#1f5f8b'
                }}
            }},
            font: {{
                color: '#fff',
                size: 14
            }},
            shape: 'box',
            margin: 10,
            data: node
        }}));

        // Prepare edges
        const edges = graphData.edges.map((edge, index) => ({{
            id: `edge_${{index}}`,
            from: edge.from,
            to: edge.to,
            label: edge.type.replace(/_/g, ' '),
            title: edge.summary,
            color: {{
                color: typeColors[edge.type] || typeColors.default,
                highlight: typeColors[edge.type] || typeColors.default
            }},
            arrows: 'to',
            font: {{
                align: 'top',
                size: 10
            }},
            data: edge
        }}));

        // Create network
        const container = document.getElementById('graph');
        const data = {{
            nodes: new vis.DataSet(nodes),
            edges: new vis.DataSet(edges)
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
                width: 2,
                smooth: {{
                    type: 'continuous'
                }}
            }}
        }};

        const network = new vis.Network(container, data, options);

        // Update stats
        document.querySelector('.stats').textContent =
            `${{graphData.nodes.length}} characters, ${{graphData.edges.length}} relationships`;

            // Handle node clicks
            network.on('click', function(params) {{
                if (params.nodes.length > 0) {{
                    const nodeId = params.nodes[0];
                    const node = nodes.find(n => n.id === nodeId);
                    showNodeDetails(node);
                }} else if (params.edges.length > 0) {{
                    const edgeId = params.edges[0];
                    const edge = edges.find(e => e.id === edgeId);
                    showEdgeDetails(edge);
                }}
            }});
        }}

        function showNodeDetails(node) {{
            const detailsDiv = document.getElementById('details');
            detailsDiv.classList.remove('empty');

            // Find all relationships for this character
            const outgoing = graphData.edges.filter(e => e.from === node.id);
            const incoming = graphData.edges.filter(e => e.to === node.id);

            let html = `
                <div class="detail-section">
                    <h2>${{node.data.full_name || node.id}}</h2>
                    <div class="stats-badge">Source: <a href="${{node.data.source_url}}" target="_blank">Wiki Page</a></div>
                    <div class="stats-badge">${{node.data.total_relationships}} relationships</div>
                </div>
            `;

            if (outgoing.length > 0) {{
                html += '<div class="detail-section"><h3>Relationships</h3>';
                outgoing.forEach(edge => {{
                    html += `
                        <div class="claim">
                            <strong>${{edge.to}}</strong>
                            <span class="relationship-type">${{edge.type.replace(/_/g, ' ')}}</span>
                            <div>${{edge.summary}}</div>
                            <div style="margin-top: 0.5rem; font-size: 0.85rem;">
                                Confidence: <span class="confidence">${{(edge.confidence * 100).toFixed(0)}}%</span>
                                | Evidence: ${{edge.evidence_count}} citations
                            </div>
                        </div>
                    `;
                }});
                html += '</div>';
            }}

            if (incoming.length > 0) {{
                html += '<div class="detail-section"><h3>Mentioned By</h3>';
                incoming.forEach(edge => {{
                    html += `
                        <div class="claim">
                            <strong>${{edge.from}}</strong>
                            <span class="relationship-type">${{edge.type.replace(/_/g, ' ')}}</span>
                            <div>${{edge.summary}}</div>
                        </div>
                    `;
                }});
                html += '</div>';
            }}

            detailsDiv.innerHTML = html;
        }}

        async function showEdgeDetails(edge) {{
            const detailsDiv = document.getElementById('details');
            detailsDiv.classList.remove('empty');

            // Show loading state
            detailsDiv.innerHTML = '<div style="padding: 2rem;">Loading relationship details...</div>';

            const detailsFile = edge.data.details_file;

            // Check cache first
            let details = relationshipDetailsCache[detailsFile];

            // Fetch if not cached
            if (!details) {{
                try {{
                    const detailsPath = `/data/projects/${{projectName}}/relationships/${{detailsFile}}`;
                    const response = await fetch(detailsPath);

                    if (!response.ok) {{
                        throw new Error(`Failed to load details: ${{response.statusText}}`);
                    }}

                    details = await response.json();
                    relationshipDetailsCache[detailsFile] = details;

                }} catch (error) {{
                    console.error('Error loading relationship details:', error);
                    detailsDiv.innerHTML = `<div style="padding: 2rem; color: red;">Error: ${{error.message}}</div>`;
                    return;
                }}
            }}

            let html = `
                <div class="detail-section">
                    <h2>${{edge.data.from}} → ${{edge.data.to}}</h2>
                    <span class="relationship-type">${{edge.data.type.replace(/_/g, ' ')}}</span>
                    <div style="margin-top: 1rem;">${{edge.data.summary}}</div>
                    <div style="margin-top: 0.5rem;">
                        <span class="stats-badge">Confidence: <span class="confidence">${{(edge.data.confidence * 100).toFixed(0)}}%</span></span>
                        <span class="stats-badge">Evidence: ${{edge.data.evidence_count}} citations</span>
                    </div>
                </div>
            `;

            if (details && details.narrative && details.narrative.claims_with_evidence) {{
                html += '<div class="detail-section"><h3>Detailed Claims</h3>';

                details.narrative.claims_with_evidence.forEach((claimObj, idx) => {{
                    html += `
                        <div class="claim">
                            <strong>Claim ${{idx + 1}}:</strong> ${{claimObj.claim}}
                            <div class="evidence">
                                <strong>Evidence (${{claimObj.evidence.length}} sources):</strong>
                    `;

                    // Show first 3 evidence sources
                    const evidenceToShow = claimObj.evidence.slice(0, 3);
                    evidenceToShow.forEach(ev => {{
                        html += `
                            <div class="evidence-item">
                                "${{ev.cited_text.substring(0, 150)}}..."
                                <div class="evidence-source">
                                    <a href="${{ev.source_url}}" target="_blank">${{ev.page_title}}</a>
                                </div>
                            </div>
                        `;
                    }});

                    if (claimObj.evidence.length > 3) {{
                        html += `<div style="margin-top: 0.5rem; font-style: italic;">+ ${{claimObj.evidence.length - 3}} more sources</div>`;
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
</html>"""


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python visualizer.py <project_name>")
        sys.exit(1)

    project = sys.argv[1]
    output = generate_visualization(project)
    print(f"Visualization generated: {output}")
