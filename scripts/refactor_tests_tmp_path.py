"""
Helper script to refactor tests to use tmp_path.

This script helps identify tests that need tmp_path parameter added.
"""

import re
from pathlib import Path


def analyze_test_file(file_path):
    """Analyze a test file and report what needs updating."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        lines = content.split('\n')

    print(f"\n{'='*80}")
    print(f"Analyzing: {file_path}")
    print(f"{'='*80}\n")

    # Find all test methods
    test_methods = []
    for i, line in enumerate(lines, 1):
        if re.match(r'\s+def test_\w+\(self', line):
            # Extract test name
            match = re.search(r'def (test_\w+)', line)
            if match:
                test_name = match.group(1)
                # Check if it already has tmp_path
                has_tmp_path = 'tmp_path' in line
                test_methods.append({
                    'name': test_name,
                    'line': i,
                    'has_tmp_path': has_tmp_path,
                    'signature': line.strip()
                })

    # Find Vector Store/Retriever/QueryEngine instantiations
    component_creates = {
        'VectorStore': [],
        'RAGRetriever': [],
        'QueryEngine': [],
        'CharacterExtractor': [],
        'WikiaCrawler': []
    }

    for i, line in enumerate(lines, 1):
        for component in component_creates.keys():
            if f'{component}(project_name=' in line or f'{component}("' in line:
                # Check if persist_directory is already specified
                has_persist_dir = 'persist_directory' in line
                component_creates[component].append({
                    'line': i,
                    'has_persist_dir': has_persist_dir,
                    'code': line.strip()
                })

    # Report
    print(f"Total test methods: {len(test_methods)}")
    print(f"Tests with tmp_path: {sum(1 for t in test_methods if t['has_tmp_path'])}")
    print(f"Tests needing tmp_path: {sum(1 for t in test_methods if not t['has_tmp_path'])}")

    print(f"\n{'-'*80}")
    print("Component instantiations:")
    print(f"{'-'*80}")
    for component, creates in component_creates.items():
        if creates:
            print(f"\n{component}: {len(creates)} instantiations")
            without_persist = [c for c in creates if not c['has_persist_dir']]
            if without_persist:
                print(f"  - {len(without_persist)} need persist_directory parameter")
                for c in without_persist[:5]:  # Show first 5
                    print(f"    Line {c['line']}: {c['code'][:70]}...")

    # Tests needing update
    print(f"\n{'-'*80}")
    print("Tests needing tmp_path parameter:")
    print(f"{'-'*80}")
    for t in test_methods:
        if not t['has_tmp_path']:
            print(f"  Line {t['line']:4d}: {t['name']}")

    return {
        'total_tests': len(test_methods),
        'needs_tmp_path': sum(1 for t in test_methods if not t['has_tmp_path']),
        'component_creates': {k: len([c for c in v if not c['has_persist_dir']])
                             for k, v in component_creates.items()}
    }


if __name__ == "__main__":
    test_files = [
        "tests/test_processor/rag/test_vector_store.py",
        "tests/test_processor/rag/test_retriever.py",
        "tests/test_processor/rag/test_query_engine.py",
        "tests/test_processor/analysis/test_character_extractor.py",
    ]

    total_stats = {
        'total_tests': 0,
        'needs_tmp_path': 0
    }

    for file_path in test_files:
        if Path(file_path).exists():
            stats = analyze_test_file(file_path)
            total_stats['total_tests'] += stats['total_tests']
            total_stats['needs_tmp_path'] += stats['needs_tmp_path']

    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    print(f"Total tests analyzed: {total_stats['total_tests']}")
    print(f"Total tests needing tmp_path: {total_stats['needs_tmp_path']}")
    print(f"Estimated time: {total_stats['needs_tmp_path'] * 1.5:.0f} minutes (@ 1.5 min per test)")
