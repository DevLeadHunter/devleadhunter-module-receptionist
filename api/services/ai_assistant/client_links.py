"""
The magic link of a sold assistant's client space: no account, no password.

The link names the assistant, expires after 30 days and carries an HMAC of both (keyed by
``SECRET_KEY``), so it can be neither forged for another assistant nor used forever. It is short on
purpose (``12.mfx3k2.Qs9…``, about 28 characters): it also rides in the one-segment alert SMS.
Every alert carries a fresh one, and the page sends a new one to the business when it has expired.
"""

from __future__ import annotations

import hmac
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import ClassVar

from core.config import settings
from services.ai_assistant.signed_token import SignedToken


@dataclass(frozen=True)
class ClientLinkToken:
    """A client-space token whose signature checked out."""

    assistant_id: int
    expires_at: datetime
    is_expired: bool


class AiAssistantClientLinks:
    """Builds and reads the signed links of the client space."""

    TTL_DAYS: ClassVar[int] = 30
    _PURPOSE: ClassVar[str] = "assistant-client-space"
    # 12 bytes of HMAC (96 bits), base64url: short enough for an SMS, far beyond guessing.
    _SIGNATURE_BYTES: ClassVar[int] = 12
    # Canonical form only (ASCII digits, no leading zero): a token is its own URL segment.
    _TOKEN: ClassVar[re.Pattern[str]] = re.compile(
        r"([1-9][0-9]{0,11})\.([0-9a-z]{1,10})\.([A-Za-z0-9_-]{16})", re.ASCII
    )

    @classmethod
    def token(cls, assistant_id: int, *, now: datetime | None = None) -> str:
        """
        A fresh token for an assistant's client space.

        Args:
            assistant_id: The sold assistant.
            now: Current time (tests); defaults to now.

        Returns:
            ``<id>.<expiry base 36>.<signature>``, valid ``TTL_DAYS`` days.
        """
        expires_at = int((cls._utc(now) + timedelta(days=cls.TTL_DAYS)).timestamp())
        expiry = cls._base36(expires_at)
        return f"{assistant_id}.{expiry}.{cls._sign(assistant_id, expiry)}"

    @classmethod
    def url(cls, assistant_id: int, *, now: datetime | None = None) -> str:
        """
        The client-space page of an assistant, with a fresh token.

        Args:
            assistant_id: The sold assistant.
            now: Current time (tests); defaults to now.

        Returns:
            The absolute page URL on the demo host.
        """
        return cls.page_url(cls.token(assistant_id, now=now))

    @staticmethod
    def page_url(token: str) -> str:
        """
        The client-space page of a token already checked by :meth:`read`.

        Args:
            token: A canonical client-space token.

        Returns:
            The absolute page URL on the demo host.
        """
        return f"{settings.demo_host_base_url.rstrip('/')}/client/{token}"

    @classmethod
    def sms_link(cls, assistant_id: int, *, now: datetime | None = None) -> str:
        """The client-space URL without its scheme (a bare link is tapped all the same in an SMS)."""
        return re.sub(r"^https?://", "", cls.url(assistant_id, now=now))

    @classmethod
    def read(cls, token: str, *, now: datetime | None = None) -> ClientLinkToken | None:
        """
        Check a token's shape and signature, and tell whether it has expired.

        Args:
            token: The token from the page URL.
            now: Current time (tests); defaults to now.

        Returns:
            The token's assistant and expiry, or None when it is malformed or forged.
        """
        match = cls._TOKEN.fullmatch(token or "")
        if match is None:
            return None
        assistant_id, expiry, signature = int(match.group(1)), match.group(2), match.group(3)
        if not hmac.compare_digest(signature, cls._sign(assistant_id, expiry)):
            return None
        expires_at = datetime.fromtimestamp(int(expiry, 36), UTC)
        return ClientLinkToken(
            assistant_id=assistant_id,
            expires_at=expires_at.replace(tzinfo=None),
            is_expired=expires_at <= cls._utc(now),
        )

    @classmethod
    def _sign(cls, assistant_id: int, expiry: str) -> str:
        """Truncated HMAC-SHA256 of the assistant and expiry, base64url without padding."""
        return SignedToken.short(cls._PURPOSE, assistant_id, expiry, length=cls._SIGNATURE_BYTES)

    @staticmethod
    def _utc(now: datetime | None) -> datetime:
        """An aware UTC moment (a naive one is naive UTC, the storage convention); now by default."""
        if now is None:
            return datetime.now(UTC)
        return now.replace(tzinfo=UTC) if now.tzinfo is None else now

    @staticmethod
    def _base36(value: int) -> str:
        """A positive integer in lowercase base 36."""
        digits = "0123456789abcdefghijklmnopqrstuvwxyz"
        encoded = ""
        while value:
            value, remainder = divmod(value, 36)
            encoded = digits[remainder] + encoded
        return encoded or "0"
