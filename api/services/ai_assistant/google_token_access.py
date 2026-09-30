"""
A valid access token for a row that keeps a Google account's tokens encrypted.

The access token is refreshed, and saved at once, two minutes before it expires; a call Google answers with a 401 (a
token it dropped early) is refreshed once and replayed. Each integration says how it refreshes (its own client, its
own errors) and which error a row without a lasting access raises.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from typing import ClassVar, Protocol, TypeVar

from sqlalchemy.orm import Session

from core.clock import naive_utc_now
from services.encryption_service import encryption_service
from services.google_oauth_client import GoogleApiError, GoogleTokens

logger = logging.getLogger(__name__)

T = TypeVar("T")


class GoogleTokenRow(Protocol):
    """A row keeping a Google account's tokens, encrypted with ``encryption_service``."""

    access_token_encrypted: str | None
    refresh_token_encrypted: str | None
    token_expires_at: datetime | None


class GoogleTokenAccess:
    """Keeps the Google access token of a row valid, for the calls of one integration."""

    REFRESH_MARGIN: ClassVar[timedelta] = timedelta(minutes=2)

    async def access_token(self, db: Session, row: GoogleTokenRow) -> str:
        """
        A valid access token, refreshed (and stored) when it expires within two minutes.

        Args:
            db: Active database session.
            row: The row keeping the tokens.

        Returns:
            The access token.

        Raises:
            GoogleApiError: When the row has no lasting access, or Google refuses to refresh it.
        """
        access_token = self.decrypt(row.access_token_encrypted)
        expires_at = row.token_expires_at
        if access_token and expires_at and expires_at > naive_utc_now() + self.REFRESH_MARGIN:
            return access_token
        return await self.refresh_access_token(db, row)

    async def refresh_access_token(self, db: Session, row: GoogleTokenRow) -> str:
        """
        A new access token from the stored refresh token, saved at once.

        Args:
            db: Active database session.
            row: The row keeping the tokens.

        Returns:
            The fresh access token.

        Raises:
            GoogleApiError: When the row has no lasting access, or Google refuses to refresh it.
        """
        refresh_token = self.decrypt(row.refresh_token_encrypted)
        if not refresh_token:
            raise self._lost_access_error()
        tokens = await self._refresh(refresh_token)
        row.access_token_encrypted = encryption_service.encrypt(tokens.access_token)
        if tokens.refresh_token and tokens.refresh_token != refresh_token:
            row.refresh_token_encrypted = encryption_service.encrypt(tokens.refresh_token)
        row.token_expires_at = tokens.expires_at
        # Saved at once, in its own short transaction: no write stays open while Google answers next.
        db.commit()
        return tokens.access_token

    async def with_fresh_token(self, db: Session, row: GoogleTokenRow, operation: Callable[[str], Awaitable[T]]) -> T:
        """
        Run a Google call with a valid token; a 401 (a token Google dropped early) is refreshed once and replayed.

        Args:
            db: Active database session.
            row: The row keeping the tokens.
            operation: The call, given the access token.

        Returns:
            What the call returns.

        Raises:
            GoogleApiError: When the call fails again, or the refresh is refused (then a reconnection is due).
        """
        access_token = await self.access_token(db, row)
        try:
            return await operation(access_token)
        except GoogleApiError as exc:
            if exc.status_code != 401:
                raise
        access_token = await self.refresh_access_token(db, row)
        return await operation(access_token)

    @staticmethod
    def decrypt(value: str | None) -> str | None:
        """
        A stored token in clear.

        Args:
            value: The encrypted token.

        Returns:
            The token, or None when absent or unreadable (a rotated key).
        """
        if not value:
            return None
        try:
            return encryption_service.decrypt(value) or None
        except ValueError:
            logger.warning("A Google token could not be decrypted")
            return None

    async def _refresh(self, refresh_token: str) -> GoogleTokens:
        """New tokens from the integration's own client, its refusals raised as its own error."""
        raise NotImplementedError

    def _lost_access_error(self) -> GoogleApiError:
        """The error of a row whose refresh token is missing or unreadable."""
        raise NotImplementedError
