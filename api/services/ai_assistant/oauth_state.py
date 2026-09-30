"""
The OAuth ``state`` of a Google consent started from a client space: the assistant, an expiry and an HMAC of both.

Each integration signs its states for its own purpose, so a state issued for one never completes a consent of
another. The state carries no client-space link.
"""

from __future__ import annotations

import hmac
import re
from datetime import UTC, datetime, timedelta
from typing import ClassVar

from core.clock import naive_utc_now
from services.ai_assistant.signed_token import SignedToken


class AiAssistantOAuthState:
    """A state valid ``TTL_MINUTES`` minutes, signed for the ``_PURPOSE`` of the integration that subclasses it."""

    TTL_MINUTES: ClassVar[int] = 15
    _PURPOSE: ClassVar[str]
    _PATTERN: ClassVar[re.Pattern[str]] = re.compile(
        r"([1-9][0-9]{0,11})\.([0-9]{1,12})\.([A-Za-z0-9_-]{22})", re.ASCII
    )

    @classmethod
    def sign(cls, assistant_id: int, *, now: datetime | None = None) -> str:
        """
        A state for one consent, valid ``TTL_MINUTES`` minutes.

        Args:
            assistant_id: The assistant whose account is being connected.
            now: Current time, naive UTC (tests); defaults to now.

        Returns:
            ``<id>.<expiry epoch>.<signature>``.
        """
        moment = now or naive_utc_now()
        expiry = str(int((moment + timedelta(minutes=cls.TTL_MINUTES)).replace(tzinfo=UTC).timestamp()))
        return f"{assistant_id}.{expiry}.{cls._signature(assistant_id, expiry)}"

    @classmethod
    def read(cls, state: str, *, now: datetime | None = None) -> int | None:
        """
        The assistant of a state that is authentic and still valid.

        Args:
            state: The ``state`` Google sent back.
            now: Current time, naive UTC (tests); defaults to now.

        Returns:
            The assistant id, or None when the state is forged, malformed, expired or signed for another purpose.
        """
        match = cls._PATTERN.fullmatch(state or "")
        if match is None:
            return None
        assistant_id, expiry, signature = int(match.group(1)), match.group(2), match.group(3)
        if not hmac.compare_digest(signature, cls._signature(assistant_id, expiry)):
            return None
        moment = now or naive_utc_now()
        if int(expiry) <= int(moment.replace(tzinfo=UTC).timestamp()):
            return None
        return assistant_id

    @classmethod
    def _signature(cls, assistant_id: int, expiry: str) -> str:
        """Truncated HMAC-SHA256 (128 bits) of the purpose, the assistant and the expiry, base64url without padding."""
        return SignedToken.short(cls._PURPOSE, assistant_id, expiry, length=16)
