"""
The HMAC core of the receptionist's signed links: a purpose, an id and an expiry, keyed by ``SECRET_KEY``.

Each link keeps its own wire format (client space, agenda consent, « marquer traitée »), so links already sent keep
verifying; only the signature is computed here.
"""

from __future__ import annotations

import base64
import hashlib
import hmac

from core.config import settings


class SignedToken:
    """Signs ``<purpose>:<id>:<expiry>`` with HMAC-SHA256 keyed by ``SECRET_KEY``."""

    @staticmethod
    def digest(purpose: str, subject_id: int, expiry: str | int) -> bytes:
        """
        The full signature of a subject and its expiry.

        Args:
            purpose: What the link is for, so a signature never serves another kind of link.
            subject_id: The assistant or request the link names.
            expiry: The expiry exactly as the link carries it.

        Returns:
            The 32-byte HMAC-SHA256 digest.
        """
        message = f"{purpose}:{subject_id}:{expiry}".encode()
        return hmac.new(settings.secret_key.encode(), message, hashlib.sha256).digest()

    @staticmethod
    def short(purpose: str, subject_id: int, expiry: str, *, length: int) -> str:
        """
        A truncated signature for a URL segment.

        Args:
            purpose: What the link is for.
            subject_id: The assistant the link names.
            expiry: The expiry exactly as the link carries it.
            length: Bytes of the digest kept.

        Returns:
            The first ``length`` bytes, base64url without padding.
        """
        truncated = SignedToken.digest(purpose, subject_id, expiry)[:length]
        return base64.urlsafe_b64encode(truncated).decode().rstrip("=")
