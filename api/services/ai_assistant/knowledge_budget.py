"""
What of the business's website and documents fits in the assistant's prompt.

The listing (name, hours, services, reviews) always goes in whole: it is short and comes first. The website
pages, then the documents, follow whole while they fit a character budget (about 6,000 tokens). Beyond it, they
are cut into passages and the ones sharing the most words with the visitor's latest messages are kept, in their
reading order (a light retrieval, no embeddings). On a tie, and with no word in common (« Et combien ça coûte ? »),
the first passage of every source comes before the second of any: each page and each document keeps its opening.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import ClassVar

from enums.assistant_knowledge_source import AssistantKnowledgeSource
from services.text_normalizer import TextNormalizer


@dataclass(frozen=True)
class KnowledgeSourceText:
    """A website page or a document, with what the assistant cites of it (title, link)."""

    kind: AssistantKnowledgeSource
    title: str
    url: str | None
    text: str


@dataclass(frozen=True)
class KnowledgePassage:
    """A piece of a source kept for the prompt, and its place in the reading order."""

    source: KnowledgeSourceText
    text: str
    position: int
    # Which piece of its source this is, and how many pieces the source was cut into (1: the source whole).
    piece: int = 0
    pieces: int = 1


class AiAssistantKnowledgeBudget:
    """Fits the website pages and the documents into the prompt's budget."""

    MAX_CHARS: ClassVar[int] = 24_000
    PASSAGE_CHARS: ClassVar[int] = 900
    # A word matches another when their first letters agree (« vidanges » / « vidange », « tarif » / « tarifs »).
    _STEM_CHARS: ClassVar[int] = 5
    _MIN_WORD_CHARS: ClassVar[int] = 4
    # Frequent words of the widget's languages that say nothing about the question.
    _STOP_WORDS: ClassVar[frozenset[str]] = frozenset(
        {
            "avec",
            "avez",
            "bonjour",
            "cette",
            "combien",
            "dans",
            "faire",
            "faut",
            "merci",
            "nous",
            "pour",
            "quel",
            "quelle",
            "quels",
            "quelles",
            "sont",
            "votre",
            "vous",
            "about",
            "have",
            "hello",
            "what",
            "when",
            "where",
            "with",
            "your",
            "haben",
            "ihre",
            "kann",
            "wann",
            "welche",
            "hebben",
            "jullie",
            "wanneer",
            "welke",
        }
    )

    @classmethod
    def select(
        cls, sources: list[KnowledgeSourceText], *, question: str | None, max_chars: int | None = None
    ) -> list[KnowledgePassage]:
        """
        The passages of the sources to put in the prompt.

        Args:
            sources: The website pages then the documents, in reading order.
            question: The visitor's latest message (ranks the passages when everything cannot fit).
            max_chars: The budget; ``MAX_CHARS`` by default.

        Returns:
            Every source whole when they fit, else the best passages within the budget, in reading order.
        """
        budget = cls.MAX_CHARS if max_chars is None else max_chars
        whole = [
            KnowledgePassage(source=source, text=source.text, position=index) for index, source in enumerate(sources)
        ]
        if sum(len(passage.text) for passage in whole) <= budget:
            return whole
        passages = cls._passages(sources)
        terms = cls._stems(question or "")
        ranked = sorted(passages, key=lambda passage: (-cls._score(passage, terms), passage.piece, passage.position))
        kept: list[KnowledgePassage] = []
        used = 0
        for passage in ranked:
            if used + len(passage.text) > budget:
                continue
            kept.append(passage)
            used += len(passage.text)
        return sorted(kept, key=lambda passage: passage.position)

    @classmethod
    def _passages(cls, sources: list[KnowledgeSourceText]) -> list[KnowledgePassage]:
        """Every source cut into passages of about ``PASSAGE_CHARS`` at line or sentence breaks."""
        passages: list[KnowledgePassage] = []
        for source in sources:
            pieces = _cut(source.text, cls.PASSAGE_CHARS)
            for index, piece in enumerate(pieces):
                passages.append(
                    KnowledgePassage(source=source, text=piece, position=len(passages), piece=index, pieces=len(pieces))
                )
        return passages

    @classmethod
    def _score(cls, passage: KnowledgePassage, terms: frozenset[str]) -> int:
        """Question words found in the passage, those of its source's title counting twice."""
        if not terms:
            return 0
        return len(terms & cls._stems(passage.text)) + 2 * len(terms & cls._stems(passage.source.title))

    @classmethod
    def _stems(cls, text: str) -> frozenset[str]:
        """The meaningful words of a text, accent-free and cut to their first letters."""
        return _stems(text, cls._STEM_CHARS, cls._MIN_WORD_CHARS, cls._STOP_WORDS)


# The same pages and documents come back with every message: their cutting and their words are kept.
@lru_cache(maxsize=256)
def _cut(text: str, passage_chars: int) -> tuple[str, ...]:
    """A text in pieces of about ``passage_chars``, cut after a line (a price list's row), else a sentence."""
    pieces: list[str] = []
    rest = text.strip()
    while len(rest) > passage_chars:
        head = rest[:passage_chars]
        cut = head.rfind("\n")
        if cut < passage_chars // 2:
            cut = head.rfind(". ")
        if cut < passage_chars // 2:
            cut = head.rfind(" ")
        cut = cut + 1 if cut > 0 else passage_chars
        pieces.append(rest[:cut].strip())
        rest = rest[cut:].strip()
    if rest:
        pieces.append(rest)
    return tuple(pieces)


@lru_cache(maxsize=4096)
def _stems(text: str, stem_chars: int, min_word_chars: int, stop_words: frozenset[str]) -> frozenset[str]:
    """The meaningful words of a text, accent-free and cut to their first ``stem_chars`` letters."""
    return frozenset(
        word[:stem_chars]
        for word in re.findall(r"[a-z0-9]+", TextNormalizer.fold(text))
        if len(word) >= min_word_chars and word not in stop_words
    )
