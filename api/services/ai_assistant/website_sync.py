"""
What changed on a business's website between two reads, and the record of the last read.

The record lives in ``knowledge_json['website_sync']``: when, how many pages, the addresses of the pages added,
removed or whose text changed (« 3 pages modifiées »), or why the site could not be read. A site that cannot be
read keeps its previous pages: a broken site never empties the assistant's knowledge. Nor does a read that lost
more than half of the pages or of the text (a sub-page timing out, a maintenance page): the weekly re-read keeps the
previous pages, and only « Mettre à jour » takes such a read.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, ClassVar


@dataclass(frozen=True)
class WebsiteDiff:
    """What changed on the website since the last read, by page address."""

    added: tuple[str, ...]
    removed: tuple[str, ...]
    changed: tuple[str, ...]

    @property
    def count(self) -> int:
        """How many pages changed in any way."""
        return len(self.added) + len(self.removed) + len(self.changed)


class AiAssistantWebsiteSync:
    """Compares two reads of a website and writes the record of the last one."""

    UNREADABLE: ClassVar[str] = "Site injoignable ou absent : les pages lues avant sont gardées."
    INCOMPLETE: ClassVar[str] = (
        "Lecture incomplète (moins de la moitié des pages ou du texte d'avant) : les pages lues avant sont gardées ; "
        "« Mettre à jour » prend la nouvelle lecture."
    )

    @staticmethod
    def diff(old: dict[str, Any] | None, new: dict[str, Any] | None) -> WebsiteDiff:
        """
        Compare two reads of a website, page by page.

        Args:
            old: The stored ``knowledge_json['website']``.
            new: The fresh crawl.

        Returns:
            The pages added, removed and changed, by address.
        """
        before = AiAssistantWebsiteSync._texts(old)
        after = AiAssistantWebsiteSync._texts(new)
        return WebsiteDiff(
            added=tuple(url for url in after if url not in before),
            removed=tuple(url for url in before if url not in after),
            changed=tuple(url for url, text in after.items() if url in before and before[url] != text),
        )

    @classmethod
    def record(cls, previous: dict[str, Any] | None, crawl: dict[str, Any] | None, *, at: datetime) -> dict[str, Any]:
        """
        The record of a read of the website.

        Args:
            previous: The pages read before (``knowledge_json['website']``), or None.
            crawl: The fresh crawl, or None when the site could not be read.
            at: When it was read, naive UTC.

        Returns:
            ``{at, pages, added, removed, changed, error}``: without a crawl, the pages kept and why.
        """
        if crawl is None:
            return {
                "at": at.isoformat(),
                "pages": len((previous or {}).get("pages") or []),
                "added": [],
                "removed": [],
                "changed": [],
                "error": cls.UNREADABLE,
            }
        changes = cls.diff(previous, crawl)
        return {
            "at": at.isoformat(),
            "pages": len(crawl.get("pages") or []),
            "added": list(changes.added),
            "removed": list(changes.removed),
            "changed": list(changes.changed),
            "error": None,
        }

    @classmethod
    def shrank(cls, previous: dict[str, Any] | None, crawl: dict[str, Any] | None) -> bool:
        """
        Whether a read lost more than half of the pages, or of the text, of the previous one.

        Args:
            previous: The pages read before.
            crawl: The fresh crawl.

        Returns:
            True when the fresh read looks incomplete rather than the site smaller.
        """
        before, after = cls._texts(previous), cls._texts(crawl)
        if len(before) >= 2 and len(after) * 2 < len(before):
            return True
        before_chars = sum(len(text) for text in before.values())
        after_chars = sum(len(text) for text in after.values())
        return before_chars >= 1000 and after_chars * 2 < before_chars

    @classmethod
    def incomplete(cls, previous: dict[str, Any] | None, *, at: datetime) -> dict[str, Any]:
        """
        The record of a read set aside as incomplete (the previous pages stay).

        Args:
            previous: The pages read before, kept.
            at: When it was read, naive UTC.

        Returns:
            ``{at, pages, added, removed, changed, error}`` with the previous page count and why.
        """
        before = len((previous or {}).get("pages") or [])
        return {
            "at": at.isoformat(),
            "pages": before,
            "added": [],
            "removed": [],
            "changed": [],
            "error": cls.INCOMPLETE,
        }

    @staticmethod
    def _texts(website: dict[str, Any] | None) -> dict[str, str]:
        """``{page address: text}`` of a website read."""
        pages = (website or {}).get("pages") or []
        return {
            str(page.get("url")): str(page.get("text") or "")
            for page in pages
            if isinstance(page, dict) and page.get("url")
        }
