"""
Save crawled content to file system with proper organization.
"""

from typing import Dict, Any, Optional
from pathlib import Path
import json
import hashlib
from datetime import datetime


class ContentSaver:
    """Manages saving crawled content to organized file structure."""
    
    def __init__(self, project_path: Path):
        """Initialize content saver with project path."""
        if not isinstance(project_path, Path):
            raise TypeError("project_path must be a Path object")
        
        self.project_path = project_path
        self.raw_dir = project_path / "raw"
        self.processed_dir = project_path / "processed"
        self.cache_dir = project_path / "cache"
        
        # Ensure all directories exist
        self._ensure_directory_exists(self.raw_dir)
        self._ensure_directory_exists(self.processed_dir)
        self._ensure_directory_exists(self.cache_dir)
        
        # Initialize index files
        self.page_index_file = self.cache_dir / "page_index.json"
        self.crawl_log_file = self.cache_dir / "crawl_log.json"
    
    def save_page_content(self, url: str, content: Dict[str, Any]) -> Path:
        """Save page content to appropriate file."""
        if not url or not content:
            raise ValueError("URL and content cannot be empty")
        
        # Determine page type and directory
        page_type = content.get('page_type', 'unknown')
        directory = self._get_page_directory(page_type)
        
        # Generate filename and create full path
        filename = self._generate_filename(url, page_type)
        file_path = directory / filename
        
        # Add metadata
        save_data = {
            'url': url,
            'saved_at': datetime.now().isoformat(),
            'content': content
        }
        
        # Save to file
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, indent=2, ensure_ascii=False)
        
        # Update page index
        self.update_page_index({
            'url': url,
            'file_path': str(file_path.relative_to(self.project_path)),
            'page_type': page_type,
            'saved_at': save_data['saved_at']
        })
        
        return file_path
    
    def save_raw_html(self, url: str, html: str) -> Path:
        """Save raw HTML content."""
        if not url or not html:
            raise ValueError("URL and HTML cannot be empty")
        
        # Save to raw directory
        directory = self._get_page_directory('raw')
        filename = self._generate_filename(url, 'raw').replace('.json', '.html')
        file_path = directory / filename
        
        # Save HTML with metadata
        save_data = {
            'url': url,
            'saved_at': datetime.now().isoformat(),
            'html': html
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, indent=2, ensure_ascii=False)
        
        return file_path
    
    def save_extracted_data(self, url: str, data: Dict[str, Any]) -> Path:
        """Save structured extracted data."""
        if not url or not data:
            raise ValueError("URL and data cannot be empty")
        
        # Use save_page_content for structured data
        return self.save_page_content(url, data)
    
    def update_page_index(self, page_info: Dict[str, Any]) -> None:
        """Update the master page index."""
        if not page_info or not page_info.get('url'):
            return
        
        # Load existing index
        index = {}
        if self.page_index_file.exists():
            try:
                with open(self.page_index_file, 'r', encoding='utf-8') as f:
                    index = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                index = {}
        
        # Update index with new page info
        url = page_info['url']
        index[url] = page_info
        
        # Save updated index
        with open(self.page_index_file, 'w', encoding='utf-8') as f:
            json.dump(index, f, indent=2, ensure_ascii=False)
    
    def save_crawl_log_entry(self, entry: Dict[str, Any]) -> None:
        """Save entry to crawl log."""
        if not entry:
            return
        
        # Add timestamp if not present
        if 'timestamp' not in entry:
            entry['timestamp'] = datetime.now().isoformat()
        
        # Load existing log
        log_entries = []
        if self.crawl_log_file.exists():
            try:
                with open(self.crawl_log_file, 'r', encoding='utf-8') as f:
                    log_entries = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                log_entries = []
        
        # Add new entry
        log_entries.append(entry)
        
        # Keep only last 1000 entries to prevent unbounded growth
        if len(log_entries) > 1000:
            log_entries = log_entries[-1000:]
        
        # Save updated log
        with open(self.crawl_log_file, 'w', encoding='utf-8') as f:
            json.dump(log_entries, f, indent=2, ensure_ascii=False)
    
    def get_saved_content(self, url: str) -> Optional[Dict[str, Any]]:
        """Retrieve saved content for URL."""
        if not url:
            return None
        
        # Check page index for file location
        if not self.page_index_file.exists():
            return None
        
        try:
            with open(self.page_index_file, 'r', encoding='utf-8') as f:
                index = json.load(f)
            
            page_info = index.get(url)
            if not page_info:
                return None
            
            # Load content from file
            file_path = self.project_path / page_info['file_path']
            if not file_path.exists():
                return None
            
            with open(file_path, 'r', encoding='utf-8') as f:
                saved_data = json.load(f)
            
            return saved_data.get('content')
        
        except (json.JSONDecodeError, FileNotFoundError, KeyError):
            return None
    
    def content_exists(self, url: str) -> bool:
        """Check if content for URL already exists."""
        if not url:
            return False
        
        if not self.page_index_file.exists():
            return False
        
        try:
            with open(self.page_index_file, 'r', encoding='utf-8') as f:
                index = json.load(f)
            return url in index
        except (json.JSONDecodeError, FileNotFoundError):
            return False
    
    def get_content_stats(self) -> Dict[str, Any]:
        """Get statistics about saved content."""
        stats = {
            'total_pages': 0,
            'by_type': {},
            'total_files': 0
        }
        
        # Count from page index
        if self.page_index_file.exists():
            try:
                with open(self.page_index_file, 'r', encoding='utf-8') as f:
                    index = json.load(f)
                
                stats['total_pages'] = len(index)
                
                # Count by page type
                for page_info in index.values():
                    page_type = page_info.get('page_type', 'unknown')
                    stats['by_type'][page_type] = stats['by_type'].get(page_type, 0) + 1
            
            except (json.JSONDecodeError, FileNotFoundError):
                pass
        
        # Count total files in project
        try:
            def count_files_recursive(path):
                if not path.exists():
                    return 0
                count = 0
                for item in path.iterdir():
                    if item.is_file():
                        count += 1
                    elif item.is_dir():
                        count += count_files_recursive(item)
                return count
            
            stats['total_files'] = count_files_recursive(self.project_path)
        except Exception:
            stats['total_files'] = 0
        
        return stats
    
    def _generate_filename(self, url: str, page_type: str = "page") -> str:
        """Generate safe filename from URL."""
        if not url:
            return "unnamed"
        
        # Create a hash-based filename to avoid filesystem issues
        url_hash = self._url_to_hash(url)
        timestamp = datetime.now().strftime("%Y%m%d")
        
        return f"{page_type}_{url_hash}_{timestamp}.json"
    
    def _get_page_directory(self, page_type: str) -> Path:
        """Get directory path for page type."""
        page_type_dirs = {
            'character': self.processed_dir / 'characters',
            'location': self.processed_dir / 'locations',
            'event': self.processed_dir / 'events',
            'article': self.processed_dir / 'articles',
            'disambiguation': self.processed_dir / 'disambiguation',
            'raw': self.raw_dir,
            'unknown': self.processed_dir / 'unknown'
        }
        
        directory = page_type_dirs.get(page_type, self.processed_dir / 'unknown')
        self._ensure_directory_exists(directory)
        return directory
    
    def _url_to_hash(self, url: str) -> str:
        """Convert URL to consistent hash for filename."""
        if not url:
            return "empty"
        return hashlib.md5(url.encode('utf-8')).hexdigest()
    
    def _ensure_directory_exists(self, directory: Path) -> None:
        """Ensure directory exists, create if needed."""
        directory.mkdir(parents=True, exist_ok=True)