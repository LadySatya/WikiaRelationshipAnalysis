# Implementation Plan: Extract Real Wikia Content

## 🎯 Goal: Get Real Content Extraction Working

**Objective**: Make the WikiaCrawler actually extract and save real content from wikia pages so you can examine extracted data locally.

## 🔍 Current Status Analysis

### ✅ **GOOD NEWS: Most Components Already Implemented!**

**Fully Implemented Components:**
- ✅ `PageExtractor` - Complete HTML parsing with title, content, links, infobox extraction
- ✅ `ContentSaver` - Complete file saving with organized directory structure  
- ✅ `WikiaCrawler` - Infrastructure, rate limiting, project management
- ✅ `SessionManager` - HTTP requests and session handling
- ✅ `URLManager` - Queue management and URL tracking

**Missing Connection:** Only `WikiaCrawler._crawl_page()` method needs implementation to connect the components!

## 📋 Implementation Plan

### Phase 1: Connect Extraction Pipeline (30 minutes)
**Status: CRITICAL - This enables real content extraction**

#### Task 1.1: Implement `_crawl_page` Method
**File**: `src/crawler/core/crawler.py`
**Lines**: 234-238 (replace the stub)

```python
async def _crawl_page(self, url: str) -> Optional[Dict]:
    """Crawl a single page and return extracted data."""
    try:
        # Fetch HTML content
        async with self.session_manager.get_session() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    html = await response.text()
                    
                    # Extract content using PageExtractor
                    if not hasattr(self, '_page_extractor'):
                        from ..extraction.page_extractor import PageExtractor
                        self._page_extractor = PageExtractor()
                    
                    extracted_data = self._page_extractor.extract_content(html, url)
                    
                    # Save content using ContentSaver
                    if extracted_data and extracted_data.get('main_content'):
                        file_path = self.content_saver.save_page_content(url, extracted_data)
                        extracted_data['saved_to'] = str(file_path)
                        return extracted_data
                    
    except Exception as e:
        logging.error(f"Error crawling {url}: {e}")
    
    return None
```

#### Task 1.2: Add Missing Import
**File**: `src/crawler/core/crawler.py`
**Add to imports section** (around line 12):
```python
from ..extraction.page_extractor import PageExtractor
```

**Estimated Time**: 15 minutes
**Test**: `python test_crawl.py` should show `pages_crawled > 0`

### Phase 2: Implement Working CLI (20 minutes)  
**Status: HIGH PRIORITY - Makes the system usable**

#### Task 2.1: Implement `main.py`
**File**: `main.py`
**Replace entire file with working implementation**

#### Task 2.2: Implement `scripts/crawl_wikia.py`
**File**: `scripts/crawl_wikia.py`  
**Replace stub functions with real implementations**

**Estimated Time**: 20 minutes
**Test**: `python main.py crawl test https://avatar.fandom.com/ --max-pages 3`

### Phase 3: Improve Content Storage (15 minutes)
**Status: NICE TO HAVE - Better organization of extracted data**

#### Task 3.1: Add Content Viewing Script
Create `view_content.py` to easily browse extracted content

#### Task 3.2: Add Content Export
Add JSON/CSV export functionality for extracted data

**Estimated Time**: 15 minutes

## 🚀 Quick Start Implementation

### **PRIORITY 1: Get Content Extraction Working (15 minutes)**

1. **Update `_crawl_page` method** in `src/crawler/core/crawler.py`:
   - Lines 234-238: Replace `return None` with extraction logic
   - Add PageExtractor import

2. **Test immediately**:
   ```bash
   python test_crawl.py
   # Should show: pages_crawled > 0, errors = 0
   ```

3. **Check extracted content**:
   ```bash
   ls data/projects/avatar_test/raw/pages/
   cat data/projects/avatar_test/raw/pages/characters/*.json
   ```

### **PRIORITY 2: Get CLI Working (20 minutes)**

