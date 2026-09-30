"""
What the receptionist reads of a Gmail API message payload: its headers, its text, and whether it is an invitation.

Gmail hands a message as a tree of MIME parts, each body base64url-encoded in its own charset. The text is the plain
part when there is one, else the HTML one flattened; attachments are never read.
"""

from __future__ import annotations

import base64
import binascii
import codecs
import re
from email.errors import HeaderParseError
from email.header import decode_header, make_header
from typing import Any, ClassVar

from services.conversation_service import html_to_text


class GmailPayloadReader:
    """Reads the headers, the text and the calendar invitations of a Gmail API message payload."""

    TEXT_MAX_CHARS: ClassVar[int] = 20_000
    MAX_PARTS: ClassVar[int] = 200
    _CHARSET: ClassVar[re.Pattern[str]] = re.compile(r"charset\s*=\s*\"?([A-Za-z0-9_.:-]+)", re.IGNORECASE)
    _CALENDAR_TYPES: ClassVar[frozenset[str]] = frozenset({"text/calendar", "application/ics"})

    @classmethod
    def headers(cls, payload: dict[str, Any]) -> dict[str, str]:
        """
        The message's headers by lower-case name.

        Args:
            payload: The message's ``payload``.

        Returns:
            Each header's decoded value on one line; the first of a repeated header.
        """
        headers: dict[str, str] = {}
        for header in payload.get("headers") or []:
            if not isinstance(header, dict):
                continue
            name = str(header.get("name") or "").strip().lower()
            if name and name not in headers:
                headers[name] = cls.decoded(str(header.get("value") or ""))
        return headers

    @staticmethod
    def decoded(value: str) -> str:
        """
        A header value on one line, its RFC 2047 encoded words decoded.

        Args:
            value: The raw value.

        Returns:
            The readable value (the raw one when it cannot be decoded).
        """
        if "=?" in value:
            try:
                value = str(make_header(decode_header(value)))
            except (HeaderParseError, LookupError, ValueError):
                pass
        return " ".join(value.split())

    @classmethod
    def text(cls, payload: dict[str, Any]) -> str:
        """
        The message's own text: its plain parts, else its HTML parts flattened.

        Args:
            payload: The message's ``payload`` in the ``full`` format.

        Returns:
            The text, bounded; empty for a message without a readable body.
        """
        plain: list[str] = []
        html: list[str] = []
        for part in cls._parts(payload):
            if cls._is_attachment(part):
                continue
            mime_type = str(part.get("mimeType") or "").lower()
            if mime_type == "text/plain":
                plain.append(cls._body_text(part))
            elif mime_type == "text/html":
                html.append(cls._body_text(part))
        text = "\n".join(chunk for chunk in plain if chunk.strip())
        if not text and html:
            text = html_to_text("\n".join(html))
        return text.strip()[: cls.TEXT_MAX_CHARS]

    @classmethod
    def has_calendar_invite(cls, payload: dict[str, Any]) -> bool:
        """
        Whether the message carries a calendar invitation (a text/calendar part or an .ics file).

        Args:
            payload: The message's ``payload`` (``full`` format to see its parts).

        Returns:
            True for an invitation, an update or an answer to one.
        """
        for part in cls._parts(payload):
            mime_type = str(part.get("mimeType") or "").lower()
            filename = str(part.get("filename") or "").lower()
            if mime_type in cls._CALENDAR_TYPES or filename.endswith(".ics"):
                return True
        return False

    @classmethod
    def _parts(cls, payload: dict[str, Any]) -> list[dict[str, Any]]:
        """The payload and every part under it, depth first, bounded."""
        parts: list[dict[str, Any]] = []
        pending: list[dict[str, Any]] = [payload]
        while pending and len(parts) < cls.MAX_PARTS:
            part = pending.pop(0)
            parts.append(part)
            pending[0:0] = [child for child in part.get("parts") or [] if isinstance(child, dict)]
        return parts

    @classmethod
    def _is_attachment(cls, part: dict[str, Any]) -> bool:
        """Whether a part is a file: a name, or an attachment disposition."""
        disposition = cls.headers(part).get("content-disposition", "").lower()
        return bool(part.get("filename")) or disposition.startswith("attachment")

    @classmethod
    def _body_text(cls, part: dict[str, Any]) -> str:
        """A text part's body in clear, read in the charset its Content-Type names (UTF-8 otherwise)."""
        data = str((part.get("body") or {}).get("data") or "")
        if not data:
            return ""
        try:
            raw = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))
        except (binascii.Error, ValueError):
            return ""
        match = cls._CHARSET.search(cls.headers(part).get("content-type", ""))
        charset = match.group(1) if match else "utf-8"
        try:
            codecs.lookup(charset)
        except LookupError:
            charset = "utf-8"
        return raw.decode(charset, errors="replace")
