"""
Gmail for a sold receptionist: the client's consent, its tokens, and the calls that read new emails and write drafts.

The client connects their own Google account from the client space. The scopes are their address, the reading of
their mailbox (``gmail.readonly``) and the writing of drafts (``gmail.compose``): nothing is ever sent from here. The
OAuth steps are those of every Google integration (``google_oauth_client``); every call is a plain HTTPS request
(httpx), mocked in tests.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, ClassVar
from urllib.parse import quote

import httpx

from core.config import settings
from services.ai_assistant.gmail_payload import GmailPayloadReader
from services.google_oauth_client import GoogleApiError, GoogleOAuthError, GoogleTokens, google_oauth_client

logger = logging.getLogger(__name__)

GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
GMAIL_COMPOSE_SCOPE = "https://www.googleapis.com/auth/gmail.compose"
GMAIL_SCOPES: tuple[str, ...] = (
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    GMAIL_READONLY_SCOPE,
    GMAIL_COMPOSE_SCOPE,
)


class GmailError(GoogleApiError):
    """A Gmail call that failed; ``needs_reconnect`` when the client must connect their mailbox again."""


@dataclass(frozen=True)
class GmailProfile:
    """The connected mailbox: its address, and the history id it stands at."""

    email_address: str
    history_id: str


@dataclass(frozen=True)
class GmailMessageRef:
    """A message as Gmail lists it; ``label_ids`` is empty when the listing does not give them."""

    message_id: str
    thread_id: str
    label_ids: frozenset[str] = frozenset()


@dataclass(frozen=True)
class GmailChanges:
    """What happened in the mailbox since a history id: the emails received, the threads answered, the new id."""

    received: list[GmailMessageRef]
    answered_thread_ids: frozenset[str]
    history_id: str


@dataclass(frozen=True)
class GmailMessage:
    """One email as the receptionist reads it; ``text`` is empty when only its headers were read."""

    message_id: str
    thread_id: str
    label_ids: frozenset[str]
    headers: dict[str, str]
    received_at: datetime | None
    text: str = ""
    has_calendar_invite: bool = False


class GmailClient:
    """OAuth and Gmail API calls for the receptionists' mailboxes (one shared Google OAuth client)."""

    API_URL: ClassVar[str] = "https://gmail.googleapis.com/gmail/v1/users/me"
    TIMEOUT_SECONDS: ClassVar[float] = 20.0
    # A backlog of more pages of 500 history records is read like an expired id: the inbox's last day instead.
    MAX_HISTORY_PAGES: ClassVar[int] = 10
    RECENT_INBOX_QUERY: ClassVar[str] = "in:inbox newer_than:1d"
    RECENT_INBOX_MAX: ClassVar[int] = 50

    @property
    def is_configured(self) -> bool:
        """Whether the Google OAuth client and the mailboxes' redirect address are configured on the server."""
        return google_oauth_client.is_configured and bool(settings.google_mailbox_redirect_uri.strip())

    @staticmethod
    def authorization_url(state: str) -> str:
        """
        The Google consent page for a receptionist's mailbox.

        Args:
            state: The signed state that brings the answer back to its receptionist.

        Returns:
            The URL to open in the client's browser (offline access, consent shown every time).
        """
        return google_oauth_client.authorization_url(
            scopes=GMAIL_SCOPES, redirect_uri=settings.google_mailbox_redirect_uri.strip(), state=state
        )

    @staticmethod
    def drafts_url(account_email: str | None) -> str:
        """
        The drafts folder of a Gmail account, opened on that account when the browser holds several.

        Args:
            account_email: The connected address, when known.

        Returns:
            The Gmail web address of the drafts.
        """
        if not account_email:
            return "https://mail.google.com/mail/#drafts"
        return f"https://mail.google.com/mail/?authuser={quote(account_email, safe='@')}#drafts"

    async def exchange_code(self, code: str) -> GoogleTokens:
        """
        Exchange the consent code for tokens.

        Args:
            code: The ``code`` Google sent to the callback.

        Returns:
            The account's tokens and the scopes it actually granted.

        Raises:
            GmailError: When Google refuses the code.
        """
        try:
            return await google_oauth_client.exchange_code(
                code, redirect_uri=settings.google_mailbox_redirect_uri.strip(), timeout_seconds=self.TIMEOUT_SECONDS
            )
        except GoogleOAuthError as exc:
            raise GmailError(str(exc), needs_reconnect=exc.is_access_lost) from exc

    async def refresh(self, refresh_token: str) -> GoogleTokens:
        """
        A fresh access token.

        Args:
            refresh_token: The stored refresh token.

        Returns:
            The new tokens (the refresh token is kept unless Google sends another one).

        Raises:
            GmailError: ``needs_reconnect`` when the access was revoked or has expired.
        """
        try:
            return await google_oauth_client.refresh(refresh_token, timeout_seconds=self.TIMEOUT_SECONDS)
        except GoogleOAuthError as exc:
            raise GmailError(str(exc), needs_reconnect=exc.is_access_lost) from exc

    async def revoke(self, token: str) -> bool:
        """
        Revoke the account's grant: every token of it stops working, the agenda's too when it shares the account.

        Args:
            token: The stored refresh token.

        Returns:
            True when Google revoked it.
        """
        return await google_oauth_client.revoke(token, timeout_seconds=self.TIMEOUT_SECONDS)

    async def get_profile(self, access_token: str) -> GmailProfile:
        """
        The connected mailbox's address and current history id.

        Args:
            access_token: A valid access token.

        Returns:
            The profile.

        Raises:
            GmailError: When Gmail refuses the call (400: the account has no Gmail mailbox).
        """
        payload = await self._call("GET", f"{self.API_URL}/profile", access_token=access_token)
        address = str(payload.get("emailAddress") or "").strip().lower()
        history_id = str(payload.get("historyId") or "")
        if not address or not history_id:
            raise GmailError("Profil Gmail incomplet")
        return GmailProfile(email_address=address, history_id=history_id)

    async def changes_since(self, access_token: str, history_id: str) -> GmailChanges | None:
        """
        The emails received and the threads answered since a history id.

        Args:
            access_token: A valid access token.
            history_id: The history id the mailbox was read up to.

        Returns:
            The changes, the inbox messages in their arrival order; None when the id is too old or unknown, or the
            backlog too long to follow.

        Raises:
            GmailError: When Gmail refuses the call.
        """
        received: list[GmailMessageRef] = []
        seen: set[str] = set()
        answered: set[str] = set()
        latest = history_id
        page_token: str | None = None
        for page in range(self.MAX_HISTORY_PAGES):
            if page > 0 and not page_token:
                break
            params: list[tuple[str, str]] = [
                ("startHistoryId", history_id),
                ("historyTypes", "messageAdded"),
                ("historyTypes", "labelAdded"),
                ("maxResults", "500"),
            ]
            if page_token:
                params.append(("pageToken", page_token))
            try:
                payload = await self._call("GET", f"{self.API_URL}/history", access_token=access_token, params=params)
            except GmailError as exc:
                if exc.status_code == 404:
                    return None
                raise
            latest = str(payload.get("historyId") or latest)
            for record in payload.get("history") or []:
                if not isinstance(record, dict):
                    continue
                for added in record.get("messagesAdded") or []:
                    ref = self._ref(added.get("message") if isinstance(added, dict) else None)
                    if ref is None:
                        continue
                    if "SENT" in ref.label_ids:
                        answered.add(ref.thread_id)
                    elif "INBOX" in ref.label_ids and ref.message_id not in seen:
                        seen.add(ref.message_id)
                        received.append(ref)
                for labelled in record.get("labelsAdded") or []:
                    if isinstance(labelled, dict) and "SENT" in (labelled.get("labelIds") or []):
                        ref = self._ref(labelled.get("message"))
                        if ref is not None:
                            answered.add(ref.thread_id)
            page_token = payload.get("nextPageToken")
        if page_token:
            return None
        return GmailChanges(received=received, answered_thread_ids=frozenset(answered), history_id=latest)

    async def recent_inbox(self, access_token: str) -> list[GmailMessageRef]:
        """
        The inbox's messages of the last day, oldest first (when the history id is too old to follow).

        Args:
            access_token: A valid access token.

        Returns:
            The messages, without their labels.

        Raises:
            GmailError: When Gmail refuses the call.
        """
        payload = await self._call(
            "GET",
            f"{self.API_URL}/messages",
            access_token=access_token,
            params=[("q", self.RECENT_INBOX_QUERY), ("maxResults", str(self.RECENT_INBOX_MAX))],
        )
        refs = [self._ref(item) for item in payload.get("messages") or []]
        return [ref for ref in reversed(refs) if ref is not None]

    async def get_message(self, access_token: str, message_id: str, *, with_body: bool) -> GmailMessage | None:
        """
        One email: its headers and labels, and its text when asked.

        Args:
            access_token: A valid access token.
            message_id: The message.
            with_body: Read its parts (text, invitation) too, not only its headers.

        Returns:
            The email, or None when it no longer exists.

        Raises:
            GmailError: When Gmail refuses the call.
        """
        url = f"{self.API_URL}/messages/{quote(message_id, safe='')}"
        params = [("format", "full" if with_body else "metadata")]
        try:
            payload = await self._call("GET", url, access_token=access_token, params=params)
        except GmailError as exc:
            if exc.status_code == 404:
                return None
            raise
        body = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
        return GmailMessage(
            message_id=str(payload.get("id") or message_id),
            thread_id=str(payload.get("threadId") or ""),
            label_ids=frozenset(str(label) for label in payload.get("labelIds") or []),
            headers=GmailPayloadReader.headers(body),
            received_at=self._internal_date(payload.get("internalDate")),
            text=GmailPayloadReader.text(body) if with_body else "",
            has_calendar_invite=GmailPayloadReader.has_calendar_invite(body) if with_body else False,
        )

    async def create_draft(self, access_token: str, *, thread_id: str, raw: str) -> str:
        """
        Leave a reply as a draft in a thread; nothing is sent.

        Args:
            access_token: A valid access token.
            thread_id: The thread it answers.
            raw: The RFC 822 message, base64url-encoded.

        Returns:
            The draft's id.

        Raises:
            GmailError: When Gmail refuses the draft.
        """
        payload = await self._call(
            "POST",
            f"{self.API_URL}/drafts",
            access_token=access_token,
            json_body={"message": {"raw": raw, "threadId": thread_id}},
        )
        return str(payload.get("id") or "")

    async def _call(
        self,
        method: str,
        url: str,
        *,
        access_token: str,
        params: list[tuple[str, str]] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """An authenticated Gmail call; a dead token, missing scopes or a domain policy call for a new consent."""
        try:
            async with httpx.AsyncClient(timeout=self.TIMEOUT_SECONDS) as client:
                response = await client.request(
                    method, url, headers={"Authorization": f"Bearer {access_token}"}, params=params, json=json_body
                )
        except httpx.HTTPError as exc:
            raise GmailError("Gmail injoignable") from exc
        if response.status_code >= 400:
            error = google_oauth_client.json_object(response).get("error")
            details = error if isinstance(error, dict) else {}
            reasons = {str(item.get("reason")) for item in details.get("errors") or [] if isinstance(item, dict)}
            logger.warning("Gmail call refused (%s): %s", response.status_code, ", ".join(sorted(reasons)) or "-")
            # A rate limit is a 403 too: only a dead token, missing scopes or a domain policy need a new consent.
            raise GmailError(
                f"Gmail a refusé l'appel ({response.status_code})",
                needs_reconnect=response.status_code == 401
                or bool(reasons & {"insufficientPermissions", "domainPolicy"}),
                status_code=response.status_code,
            )
        return google_oauth_client.json_object(response)

    @staticmethod
    def _ref(message: object) -> GmailMessageRef | None:
        """A listed message, None when it carries no id."""
        if not isinstance(message, dict) or not message.get("id"):
            return None
        return GmailMessageRef(
            message_id=str(message["id"]),
            thread_id=str(message.get("threadId") or ""),
            label_ids=frozenset(str(label) for label in message.get("labelIds") or []),
        )

    @staticmethod
    def _internal_date(value: object) -> datetime | None:
        """Gmail's reception time (milliseconds since the epoch) as naive UTC."""
        try:
            return datetime.fromtimestamp(int(str(value)) / 1000, tz=UTC).replace(tzinfo=None)
        except (TypeError, ValueError, OverflowError, OSError):
            return None


gmail_client = GmailClient()