1. **Implement `main.py`** - Replace stub with working interface
2. **Test CLI**:
   ```bash
   python main.py crawl my_test https://avatar.fandom.com/wiki/Avatar_Wiki --max-pages 5
   python main.py status my_test
   ```

## 🔧 Detailed Implementation Guide

### Step 1: Fix `_crawl_page` Method

**Current Code** (lines 234-238 in `src/crawler/core/crawler.py`):
```python
async def _crawl_page(self, url: str) -> Optional[Dict]:
    """Crawl a single page and return extracted data."""
    # This method will be implemented when we work on the extraction pipeline
    # For now, return None to indicate no data extracted
    return None
```

**Replace With**:
```python
async def _crawl_page(self, url: str) -> Optional[Dict]:
    """Crawl a single page and return extracted data."""
    try:
        # Fetch HTML content using existing session manager
        async with self.session_manager.get_session() as session:
            async with session.get(url, timeout=self.timeout_seconds) as response:
                if response.status != 200:
                    logging.warning(f"HTTP {response.status} for {url}")
                    return None
                
                html = await response.text()
                if not html:
                    return None
                
                # Initialize PageExtractor if not exists
                if not hasattr(self, '_page_extractor'):
                    from ..extraction.page_extractor import PageExtractor
                    self._page_extractor = PageExtractor()
                
                # Extract structured content
                extracted_data = self._page_extractor.extract_content(html, url)
                
                # Validate content quality
                if not extracted_data or not extracted_data.get('main_content'):
                    return None
                
                # Save content to file system
                try:
                    file_path = self.content_saver.save_page_content(url, extracted_data)
                    extracted_data['saved_to'] = str(file_path)
                    logging.info(f"Saved page content: {file_path}")
                except Exception as save_error:
                    logging.error(f"Failed to save content for {url}: {save_error}")
                
                return extracted_data
                
    except Exception as e:
        logging.error(f"Error crawling {url}: {e}")
        return None
```

### Step 2: Test Content Extraction

**Run Test**:
```bash
python test_crawl.py
```

**Expected New Output**:
```
=== CRAWL COMPLETED ===
Pages attempted: 1
Pages crawled: 1    # <-- Should be 1 now, not 0
Errors: 0           # <-- Should be 0 now, not 1
Duration: 2.34s
URLs in queue: 0
```

**Check Saved Content**:
```bash
# View directory structure
find data/projects/avatar_test/raw/pages/ -name "*.json"

# View extracted content
cat data/projects/avatar_test/raw/pages/articles/avatar_wiki_*.json | jq .
```

### Step 3: Implement Working CLI

**Create `working_main.py`** (then rename to `main.py`):

