"""
Google Calendar for a sold assistant: the client's consent, its tokens, and the two calls booking needs.

The client connects their own Google account from the client space. The scopes are their address (to show
which account is connected), their events (to create the appointment) and their availability (the free/busy
query does not accept the events scope). Every call is a plain HTTPS request (httpx), mocked in tests.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar
from urllib.parse import quote, urlencode

import httpx

from core.config import settings

logger = logging.getLogger(__name__)

GOOGLE_CALENDAR_EVENTS_SCOPE = "https://www.googleapis.com/auth/calendar.events"
GOOGLE_CALENDAR_FREEBUSY_SCOPE = "https://www.googleapis.com/auth/calendar.freebusy"
GOOGLE_CALENDAR_SCOPES: tuple[str, ...] = (
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    GOOGLE_CALENDAR_EVENTS_SCOPE,
    GOOGLE_CALENDAR_FREEBUSY_SCOPE,
)


class GoogleCalendarError(Exception):
    """A Google call that failed; ``needs_reconnect`` when the client must connect their agenda again."""

    def __init__(self, message: str, *, needs_reconnect: bool = False, status_code: int | None = None) -> None:
        super().__init__(message)
        self.needs_reconnect = needs_reconnect
        self.status_code = status_code


@dataclass(frozen=True)
class GoogleTokens:
    """Tokens of a Google account; ``expires_at`` is naive UTC."""

    access_token: str
    refresh_token: str | None
    expires_at: datetime
    scopes: frozenset[str]


@dataclass(frozen=True)
class BusyPeriod:
    """A busy stretch of the agenda, naive UTC, end excluded."""

    start: datetime
    end: datetime


@dataclass(frozen=True)
class CalendarEventDraft:
    """The event created for a booked appointment; times are aware (business time zone)."""

    event_id: str
    summary: str
    description: str
    start: datetime
    end: datetime
    time_zone: str
    request_id: int


class GoogleCalendarClient:
    """OAuth and Calendar API calls for the assistants' agendas (one shared Google OAuth client)."""

    AUTHORIZATION_URL: ClassVar[str] = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL: ClassVar[str] = "https://oauth2.googleapis.com/token"
    REVOKE_URL: ClassVar[str] = "https://oauth2.googleapis.com/revoke"
    USERINFO_URL: ClassVar[str] = "https://www.googleapis.com/oauth2/v2/userinfo"
    FREEBUSY_URL: ClassVar[str] = "https://www.googleapis.com/calendar/v3/freeBusy"
    EVENTS_URL: ClassVar[str] = "https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"
    TIMEOUT_SECONDS: ClassVar[float] = 15.0

    @property
    def is_configured(self) -> bool:
        """Whether the Google OAuth client is configured on the server."""
        return bool(settings.google_client_id and settings.google_client_secret)

    @staticmethod
    def authorization_url(state: str) -> str:
        """
        The Google consent page for an assistant's agenda.

        Args:
            state: The signed state that brings the answer back to its assistant.

        Returns:
            The URL to open in the client's browser (offline access, consent shown every time).
        """
        query = urlencode(
            {
                "client_id": settings.google_client_id,
                "redirect_uri": settings.google_calendar_redirect_uri,
                "response_type": "code",
                "scope": " ".join(GOOGLE_CALENDAR_SCOPES),
                "access_type": "offline",
                "prompt": "consent",
                "include_granted_scopes": "true",
                "state": state,
            },
            quote_via=quote,
        )
        return f"{GoogleCalendarClient.AUTHORIZATION_URL}?{query}"

    async def exchange_code(self, code: str) -> GoogleTokens:
        """
        Exchange the consent code for tokens.

        Args:
            code: The ``code`` Google sent to the callback.

        Returns:
            The account's tokens and the scopes it actually granted.

        Raises:
            GoogleCalendarError: When Google refuses the code.
        """
        payload = await self._token_request(
            {
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_calendar_redirect_uri,
                "grant_type": "authorization_code",
            }
        )
        return self._tokens(payload, refresh_token=payload.get("refresh_token"))

    async def refresh(self, refresh_token: str) -> GoogleTokens:
        """
        A fresh access token.

        Args:
            refresh_token: The stored refresh token.

        Returns:
            The new tokens (the refresh token is kept unless Google sends another one).

        Raises:
            GoogleCalendarError: ``needs_reconnect`` when the access was revoked or has expired.
        """
        payload = await self._token_request(
            {
                "refresh_token": refresh_token,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "grant_type": "refresh_token",
            }
        )
        return self._tokens(payload, refresh_token=payload.get("refresh_token") or refresh_token)

    async def account_email(self, access_token: str) -> str | None:
        """
        The verified address of the connected Google account.

        Args:
            access_token: A valid access token.

        Returns:
            The address, or None when Google does not vouch for it.
        """
        payload = await self._call("GET", self.USERINFO_URL, access_token=access_token)
        email = payload.get("email")
        return str(email) if email and payload.get("verified_email") else None

    async def busy_periods(
        self, access_token: str, calendar_id: str, *, start: datetime, end: datetime
    ) -> list[BusyPeriod]:
        """
        The busy stretches of an agenda between two moments.

        Args:
            access_token: A valid access token.
            calendar_id: The agenda (``primary`` for the account's main one).
            start: Start of the window, naive UTC.
            end: End of the window, naive UTC.

        Returns:
            The busy periods, naive UTC.

        Raises:
            GoogleCalendarError: When the agenda cannot be read.
        """
        payload = await self._call(
            "POST",
            self.FREEBUSY_URL,
            access_token=access_token,
            json_body={
                "timeMin": self._rfc3339(start),
                "timeMax": self._rfc3339(end),
                "items": [{"id": calendar_id}],
            },
        )
        calendars: dict[str, Any] = payload.get("calendars") or {}
        entry = calendars.get(calendar_id) or (next(iter(calendars.values())) if len(calendars) == 1 else None)
        if not isinstance(entry, dict):
            raise GoogleCalendarError("Agenda absent de la réponse de Google")
        if entry.get("errors"):
            reasons = ", ".join(str(error.get("reason")) for error in entry["errors"] if isinstance(error, dict))
            raise GoogleCalendarError(f"Agenda illisible ({reasons or 'erreur inconnue'})")
        periods: list[BusyPeriod] = []
        for busy in entry.get("busy") or []:
            try:
                periods.append(BusyPeriod(start=self._parse(busy["start"]), end=self._parse(busy["end"])))
            except (KeyError, TypeError, ValueError):
                continue
        return periods

    async def insert_event(self, access_token: str, calendar_id: str, draft: CalendarEventDraft) -> str:
        """
        Create the appointment in the agenda (idempotent: the event id is ours).

        Args:
            access_token: A valid access token.
            calendar_id: The agenda.
            draft: The event.

        Returns:
            The Google event id.

        Raises:
            GoogleCalendarError: When Google refuses the event.
        """
        body = {
            "id": draft.event_id,
            "summary": draft.summary,
            "description": draft.description,
            "start": {"dateTime": draft.start.isoformat(), "timeZone": draft.time_zone},
            "end": {"dateTime": draft.end.isoformat(), "timeZone": draft.time_zone},
            "extendedProperties": {"private": {"devleadhunterRequestId": str(draft.request_id)}},
        }
        url = self.EVENTS_URL.format(calendar_id=quote(calendar_id, safe=""))
        try:
            payload = await self._call("POST", url, access_token=access_token, json_body=body)
        except GoogleCalendarError as exc:
            # A retry after a lost answer: the event with our id already exists.
            if exc.status_code == 409:
                return draft.event_id
            raise
        return str(payload.get("id") or draft.event_id)

    async def revoke(self, token: str) -> None:
        """Revoke a token at Google (best effort: a token already dead is fine)."""
        try:
            async with httpx.AsyncClient(timeout=self.TIMEOUT_SECONDS) as client:
                await client.post(self.REVOKE_URL, data={"token": token})
        except httpx.HTTPError:
            logger.warning("Google token revocation failed", exc_info=True)

    async def _token_request(self, form: dict[str, str]) -> dict[str, Any]:
        """POST to the token endpoint; an ``invalid_grant`` means the client must connect again."""
        try:
            async with httpx.AsyncClient(timeout=self.TIMEOUT_SECONDS) as client:
                response = await client.post(self.TOKEN_URL, data=form)
        except httpx.HTTPError as exc:
            raise GoogleCalendarError("Google injoignable") from exc
        if response.status_code >= 400:
            error = self._json(response).get("error")
            logger.warning("Google token endpoint refused (%s): %s", response.status_code, error)
            raise GoogleCalendarError(
                f"Google a refusé l'accès ({error or response.status_code})",
                needs_reconnect=error in ("invalid_grant", "unauthorized_client"),
            )
        return self._json(response)

    async def _call(
        self, method: str, url: str, *, access_token: str, json_body: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """An authenticated Calendar call; 401 and 403 mean the access is gone or too narrow."""
        try:
            async with httpx.AsyncClient(timeout=self.TIMEOUT_SECONDS) as client:
                response = await client.request(
                    method, url, headers={"Authorization": f"Bearer {access_token}"}, json=json_body
                )
        except httpx.HTTPError as exc:
            raise GoogleCalendarError("Google Agenda injoignable") from exc
        if response.status_code >= 400:
            error = self._json(response).get("error")
            details = error if isinstance(error, dict) else {}
            reasons = {str(item.get("reason")) for item in details.get("errors") or [] if isinstance(item, dict)}
            logger.warning("Google Calendar call refused (%s): %s", response.status_code, details.get("message"))
            # Only a dead token or missing scopes call for a new consent (not a rate limit, not a read-only agenda).
            raise GoogleCalendarError(
                f"Google Agenda a refusé l'appel ({response.status_code})",
                needs_reconnect=response.status_code == 401 or "insufficientPermissions" in reasons,
                status_code=response.status_code,
            )
        return self._json(response)

    @staticmethod
    def _tokens(payload: dict[str, Any], *, refresh_token: str | None) -> GoogleTokens:
        """Tokens read from a token-endpoint answer."""
        access_token = payload.get("access_token")
        if not access_token:
            raise GoogleCalendarError("Réponse de Google sans jeton d'accès")
        expires_in = int(payload.get("expires_in") or 3600)
        return GoogleTokens(
            access_token=str(access_token),
            refresh_token=str(refresh_token) if refresh_token else None,
            expires_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(seconds=expires_in),
            scopes=frozenset(str(payload.get("scope") or "").split()),
        )

    @staticmethod
    def _json(response: httpx.Response) -> dict[str, Any]:
        """A response's JSON object (empty when it has none)."""
        try:
            payload = response.json()
        except ValueError:
            return {}
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _rfc3339(moment: datetime) -> str:
        """A naive UTC moment in RFC 3339."""
        return moment.replace(tzinfo=UTC).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _parse(value: str) -> datetime:
        """An RFC 3339 moment as naive UTC."""
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC).replace(tzinfo=None)


google_calendar_client = GoogleCalendarClient()
