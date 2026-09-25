"""
The « §MANQUE: » line an assistant's reply starts with when the visitor asked for something its knowledge lacks.

The system prompt asks for it on the first line so the question can reach the business's « questions sans
réponse » list without the visitor ever seeing it: a whole reply is split in one go, a streamed one holds its
first line back until it is complete (or clearly not a marker) and passes everything after it through.
"""

from __future__ import annotations

import re

# A first line this long without a newline is a plain reply: nothing to hold back any more.
FIRST_LINE_PEEK_CHARS = 120

# Tolerant of the model's typography: spaces, casing, a missing « § », French « § MANQUE : », bold or quotes around.
_MARKER_PREFIX = r"^[\s*_«\"'-]*§?\s*manque\s*:"
_MARKER_LINE = re.compile(_MARKER_PREFIX + r"\s*(?P<question>.*?)[\s*_»\"']*$", re.IGNORECASE)
_MARKER_START = re.compile(_MARKER_PREFIX, re.IGNORECASE)
# What precedes the marker word, to tell early whether a line still may become one.
_MARKER_LEAD = re.compile(r"^[\s*_«\"'-]*§?\s*")
_MARKER_WORD = "manque:"


def may_still_be_marker(head: str) -> bool:
    """
    Whether an incomplete first line may still turn out to be the marker.

    Args:
        head: The first line so far.

    Returns:
        True while the text read is a prefix of « §MANQUE: » (tolerances included); False from the first
        character that rules it out, so a plain reply streams at once.
    """
    probe = _MARKER_LEAD.sub("", head).lower().replace(" ", "")
    return _MARKER_WORD.startswith(probe[: len(_MARKER_WORD)])


class MissingInfoMarkerStream:
    """Cleans a reply as it streams: the first line is held until it can be told from a marker."""

    def __init__(self) -> None:
        # The question the marker carried, known once the first line is decided.
        self.question: str | None = None
        self._head = ""
        self._decided = False
        # Leading whitespace — of the reply, or left after the marker line — never reaches the visitor.
        self._skipping_blank = True
        self._parts: list[str] = []

    @property
    def reply(self) -> str:
        """The cleaned reply passed through so far."""
        return "".join(self._parts).strip()

    def feed(self, chunk: str) -> str:
        """
        Take one delta of the reply.

        Args:
            chunk: The next piece of text from the model.

        Returns:
            What the visitor may read now (empty while the first line is held back).
        """
        if self._decided:
            return self._emit(chunk)
        self._head += chunk
        if "\n" in self._head:
            return self._decide()
        if _MARKER_START.match(self._head):
            # A marker line: its question runs to the newline.
            return ""
        if not may_still_be_marker(self._head) or len(self._head) >= FIRST_LINE_PEEK_CHARS:
            return self._decide()
        return ""

    def finish(self) -> str:
        """
        The reply is complete.

        Returns:
            What was still held back and the visitor may read (empty when it was a marker line).
        """
        return self._decide() if not self._decided else ""

    def _decide(self) -> str:
        """Tell the first line: a marker keeps its question and drops out, anything else passes through."""
        first, newline, rest = self._head.partition("\n")
        self._head = ""
        self._decided = True
        match = _MARKER_LINE.match(first)
        if match is None:
            return self._emit(first + newline + rest)
        self.question = " ".join(match.group("question").split()) or None
        return self._emit(rest)

    def _emit(self, text: str) -> str:
        if self._skipping_blank:
            text = text.lstrip()
            if not text:
                return ""
            self._skipping_blank = False
        self._parts.append(text)
        return text


class MissingInfoMarker:
    """Splits a whole reply into what the visitor reads and the question its marker carried."""

    @staticmethod
    def split(reply: str) -> tuple[str, str | None]:
        """
        Split a complete reply.

        Args:
            reply: The model's reply, marker line included when it wrote one.

        Returns:
            The cleaned reply (stripped, the marker line gone) and the question, None without a marker.
        """
        stream = MissingInfoMarkerStream()
        stream.feed(reply)
        stream.finish()
        return stream.reply, stream.question
