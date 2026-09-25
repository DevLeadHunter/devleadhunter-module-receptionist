"""
Signed one-click links carried by the request summary email.

The business owner marks a request handled straight from the email, without an account: the link
names the request, expires after 30 days and carries an HMAC of both (keyed by ``SECRET_KEY``), so it
can be neither forged for another request nor replayed forever.
"""

from __future__ import annotations

import hmac
from datetime import UTC, datetime, timedelta

from core.config import settings
from services.ai_assistant.signed_token import SignedToken


class AiAssistantRequestLinks:
    """Builds and verifies the « marquer traitée » link of a request."""

    LINK_TTL_DAYS = 30
    _PURPOSE = "assistant-request-handled"

    @classmethod
    def handled_url(cls, request_id: int, *, now: datetime | None = None) -> str:
        """
        Public URL that marks a request handled.

        Args:
            request_id: The request to act on.
            now: Current time (tests); defaults to now.

        Returns:
            The absolute signed URL, valid ``LINK_TTL_DAYS`` days.
        """
        expires_at = int(((now or datetime.now(UTC)) + timedelta(days=cls.LINK_TTL_DAYS)).timestamp())
        base = settings.api_base_url.rstrip("/")
        return (
            f"{base}{settings.api_prefix}/ai-assistants/public/requests/{request_id}/handled"
            f"?exp={expires_at}&token={cls.sign(request_id, expires_at)}"
        )

    @classmethod
    def verify(cls, request_id: int, expires_at: int, token: str | None, *, now: datetime | None = None) -> bool:
        """
        Check a link's signature and expiry.

        Args:
            request_id: The request named by the link.
            expires_at: Unix expiry timestamp carried by the link.
            token: Signature carried by the link.
            now: Current time (tests); defaults to now.

        Returns:
            True only for an unexpired link signed for this request.
        """
        if not token or not token.isascii() or expires_at < int((now or datetime.now(UTC)).timestamp()):
            return False
        return hmac.compare_digest(token, cls.sign(request_id, expires_at))

    @classmethod
    def sign(cls, request_id: int, expires_at: int) -> str:
        """HMAC-SHA256 of the request id and expiry, hex-encoded."""
        return SignedToken.digest(cls._PURPOSE, request_id, expires_at).hex()
