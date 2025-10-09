"""
Wikia/Fandom-specific content parsing and filtering.
"""

from typing import Dict, List, Optional, Set
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
import re

from ..utils.url_utils import URLUtils


class WikiaParser:
    """Handles Wikia/Fandom-specific content extraction and filtering."""
    
    def __init__(self, target_namespaces: Optional[List[str]] = None, exclude_patterns: Optional[List[str]] = None):
        """Initialize with namespace and exclusion filters."""
        self.target_namespaces = target_namespaces or ['Main', 'Character', 'Location', 'Event', 'Organization']
        self.exclude_patterns = exclude_patterns or [
            'Template:', 'User:', 'File:', 'Category:', 'Help:', 'Special:', 'MediaWiki:',
            'User_talk:', 'Template_talk:', 'File_talk:', 'Help_talk:', 'MediaWiki_talk:'
        ]
        
        # Wikia-specific selectors
        self.wikia_selectors = {
            'portable_infobox': ['.pi-data-label', '.pi-data-value', '.portable-infobox'],
            'standard_infobox': ['.infobox', '.wikitable.infobox'],
            'navigation_elements': ['.wikia-header', '.fandom-community-header', '.global-navigation'],
            'content_area': ['.page-content', '.mw-content-text', '#content', 'main'],
            'categories': ['#catlinks', '.page-footer__categories', '.categories'],
            'related_articles': ['.related-articles', '.see-also', '.references']
        }
        
        # Namespace patterns for URL detection
        self.namespace_patterns = {
            'Main': r'^/wiki/[^:]+$',
            'Character': r'^/wiki/(Character:|Characters:|)',
            'Location': r'^/wiki/(Location:|Locations:|Places:|)',
            'Event': r'^/wiki/(Event:|Events:|)',
            'Organization': r'^/wiki/(Organization:|Organizations:|Faction:|Factions:|)'
        }
    
    def should_crawl_page(self, url: str, soup: Optional[BeautifulSoup] = None) -> bool:
        """Determine if page should be crawled based on URL and content."""
        if not url:
            return False
        
        # Check if URL matches exclusion patterns
        if self._is_excluded_page(url):
            return False
        
        # Check if URL is in target namespaces
        namespace = self.get_page_namespace(url)
        if namespace and namespace not in self.target_namespaces:
            return False
        
        # Additional content-based checks if soup is provided
        if soup:
            # Skip disambiguation pages (typically low value for relationships)
            page_text = soup.get_text().lower()
            if 'disambiguation' in page_text or 'may refer to:' in page_text:
                return False
        
        return True
    
    def extract_wikia_content(self, soup: BeautifulSoup, url: str) -> Dict:
        """Extract Wikia-specific structured content with simplified approach."""
        if not soup:
            return {}
        
        # Clean the soup of wikia navigation
        cleaned_soup = self._clean_wikia_navigation(soup)
        
        result = {
            'url': url,
            'namespace': self.get_page_namespace(url),
            'infobox': self.extract_portable_infobox(cleaned_soup),
            'related_articles': self.extract_related_articles(cleaned_soup),
            'categories': self._extract_page_categories(cleaned_soup)
        }
        
        return result
    
    def get_page_namespace(self, url: str) -> Optional[str]:
        """Extract namespace from Wikia URL."""
        if not url:
            return None
        
        # Check each namespace pattern
        for namespace, pattern in self.namespace_patterns.items():
            if re.search(pattern, url, re.IGNORECASE):
                return namespace
        
        # Check for explicit namespace prefixes
        if '/wiki/' in url:
            path_part = url.split('/wiki/')[-1]
            if ':' in path_part:
                potential_namespace = path_part.split(':')[0]
                if potential_namespace in ['Character', 'Location', 'Event', 'Organization', 'Category', 'Template', 'User', 'Help', 'Special', 'File']:
                    return potential_namespace
        
        # Default to Main for wiki pages without explicit namespace
        if '/wiki/' in url and not any(exclude in url for exclude in self.exclude_patterns):
            return 'Main'
        
        return None
    
    
    def extract_related_articles(self, soup: BeautifulSoup) -> List[str]:
        """Extract related articles section links."""
        if not soup:
            return []
        
        related_links = []
        
        # Look for related articles in common sections
        for selector in self.wikia_selectors['related_articles']:
            section = soup.select_one(selector)
            if section:
                for link in section.find_all('a', href=True):
                    href = link['href']
                    if href.startswith('/wiki/') and href not in related_links:
                        related_links.append(href)
        
        # Also check for "See also" headings
        see_also_headings = soup.find_all(['h2', 'h3', 'h4'], string=lambda text: text and 'see also' in text.lower())
        for heading in see_also_headings:
            # Find links in the section following this heading
            next_sibling = heading.next_sibling
            while next_sibling:
                if hasattr(next_sibling, 'find_all'):
                    for link in next_sibling.find_all('a', href=True):
                        href = link['href']
                        if href.startswith('/wiki/') and href not in related_links:
                            related_links.append(href)
                if next_sibling.name in ['h1', 'h2', 'h3', 'h4']:
                    break  # Stop at next heading
                next_sibling = next_sibling.next_sibling
        
        return related_links[:20]  # Limit to avoid too many

    def extract_portable_infobox(self, soup: BeautifulSoup) -> Dict:
        """Extract data from Wikia's portable infobox format."""
        if not soup:
            return {}
        
        infobox_data = {}
        
        # Try portable infobox first (newer Wikia format)
        for selector in self.wikia_selectors['portable_infobox']:
            infobox = soup.select_one(selector)
            if infobox:
                # Extract data from portable infobox structure
                data_pairs = infobox.select('.pi-item')
                for pair in data_pairs:
                    label_elem = pair.select_one('.pi-data-label')
                    value_elem = pair.select_one('.pi-data-value')
                    
                    if label_elem and value_elem:
                        label = label_elem.get_text(strip=True)
                        value = value_elem.get_text(strip=True)
                        if label and value:
                            infobox_data[label] = value
                
                # If we found portable infobox data, return it
                if infobox_data:
                    return infobox_data
        
        # Fall back to standard infobox format
        for selector in self.wikia_selectors['standard_infobox']:
            infobox = soup.select_one(selector)
            if infobox:
                # Extract from table-based infobox
                rows = infobox.find_all('tr')
                for row in rows:
                    cells = row.find_all(['th', 'td'])
                    if len(cells) >= 2:
                        label = cells[0].get_text(strip=True)
                        value = cells[1].get_text(strip=True)
                        if label and value:
                            infobox_data[label] = value
        
        return infobox_data
    
    
    def _clean_wikia_navigation(self, soup: BeautifulSoup) -> BeautifulSoup:
        """Remove Wikia navigation elements. WARNING: Modifies soup in-place."""
        if not soup:
            return soup
        
        # Remove wikia-specific navigation elements
        for selector in self.wikia_selectors['navigation_elements']:
            for element in soup.select(selector):
                element.decompose()

        # Remove other common navigation/chrome elements
        chrome_selectors = [
            '.global-navigation', '.fandom-sticky-header', '.page-header__top',
            '.rail', '.right-rail', '.sidebar', '.notifications',
            '.fandom-community-header', '.wikia-bar', '.ads', '.advertisement'
        ]

        for selector in chrome_selectors:
            for element in soup.select(selector):
                element.decompose()

        return soup
    
    def _extract_page_categories(self, soup: BeautifulSoup) -> List[str]:
        """Extract Wikia page categories."""
        if not soup:
            return []
        
        categories = []
        
        # Look for categories in various selectors
        for selector in self.wikia_selectors['categories']:
            category_container = soup.select_one(selector)
            if category_container:
                # Extract category links
                for link in category_container.find_all('a', href=True):
                    href = link['href']
                    text = link.get_text(strip=True)
                    
                    # Filter for actual category links
                    if '/wiki/Category:' in href and text:
                        categories.append(text)
        
        return list(set(categories))  # Remove duplicates
    
    def _is_same_wikia_domain(self, href: str, base_url: str) -> bool:
        """Check if href belongs to the same wikia domain as base_url."""
        # Use centralized domain validation from URLUtils
        return URLUtils.is_same_wikia_domain(href, base_url)
    
    
    def _normalize_url(self, href: str, base_url: str) -> str:
        """Convert relative URLs to absolute URLs."""
        # Already absolute
        if href.startswith(('http://', 'https://')):
            return href

        # Protocol-relative URL
        if href.startswith('//'):
            parsed_base = urlparse(base_url)
            return parsed_base.scheme + ':' + href

        # Relative URL
        if href.startswith('/'):
            parsed_base = urlparse(base_url)
            return f"{parsed_base.scheme}://{parsed_base.netloc}{href}"

        # Use urljoin for other cases
        return urljoin(base_url, href)