"""
The « §SUITE: » line an assistant's reply ends with: two or three questions the visitor may want to ask next.

The system prompt asks for it on the last line so the widget can offer the questions as chips under the reply
without the visitor ever reading the line itself: a whole reply is split in one go, a streamed one holds back
every line that may still turn out to be the marker (and the blank lines just before it) and passes the rest
through as it lands. A model that glues the marker to the end of a sentence is caught too: from a « § » on, the
text is held until it is told from a marker.
"""

from __future__ import annotations

import re

MAX_FOLLOW_UPS = 3
MAX_FOLLOW_UP_CHARS = 80

# Tolerant of the model's typography: spaces, casing, a missing « § », French « § SUITE : », bold or quotes around.
_MARKER_PREFIX = r"^[\s*_«\"'-]*§?\s*suite\s*:"
_MARKER_LINE = re.compile(_MARKER_PREFIX + r"\s*(?P<items>.*?)[\s*_»\"']*$", re.IGNORECASE)
# What precedes the marker word, to tell early whether a line still may become one.
_MARKER_LEAD = re.compile(r"^[\s*_«\"'-]*§?\s*")
_MARKER_WORD = "suite:"
# Inside a line, only the sign itself may open the marker (« suite : » is a plain French word there).
_MARKER_SIGN = "§"
# The questions are separated by « | » (asked), or by « ; », « • », « / » when the model improvises.
_SEPARATOR = re.compile(r"\s*[|;•]\s*|\s+/\s+")
_TRIMMED = " \t*_«»\"'-"


def may_still_be_follow_up_marker(line: str) -> bool:
    """
    Whether an incomplete line may still turn out to be the marker.

    Args:
        line: The line so far, from its first character.

    Returns:
        True while the text read is a prefix of « §SUITE: » (tolerances included); False from the first
        character that rules it out, so the text streams at once.
    """
    probe = _MARKER_LEAD.sub("", line).lower().replace(" ", "")
    return _MARKER_WORD.startswith(probe[: len(_MARKER_WORD)])


def parse_follow_ups(items: str) -> tuple[str, ...]:
    """
    The questions a marker line carries.

    Args:
        items: The text after « §SUITE: ».

    Returns:
        At most three distinct questions (case aside), each trimmed and cut to 80 characters, in order.
    """
    kept: list[str] = []
    for raw in _SEPARATOR.split(items):
        text = " ".join(raw.strip(_TRIMMED).split())[:MAX_FOLLOW_UP_CHARS].strip()
        if text and text.lower() not in {question.lower() for question in kept}:
            kept.append(text)
        if len(kept) == MAX_FOLLOW_UPS:
            break
    return tuple(kept)


class FollowUpMarkerStream:
    """Cleans a reply as it streams: text that may be the trailing marker is held until it is decided."""

    def __init__(self) -> None:
        # The questions the marker carried, known once its line is complete.
        self.follow_ups: tuple[str, ...] = ()
        self._line = ""
        # False once the current line was released in part: its rest can only be a marker from a « § » on.
        self._line_is_whole = True
        # Blank lines before an undecided line: trailing whitespace if the marker follows, kept otherwise.
        self._held_blank = ""
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
            What the visitor may read now (empty while text that may be the marker is held back).
        """
        released: list[str] = []
        self._line += chunk
        while "\n" in self._line:
            line, _, self._line = self._line.partition("\n")
            released.append(self._complete_line(line + "\n"))
            self._line_is_whole = True
        # A marker glued to a sentence: what precedes the sign is released, the sign opens a held line.
        sign = self._line.find(_MARKER_SIGN)
        if sign >= 0 and (not self._line_is_whole or not self._sign_opens_the_line(sign)):
            if sign > 0:
                released.append(self._release(self._line[:sign]))
            self._line = self._line[sign:]
            self._line_is_whole = True
        if self._line and not (self._line_is_whole and may_still_be_follow_up_marker(self._line)):
            released.append(self._release(self._line))
            self._line = ""
            self._line_is_whole = False
        return "".join(released)

    def finish(self) -> str:
        """
        The reply is complete.

        Returns:
            What was still held back and the visitor may read (empty when it was the marker).
        """
        released = ""
        if self._line:
            released = self._complete_line(self._line) if self._line_is_whole else self._release(self._line)
            self._line = ""
        # Blank lines still held at the end are trailing whitespace.
        self._held_blank = ""
        return released

    def _sign_opens_the_line(self, sign: int) -> bool:
        """Whether only the marker's own decoration (bold, quotes, spaces) precedes the sign on the held line."""
        lead = _MARKER_LEAD.match(self._line)
        return lead is not None and lead.end() > sign

    def _complete_line(self, line: str) -> str:
        """A whole line: the marker keeps its questions and drops out, a blank one waits, anything else passes."""
        match = _MARKER_LINE.match(line)
        if match is not None:
            self.follow_ups = parse_follow_ups(match.group("items"))
            return ""
        if not line.strip():
            self._held_blank += line
            return ""
        return self._release(line)

    def _release(self, text: str) -> str:
        text = self._held_blank + text
        self._held_blank = ""
        self._parts.append(text)
        return text


class FollowUpMarker:
    """Splits a whole reply into what the visitor reads and the questions its marker carried."""

    @staticmethod
    def split(reply: str) -> tuple[str, tuple[str, ...]]:
        """
        Split a complete reply.

        Args:
            reply: The model's reply, marker line included when it wrote one.

        Returns:
            The cleaned reply (stripped, the marker line gone) and the questions, empty without a marker.
        """
        stream = FollowUpMarkerStream()
        stream.feed(reply)
        stream.finish()
        return stream.reply, stream.follow_ups