```python
#!/usr/bin/env python3
"""
Working main entry point for WikiaAnalyzer application.
"""

import argparse
import asyncio
import sys
from pathlib import Path
import yaml

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from crawler.core.crawler import WikiaCrawler


def load_config() -> dict:
    """Load crawler configuration."""
    config_path = Path("config/crawler_config.yaml")
    with open(config_path, 'r') as f:
        full_config = yaml.safe_load(f)
    
    return {
        'respect_robots_txt': full_config['crawler']['respect_robots_txt'],
        'user_agent': full_config['crawler']['user_agent'],
        'default_delay_seconds': full_config['crawler']['default_delay_seconds'],
        'max_requests_per_minute': full_config['crawler']['max_requests_per_minute'],
        'target_namespaces': full_config['crawler']['target_namespaces'],
        'timeout_seconds': full_config['crawler']['timeout_seconds'],
        'max_retries': full_config['crawler']['max_retries'],
        'exclude_patterns': full_config['crawler']['exclude_patterns'],
        'save_state_every_n_pages': full_config['crawler']['save_state_every_n_pages'],
    }


async def crawl_command(args):
    """Execute crawl command."""
    print(f"Starting crawl of {args.wikia_url} for project '{args.project_name}'")
    print(f"Max pages: {args.max_pages or 'unlimited'}")
    
    config = load_config()
    crawler = WikiaCrawler(args.project_name, config)
    
    start_urls = [args.wikia_url]
    stats = await crawler.crawl_wikia(start_urls, max_pages=args.max_pages)
    
    print(f"\n=== CRAWL COMPLETED ===")
    print(f"Pages crawled: {stats['pages_crawled']}")
    print(f"Errors: {stats['errors']}")
    print(f"Duration: {stats['duration_seconds']:.2f}s")
    print(f"Project saved to: {crawler.project_path}")


def status_command(args):
    """Show project status."""
    project_path = Path(f"data/projects/{args.project_name}")
    if not project_path.exists():
        print(f"Project '{args.project_name}' not found")
        return
    
    # Count files
    raw_files = list((project_path / "raw/pages").rglob("*.json"))
    print(f"Project: {args.project_name}")
    print(f"Location: {project_path}")
    print(f"Pages saved: {len(raw_files)}")


def list_command(args):
    """List all projects."""
    projects_dir = Path("data/projects")
    if not projects_dir.exists():
        print("No projects found")
        return
    
    projects = [d.name for d in projects_dir.iterdir() if d.is_dir()]
    print("Available projects:")
    for project in projects:
        print(f"  - {project}")


async def main():
    """Main application entry point."""
    parser = argparse.ArgumentParser(description="WikiaAnalyzer - Extract character relationships")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Crawl command
    crawl_parser = subparsers.add_parser("crawl", help="Start crawling a wikia")
    crawl_parser.add_argument("project_name", help="Name for this project")
    crawl_parser.add_argument("wikia_url", help="Base URL of wikia to crawl")
    crawl_parser.add_argument("--max-pages", type=int, help="Maximum pages to crawl")
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Show project status")
    status_parser.add_argument("project_name", help="Project to check")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List all projects")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    if args.command == "crawl":
        await crawl_command(args)
    elif args.command == "status":
        status_command(args)
    elif args.command == "list":
        list_command(args)


if __name__ == "__main__":
    asyncio.run(main())
```

## 🧪 Testing Strategy

### Test 1: Content Extraction
```bash
python test_crawl.py
# Verify: pages_crawled > 0, check saved files
```

### Test 2: CLI Interface  
```bash
python main.py crawl avatar_small https://avatar.fandom.com/wiki/Avatar_Wiki --max-pages 3
python main.py status avatar_small
python main.py list
```

### Test 3: Content Viewing
```bash
# View extracted content structure
find data/projects/ -name "*.json" -exec head -20 {} \;

# Pretty print content
cat data/projects/avatar_small/raw/pages/articles/*.json | jq '.' | head -50
```

## 📁 Expected File Structure After Implementation

```
data/projects/avatar_small/
├── raw/pages/
│   ├── articles/
│   │   └── avatar_wiki_[hash].json    # Main page content
│   ├── characters/                     # Character pages (if found)
│   └── locations/                      # Location pages (if found)
├── cache/
│   ├── page_index.json                # Index of saved pages
│   └── crawl_log.json                 # Crawl activity log
└── crawl_state/                       # (Future: state persistence)
```

## 🎯 Success Criteria

### ✅ Phase 1 Success:
- `python test_crawl.py` shows `pages_crawled > 0`
- JSON files appear in `data/projects/avatar_test/raw/pages/`
- JSON contains actual page content with title, text, links

### ✅ Phase 2 Success:
- `python main.py crawl test https://avatar.fandom.com/ --max-pages 3` works
- `python main.py status test` shows project info
- `python main.py list` shows available projects

### 🎉 Final Success:
You can browse real wikia content locally in organized JSON files and use the CLI to crawl any wikia site!

## ⏱️ Time Estimate
- **Phase 1**: 15 minutes (critical - enables content extraction)
- **Phase 2**: 20 minutes (high value - makes system usable)  
- **Total**: 35 minutes to get fully working content extraction

**Priority Order**: Phase 1 → Test → Phase 2 → Test → Done!