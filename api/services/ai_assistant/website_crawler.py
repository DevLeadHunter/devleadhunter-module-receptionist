"""Light crawl of a prospect's website for the assistant's knowledge base.

The Google Maps enrichment says little (a line of description, sometimes no service at all); the
prospect's own site says what they sell, at what price, where and to whom. A handful of pages, text
only, bounded so the whole site fits in the prompt — no retrieval layer until a catalogue needs one.
"""

import logging
import re
import unicodedata
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

MAX_PAGES = 8
MAX_PAGE_CHARS = 4000
MAX_TOTAL_CHARS = 24000
FETCH_TIMEOUT_SECONDS = 8.0
_USER_AGENT = "DevLeadHunterBot/1.0 (+https://devleadhunter.fr)"
# Path or link-label words that usually mark what the assistant must know (offer, prices, hours, FAQ…).
_INTERESTING_WORDS: tuple[str, ...] = (
    "service",
    "prestation",
    "tarif",
    "prix",
    "offre",
    "faq",
    "question",
    "contact",
    "horaire",
    "propos",
    "about",
    "equipe",
    "team",
    "realisation",
    "projet",
    "zone",
    "devis",
)
# Pages that eat the budget without telling a visitor anything useful (news, legal boilerplate).
_SKIPPED_PATH_WORDS: tuple[str, ...] = (
    "blog",
    "actualit",
    "news",
    "article",
    "mention",
    "legal",
    "cookie",
    "confidentialite",
    "privacy",
    "cgv",
    "cgu",
)
# Chrome of a page, never its substance.
_DROPPED_TAGS: tuple[str, ...] = (
    "script",
    "style",
    "noscript",
    "svg",
    "nav",
    "footer",
    "header",
    "aside",
    "form",
    "iframe",
)
_BINARY_EXTENSIONS: tuple[str, ...] = (
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".svg",
    ".zip",
    ".mp4",
    ".doc",
    ".docx",
)
_WHITESPACE = re.compile(r"\s+")


class AiAssistantWebsiteCrawler:
    """Fetches a site's home page and its most useful internal pages as clean text."""

    async def crawl(self, website_url: str | None) -> dict[str, Any] | None:
        """Read up to ``MAX_PAGES`` pages of the site, text only, within the character budget.

        Args:
            website_url: The prospect's website, with or without scheme.

        Returns:
            ``{"url", "crawled_at", "pages": [{"url", "title", "text"}]}``, or None when the home page
            cannot be read. Never raises: a broken site just yields fewer pages.
        """
        home_url: str | None = self._normalize_url(website_url)
        if home_url is None:
            return None
        pages: list[dict[str, str]] = []
        total_chars: int = 0
        try:
            async with httpx.AsyncClient(
                timeout=FETCH_TIMEOUT_SECONDS, follow_redirects=True, headers={"User-Agent": _USER_AGENT}
            ) as client:
                home = await self._fetch(client, home_url)
                if home is None:
                    return None
                pages.append(home["page"])
                total_chars += len(home["page"]["text"])
                for link in home["links"][: MAX_PAGES - 1]:
                    if total_chars >= MAX_TOTAL_CHARS:
                        break
                    fetched = await self._fetch(client, link)
                    if fetched is None:
                        continue
                    page: dict[str, str] = fetched["page"]
                    page["text"] = page["text"][: MAX_TOTAL_CHARS - total_chars]
                    if not page["text"]:
                        continue
                    pages.append(page)
                    total_chars += len(page["text"])
        except Exception:
            logger.warning("Website crawl interrupted for %s", home_url, exc_info=True)
            if not pages:
                return None
        return {"url": home_url, "crawled_at": datetime.now(UTC).isoformat(), "pages": pages}

    async def _fetch(self, client: httpx.AsyncClient, url: str) -> dict[str, Any] | None:
        """One page as ``{"page": {url, title, text}, "links": [internal urls]}``, or None when unreadable."""
        try:
            response = await client.get(url)
        except httpx.HTTPError:
            return None
        if response.status_code != 200 or "html" not in response.headers.get("content-type", "").lower():
            return None
        soup = BeautifulSoup(response.text, "html.parser")
        links: list[str] = self._internal_links(soup, str(response.url))
        for tag in soup(_DROPPED_TAGS):
            tag.decompose()
        title: str = self._collapse(soup.title.get_text(" ", strip=True) if soup.title else "")
        text: str = self._collapse(soup.get_text(" ", strip=True))[:MAX_PAGE_CHARS]
        if not text:
            return None
        return {"page": {"url": url, "title": title, "text": text}, "links": links}

    def _internal_links(self, soup: BeautifulSoup, base_url: str) -> list[str]:
        """Same-site page links, the ones about the offer first, without duplicates or the page itself."""
        base_host: str = self._host(base_url)
        base_path: str = urlparse(base_url).path.rstrip("/") or "/"
        interesting: list[str] = []
        others: list[str] = []
        seen: set[str] = set()
        for anchor in soup.find_all("a", href=True):
            absolute: str = self._normalize_url(urljoin(base_url, str(anchor["href"]))) or ""
            if not absolute or self._host(absolute) != base_host or absolute in seen:
                continue
            path: str = urlparse(absolute).path.rstrip("/") or "/"
            folded_path: str = self._fold(path)
            if path == base_path or folded_path.endswith(_BINARY_EXTENSIONS):
                continue
            if any(word in folded_path for word in _SKIPPED_PATH_WORDS):
                continue
            seen.add(absolute)
            label: str = f"{folded_path} {self._fold(anchor.get_text(' ', strip=True))}"
            (interesting if any(word in label for word in _INTERESTING_WORDS) else others).append(absolute)
        return interesting + others

    @staticmethod
    def _normalize_url(raw: str | None) -> str | None:
        """An absolute http(s) URL without fragment, or None when the value is not a web address."""
        value: str = (raw or "").strip()
        if not value:
            return None
        if not value.lower().startswith(("http://", "https://")):
            value = f"https://{value}"
        parsed = urlparse(value)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return None
        return urlunparse((parsed.scheme, parsed.netloc.lower(), parsed.path or "/", "", parsed.query, ""))

    @staticmethod
    def _host(url: str) -> str:
        host: str = urlparse(url).netloc.lower()
        return host[4:] if host.startswith("www.") else host

    @staticmethod
    def _collapse(text: str) -> str:
        return _WHITESPACE.sub(" ", text).strip()

    @staticmethod
    def _fold(text: str) -> str:
        """Lowercase ASCII (accents stripped), to match the keyword list."""
        return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()


ai_assistant_website_crawler = AiAssistantWebsiteCrawler()
