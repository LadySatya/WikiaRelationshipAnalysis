"""
HTML parsing and text content extraction from web pages.
"""

from typing import Dict, List, Optional

from bs4 import BeautifulSoup


class PageExtractor:
    """Extracts structured content from HTML pages."""

    def __init__(self, config: Optional[Dict] = None):
        """Initialize extractor with configuration."""
        self.config = config or self._get_default_config()

    def _get_default_config(self) -> Dict:
        """Get default configuration for PageExtractor."""
        return {
            "title_selectors": ["title", "h1", ".page-title", ".title"],
            "content_selectors": [
                "main",
                ".main-content",
                ".page-content",
                ".content",
                "#content",
                ".mw-content-text",
                ".entry-content",
                "article",
            ],
            "ignore_selectors": [
                "nav",
                ".nav",
                ".navigation",
                ".sidebar",
                ".rail",
                "footer",
                ".footer",
                "script",
                "style",
                ".ad",
                ".advertisement",
            ],
            "infobox_selectors": [".infobox", ".wikitable", ".character-info"],
            "min_content_length": 50,
        }

    def extract_content(self, html: str, url: str) -> Dict:
        """Extract structured content from HTML."""
        if not html:
            return {}

        soup = BeautifulSoup(html, "html.parser")

        result = {
            "url": url,
            "title": self.extract_title(soup),
            "main_content": self.extract_main_content(soup),
            "links": self.extract_links(soup, url),
            "infobox_data": self.extract_infobox_data(soup),
            "is_disambiguation": self.is_disambiguation_page(soup),
        }

        return result

    def extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract page title from HTML."""
        if not soup:
            return None

        # Try each title selector in order
        for selector in self.config.get("title_selectors", ["title"]):
            element = soup.select_one(selector)
            if element:
                title = element.get_text(strip=True)
                if title:
                    return self._clean_text(title)

        return None

    def extract_main_content(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract main text content, removing navigation and sidebars."""
        if not soup:
            return None

        # Make a copy to avoid modifying the original
        soup_copy = BeautifulSoup(str(soup), "html.parser")

        # Remove unwanted elements
        for selector in self.config.get("ignore_selectors", []):
            for element in soup_copy.select(selector):
                element.decompose()

        # Try to find main content area
        for selector in self.config.get("content_selectors", ["body"]):
            content_element = soup_copy.select_one(selector)
            if content_element:
                text = content_element.get_text(separator=" ", strip=True)
                cleaned_text = self._clean_text(text)

                # Check minimum length
                min_length = self.config.get("min_content_length", 50)
                if len(cleaned_text) >= min_length:
                    return cleaned_text

        return None

    def extract_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extract links from same wikia domain only."""
        if not soup:
            return []

        from ..utils.url_utils import URLUtils

        links = []
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if href and not href.startswith("#"):
                # Convert relative URLs to absolute
                if href.startswith("/"):
                    from urllib.parse import urljoin

                    href = urljoin(base_url, href)
                elif not href.startswith(("http:", "https:")):
                    from urllib.parse import urljoin

                    href = urljoin(base_url, href)

                # Only keep links from same wikia domain
                if URLUtils.is_same_wikia_domain(href, base_url):
                    links.append(href)

        return list(set(links))  # Remove duplicates

    def extract_infobox_data(self, soup: BeautifulSoup) -> Dict:
        """Extract infobox data if present."""
        if not soup:
            return {}

        infobox_data = {}

        # Try infobox selectors
        for selector in self.config.get("infobox_selectors", []):
            infobox = soup.select_one(selector)
            if infobox:
                # Look for table rows or definition list items
                rows = infobox.find_all(["tr", "dt", "dd"])

                current_key = None
                for row in rows:
                    if row.name == "tr":
                        cells = row.find_all(["th", "td"])
                        if len(cells) >= 2:
                            key = cells[0].get_text(strip=True)
                            value = cells[1].get_text(strip=True)
                            if key and value:
                                infobox_data[key] = self._clean_text(value)
                    elif row.name == "dt":
                        current_key = row.get_text(strip=True)
                    elif row.name == "dd" and current_key:
                        value = row.get_text(strip=True)
                        if value:
                            infobox_data[current_key] = self._clean_text(value)
                        current_key = None

                break  # Use first found infobox

        return infobox_data

    def is_disambiguation_page(self, soup: BeautifulSoup) -> bool:
        """Check if page is a disambiguation page."""
        if not soup:
            return False

        # Check for disambiguation indicators
        page_text = soup.get_text().lower()

        disambiguation_indicators = [
            "disambiguation",
            "may refer to:",
            "can refer to:",
            "might refer to:",
            "this article is about",
        ]

        return any(indicator in page_text
                   for indicator in disambiguation_indicators)

    def _clean_text(self, text: str) -> str:
        """Clean and normalize extracted text."""
        if not text:
            return ""

        # Remove wiki markup
        cleaned = self._remove_wiki_markup(text)

        # Normalize whitespace
        import re

        cleaned = re.sub(r"\s+", " ", cleaned)
        cleaned = re.sub(r"\n\s*\n", "\n", cleaned)

        return cleaned.strip()

    def _remove_wiki_markup(self, text: str) -> str:
        """Remove wiki-specific markup from text."""
        if not text:
            return ""

        import re

        # Remove wiki templates {{...}}
        text = re.sub(r"\{\{[^}]*\}\}", "", text)

        # Remove wiki links [[...]] but keep the display text
        text = re.sub(
            r"\[\[([^|\]]+)\|([^\]]+)\]\]", r"\2", text
        )  # [[link|display]] -> display
        text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)  # [[link]] -> link

        # Remove external links [http://... display]
        text = re.sub(r"\[http[^\s]+ ([^\]]+)\]", r"\1", text)

        # Remove citations [1], [2], etc.
        text = re.sub(r"\[\d+\]", "", text)

        # Remove remaining HTML tags
        text = re.sub(r"<[^>]+>", "", text)

        return text
