"""
Content filtering and cleaning utilities.
"""

from typing import List, Set, Optional
import re
from bs4 import BeautifulSoup


class ContentFilter:
    """Utilities for filtering and cleaning web content."""
    
    def __init__(self, custom_filters: Optional[List[str]] = None, custom_selectors: Optional[dict] = None):
        """Initialize ContentFilter with optional custom configuration."""
        # Default CSS selectors for removing unwanted elements
        self.removal_selectors = {
            'navigation': ['nav', '.nav', '.navigation', '.navbar', '.menu', '.wikia-nav'],
            'sidebar': ['.sidebar', '.rail', '.right-rail', '.left-rail', '.side-panel'],
            'ads': ['.ad', '.advertisement', '.ads', '.sponsored', '.promo'],
            'footer': ['footer', '.footer', '.wikia-footer'],
            'scripts': ['script', 'style', 'noscript'],
            'wikia_chrome': ['.wikia-header', '.wikia-footer', '.global-navigation', '.fandom-community-header']
        }
        
        # Default filters for text content
        self.text_filters = [
            r'\{\{[^}]+\}\}',  # Remove wiki templates
            r'\[\[[^]]+\]\]',  # Remove wiki links  
            r'\[[\d\s,]+\]',   # Remove citations [1], [2,3]
            r'<[^>]+>',        # Remove any remaining HTML tags
        ]
        
        # Apply custom configurations if provided
        if custom_selectors:
            self.removal_selectors.update(custom_selectors)
            
        if custom_filters:
            self.text_filters.extend(custom_filters)
    
    def remove_navigation_elements(self, soup: BeautifulSoup) -> BeautifulSoup:
        """Remove navigation, menu, and sidebar elements. WARNING: Modifies soup in-place."""
        # Remove navigation elements
        for selector in self.removal_selectors.get('navigation', []):
            for element in soup.select(selector):
                element.decompose()

        return soup
    
    def remove_wikia_chrome(self, soup: BeautifulSoup) -> BeautifulSoup:
        """Remove Wikia-specific UI elements (ads, rails, etc.). WARNING: Modifies soup in-place."""
        # Remove wikia chrome elements
        for selector in self.removal_selectors.get('wikia_chrome', []):
            for element in soup.select(selector):
                element.decompose()

        # Remove ads
        for selector in self.removal_selectors.get('ads', []):
            for element in soup.select(selector):
                element.decompose()

        # Remove sidebar/rails
        for selector in self.removal_selectors.get('sidebar', []):
            for element in soup.select(selector):
                element.decompose()

        return soup
    
    def extract_main_content_area(self, soup: BeautifulSoup) -> Optional[BeautifulSoup]:
        """Extract the main content area from page."""
        # Try common content selectors in order of preference
        content_selectors = [
            'main',
            '.main-content', 
            '.page-content',
            '.content',
            '#content',
            '.mw-content-text',
            '.entry-content',
            'article'
        ]
        
        for selector in content_selectors:
            content_area = soup.select_one(selector)
            if content_area:
                return BeautifulSoup(str(content_area), 'html.parser')
        
        # If no specific content area found, return the body minus unwanted elements
        body = soup.select_one('body')
        if body:
            body_copy = BeautifulSoup(str(body), 'html.parser')
            # Remove unwanted elements from body
            body_copy = self.remove_navigation_elements(body_copy)
            body_copy = self.remove_wikia_chrome(body_copy)
            return body_copy
            
        return None
    
    def clean_text_content(self, text: str) -> str:
        """Clean and normalize text content."""
        if not text:
            return ""
        
        # Apply all text filters
        cleaned = text
        for pattern in self.text_filters:
            cleaned = re.sub(pattern, '', cleaned, flags=re.MULTILINE | re.DOTALL)
        
        # Normalize whitespace
        cleaned = self.normalize_whitespace(cleaned)
        
        return cleaned.strip()
    
    def remove_wiki_templates(self, text: str) -> str:
        """Remove wiki template markup."""
        if not text:
            return ""
        
        # Remove {{template}} patterns
        cleaned = re.sub(r'\{\{[^}]+\}\}', '', text, flags=re.MULTILINE | re.DOTALL)
        return cleaned.strip()
    
    def filter_useful_links(self, links: List[str], base_url: str) -> List[str]:
        """Filter links to keep only useful ones for crawling."""
        if not links:
            return []
        
        useful_links = []
        for link in links:
            if self._is_useful_link(link, base_url):
                useful_links.append(link)
        
        return useful_links
    
    def _is_useful_link(self, link: str, base_url: str) -> bool:
        """Check if a link is useful for crawling."""
        if not link:
            return False
        
        # Skip external links, javascript, etc.
        if link.startswith(('javascript:', 'mailto:', 'tel:', '#')):
            return False
        
        # Skip common non-content file extensions
        skip_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.pdf', '.css', '.js', '.ico'}
        if any(link.lower().endswith(ext) for ext in skip_extensions):
            return False
        
        # Skip common wiki utility pages
        skip_patterns = [
            '/wiki/Special:', '/wiki/User:', '/wiki/File:', '/wiki/Category:',
            '/wiki/Template:', '/wiki/Help:', '/wiki/MediaWiki:',
            'action=edit', 'action=history', 'printable=yes'
        ]
        if any(pattern in link for pattern in skip_patterns):
            return False
        
        return True
    
    def is_content_page(self, soup: BeautifulSoup, url: str) -> bool:
        """Determine if page contains substantial content."""
        # Get main content area
        main_content = self.extract_main_content_area(soup)
        if not main_content:
            return False
        
        # Extract text and check if it meets minimum requirements
        text = self.extract_meaningful_text(main_content, min_length=100)
        return text is not None and len(text.strip()) >= 100
    
    def extract_meaningful_text(self, soup: BeautifulSoup, min_length: int = 100) -> Optional[str]:
        """Extract meaningful text content above minimum length. WARNING: Modifies soup in-place."""
        # Remove scripts, styles, and other non-content elements
        for selector in self.removal_selectors.get('scripts', []):
            for element in soup.select(selector):
                element.decompose()

        # Get text content
        text = soup.get_text(separator=' ')
        
        # Clean the text
        cleaned_text = self.clean_text_content(text)
        
        # Check if it meets minimum length requirement
        if len(cleaned_text.strip()) >= min_length:
            return cleaned_text
        
        return None
    
    def remove_citations(self, text: str) -> str:
        """Remove citation markers and references."""
        if not text:
            return ""
        
        # Remove citation markers like [1], [2,3], [cite needed]
        citation_patterns = [
            r'\[\d+\]',            # [1], [2]
            r'\[\d+[,\s]+\d+\]',   # [1,2], [1 2]
            r'\[[^\]]*cite[^\]]*\]', # [citation needed], [cite news]
            r'\[[^\]]*source[^\]]*\]', # [source needed]
        ]
        
        cleaned = text
        for pattern in citation_patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
        
        return cleaned.strip()
    
    def normalize_whitespace(self, text: str) -> str:
        """Normalize whitespace in text content."""
        if not text:
            return ""
        
        # Replace multiple whitespace with single space
        normalized = re.sub(r'\s+', ' ', text)
        
        # Remove leading/trailing whitespace from each line
        lines = [line.strip() for line in normalized.split('\n')]
        
        # Remove empty lines and rejoin
        cleaned_lines = [line for line in lines if line]
        
        return '\n'.join(cleaned_lines).strip()