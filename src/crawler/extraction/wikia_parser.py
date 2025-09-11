"""
Wikia/Fandom-specific content parsing and filtering.
"""

from typing import Dict, List, Optional, Set
from bs4 import BeautifulSoup


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
        """Extract Wikia-specific structured content."""
        if not soup:
            return {}
        
        # Clean the soup of wikia navigation
        cleaned_soup = self._clean_wikia_navigation(soup)
        
        result = {
            'url': url,
            'namespace': self.get_page_namespace(url),
            'infobox': self.extract_portable_infobox(cleaned_soup),
            'character_links': self.extract_character_links(cleaned_soup, url),
            'related_articles': self.extract_related_articles(cleaned_soup),
            'categories': self._extract_page_categories(cleaned_soup),
            'is_character_page': self.is_character_page(cleaned_soup, url),
            'is_location_page': self.is_location_page(cleaned_soup, url)
        }
        
        return result
    
    def get_page_namespace(self, url: str) -> Optional[str]:
        """Extract namespace from Wikia URL."""
        if not url:
            return None
        
        import re
        
        # Check each namespace pattern
        for namespace, pattern in self.namespace_patterns.items():
            if re.search(pattern, url, re.IGNORECASE):
                return namespace
        
        # Check for explicit namespace prefixes
        if '/wiki/' in url:
            path_part = url.split('/wiki/')[-1]
            if ':' in path_part:
                potential_namespace = path_part.split(':')[0]
                if potential_namespace in ['Character', 'Location', 'Event', 'Organization']:
                    return potential_namespace
        
        # Default to Main for wiki pages without explicit namespace
        if '/wiki/' in url and not any(exclude in url for exclude in self.exclude_patterns):
            return 'Main'
        
        return None
    
    def extract_character_links(self, soup: BeautifulSoup, base_url: str) -> Set[str]:
        """Find links that likely point to character pages within the same wikia."""
        if not soup or not base_url:
            return set()
        
        character_links = set()
        
        for link_tag in soup.find_all('a', href=True):
            href = link_tag['href']
            link_text = link_tag.get_text(strip=True)
            
            # Skip if not same domain
            if not self._is_same_wikia_domain(href, base_url):
                continue
            
            # Additional check to exclude Fandom meta-domains that might slip through
            from urllib.parse import urlparse
            try:
                href_domain = urlparse(href).netloc.lower() if href.startswith('http') else ''
                fandom_meta_domains = [
                    'community.fandom.com',
                    'fandom.zendesk.com', 
                    'about.fandom.com',
                    'auth.fandom.com'
                ]
                if href_domain in fandom_meta_domains:
                    continue
            except:
                pass
            
            # Skip common non-character pages
            if self._is_excluded_page(href):
                continue
                
            # More precise character detection
            is_character_link = (
                self._has_character_namespace(href) or
                self._has_character_indicators(link_text, href) or
                self._is_likely_character_name(link_text, link_tag)
            )
            
            if is_character_link:
                # Normalize URL to absolute form
                normalized_href = self._normalize_url(href, base_url)
                character_links.add(normalized_href)
        
        return character_links
    
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
    
    def is_character_page(self, soup: BeautifulSoup, url: str) -> bool:
        """Determine if page is about a character."""
        if not soup or not url:
            return False
        
        # Check URL for character namespace
        if '/Character:' in url or '/Characters:' in url:
            return True
        
        # Check page content for character indicators
        page_text = soup.get_text().lower()
        character_indicators = [
            'character', 'person', 'individual', 'protagonist', 'antagonist',
            'born', 'died', 'age', 'occupation', 'affiliation', 'status',
            'family', 'relatives', 'abilities', 'personality'
        ]
        
        indicator_count = sum(1 for indicator in character_indicators if indicator in page_text)
        
        # If multiple character indicators are present, likely a character page
        return indicator_count >= 3
    
    def is_location_page(self, soup: BeautifulSoup, url: str) -> bool:
        """Determine if page is about a location."""
        if not soup or not url:
            return False
        
        # Check URL for location namespace
        if '/Location:' in url or '/Locations:' in url or '/Places:' in url:
            return True
        
        # Check page content for location indicators
        page_text = soup.get_text().lower()
        location_indicators = [
            'location', 'place', 'area', 'region', 'territory', 'zone',
            'city', 'town', 'village', 'country', 'continent', 'planet',
            'located', 'situated', 'geography', 'inhabitants', 'population',
            'climate', 'government', 'notable features'
        ]
        
        indicator_count = sum(1 for indicator in location_indicators if indicator in page_text)
        
        # If multiple location indicators are present, likely a location page
        return indicator_count >= 3
    
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
    
    def _is_excluded_page(self, url: str) -> bool:
        """Check if page matches exclusion patterns."""
        if not url:
            return True
        
        # Check against exclusion patterns
        for pattern in self.exclude_patterns:
            if pattern in url:
                return True
        
        # Also exclude common non-content pages
        exclude_keywords = [
            'Special:', 'File:', 'Image:', 'Media:', 'Template:',
            'User:', 'User_talk:', 'Talk:', 'Category_talk:',
            'action=edit', 'action=history', 'printable=yes'
        ]
        
        return any(keyword in url for keyword in exclude_keywords)
    
    def _clean_wikia_navigation(self, soup: BeautifulSoup) -> BeautifulSoup:
        """Remove Wikia navigation elements."""
        if not soup:
            return soup
        
        # Create a copy to avoid modifying original
        cleaned_soup = BeautifulSoup(str(soup), 'html.parser')
        
        # Remove wikia-specific navigation elements
        for selector in self.wikia_selectors['navigation_elements']:
            for element in cleaned_soup.select(selector):
                element.decompose()
        
        # Remove other common navigation/chrome elements
        chrome_selectors = [
            '.global-navigation', '.fandom-sticky-header', '.page-header__top',
            '.rail', '.right-rail', '.sidebar', '.notifications',
            '.fandom-community-header', '.wikia-bar', '.ads', '.advertisement'
        ]
        
        for selector in chrome_selectors:
            for element in cleaned_soup.select(selector):
                element.decompose()
        
        return cleaned_soup
    
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
        from urllib.parse import urlparse
        
        # Handle relative URLs - they're always same domain
        if href.startswith('/'):
            return True
        
        # Handle fragment-only URLs (#section)
        if href.startswith('#'):
            return True
        
        # Handle protocol-relative URLs
        if href.startswith('//'):
            href = 'https:' + href
        
        try:
            base_domain = urlparse(base_url).netloc.lower()
            href_domain = urlparse(href).netloc.lower()
            
            # Exclude Fandom platform meta-domains
            fandom_meta_domains = [
                'community.fandom.com',
                'fandom.zendesk.com', 
                'about.fandom.com',
                'auth.fandom.com'
            ]
            
            if href_domain in fandom_meta_domains:
                return False
            
            # Exact domain match
            if base_domain == href_domain:
                return True
            
            # Check if both are wikia/fandom domains
            if self._is_wikia_domain(base_domain) and self._is_wikia_domain(href_domain):
                base_wikia = self._extract_wikia_name(base_domain)
                href_wikia = self._extract_wikia_name(href_domain)
                return base_wikia == href_wikia
            
            return False
        except Exception:
            return False
    
    def _has_character_namespace(self, href: str) -> bool:
        """Check if URL has explicit character namespace."""
        character_namespaces = ['/Character:', '/Characters:', '/character:', '/characters:']
        return any(ns in href for ns in character_namespaces)
    
    def _has_character_indicators(self, link_text: str, href: str) -> bool:
        """Check if link has character-related indicators in text or URL."""
        if not link_text:
            return False
        
        text_lower = link_text.lower()
        href_lower = href.lower()
        
        # Skip obvious non-character terms
        non_character_terms = {
            'sitemap', 'community', 'help', 'policy', 'wiki', 'central', 
            'contents', 'editing', 'purge', 'history', 'action=', 'special:',
            'category:', 'file:', 'template:', 'user:'
        }
        
        if any(term in text_lower or term in href_lower for term in non_character_terms):
            return False
        
        # Avoid too broad matches - be more specific
        character_indicators = [
            'characters/', 'character/', 'cast member', 'played by', 'portrayed by'
        ]
        
        return any(indicator in href_lower or indicator in text_lower 
                  for indicator in character_indicators)
    
    def _is_likely_character_name(self, link_text: str, link_tag) -> bool:
        """Analyze context to determine if link likely points to a character."""
        if not link_text or len(link_text.split()) > 3:
            return False
        
        # Skip if it's clearly not a name (contains common non-name words)
        non_name_words = {
            'the', 'and', 'or', 'of', 'in', 'on', 'at', 'to', 'for', 'with', 
            'by', 'from', 'about', 'wiki', 'page', 'category', 'file', 'image',
            'help', 'special', 'user', 'talk', 'template', 'edit', 'history',
            'sitemap', 'community', 'central', 'contents', 'editing', 'policy'
        }
        
        words = link_text.lower().split()
        if any(word in non_name_words for word in words):
            return False
        
        # Check for proper name pattern (capitalized words)
        name_words = link_text.split()
        if not all(word and word[0].isupper() for word in name_words if len(word) > 1):
            return False
        
        # Check surrounding context for character-related terms
        parent = link_tag.parent
        if parent:
            parent_text = parent.get_text().lower()
            character_context = ['character', 'played by', 'portrayed', 'actor', 'actress', 'cast']
            if any(ctx in parent_text for ctx in character_context):
                return True
        
        # Check if in a character-related section
        section_header = self._find_section_header(link_tag)
        if section_header:
            header_text = section_header.get_text().lower()
            if any(keyword in header_text for keyword in ['character', 'cast', 'people', 'main']):
                return True
        
        # If it looks like a proper name and no negative indicators, consider it likely
        return len(name_words) <= 3 and len(link_text) > 3
    
    def _find_section_header(self, element):
        """Find the nearest section header (h1-h6) above the element."""
        current = element.parent
        while current:
            # Check if current element is a heading
            if current.name and current.name.lower() in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                return current
            
            # Look for headings in previous siblings
            for sibling in reversed(list(current.previous_siblings)):
                if hasattr(sibling, 'name') and sibling.name and sibling.name.lower() in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                    return sibling
            
            current = current.parent
        return None
    
    def _normalize_url(self, href: str, base_url: str) -> str:
        """Convert relative URLs to absolute URLs."""
        from urllib.parse import urljoin, urlparse
        
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