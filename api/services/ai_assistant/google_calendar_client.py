"""
Google Calendar for a sold assistant: the client's consent, its tokens, and the calls booking needs.

The client connects their own Google account from the client space. The scopes are their address (to show
which account is connected), their events (to create the appointment) and their availability (the free/busy
query does not accept the events scope). The OAuth steps are those of every Google integration
(``google_oauth_client``); every call is a plain HTTPS request (httpx), mocked in tests.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, ClassVar
from urllib.parse import quote

import httpx

from core.config import settings
from services.google_oauth_client import GoogleOAuthError, GoogleTokens, google_oauth_client

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
class BusyPeriod:
    """A busy stretch of the agenda, naive UTC, end excluded."""

    start: datetime
    end: datetime


@dataclass(frozen=True)
class CalendarEventState:
    """An event of ours as the agenda holds it now: cancelled or not, and its start (naive UTC) when timed."""

    cancelled: bool
    start: datetime | None


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

    FREEBUSY_URL: ClassVar[str] = "https://www.googleapis.com/calendar/v3/freeBusy"
    EVENTS_URL: ClassVar[str] = "https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"
    EVENT_URL: ClassVar[str] = "https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events/{event_id}"
    TIMEOUT_SECONDS: ClassVar[float] = 15.0

    @property
    def is_configured(self) -> bool:
        """Whether the Google OAuth client is configured on the server."""
        return google_oauth_client.is_configured

    @staticmethod
    def authorization_url(state: str) -> str:
        """
        The Google consent page for an assistant's agenda.

        Args:
            state: The signed state that brings the answer back to its assistant.

        Returns:
            The URL to open in the client's browser (offline access, consent shown every time).
        """
        return google_oauth_client.authorization_url(
            scopes=GOOGLE_CALENDAR_SCOPES,
            redirect_uri=settings.google_calendar_redirect_uri,
            state=state,
            include_granted_scopes=True,
        )

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
        try:
            return await google_oauth_client.exchange_code(
                code, redirect_uri=settings.google_calendar_redirect_uri, timeout_seconds=self.TIMEOUT_SECONDS
            )
        except GoogleOAuthError as exc:
            raise GoogleCalendarError(str(exc), needs_reconnect=exc.is_access_lost) from exc

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
        try:
            return await google_oauth_client.refresh(refresh_token, timeout_seconds=self.TIMEOUT_SECONDS)
        except GoogleOAuthError as exc:
            raise GoogleCalendarError(str(exc), needs_reconnect=exc.is_access_lost) from exc

    async def account_email(self, access_token: str) -> str | None:
        """
        The verified address of the connected Google account.

        Args:
            access_token: A valid access token.

        Returns:
            The address, or None when Google does not vouch for it.

        Raises:
            GoogleCalendarError: When Google refuses the token or does not answer.
        """
        try:
            profile = await google_oauth_client.user_info(access_token, timeout_seconds=self.TIMEOUT_SECONDS)
        except GoogleOAuthError as exc:
            if exc.status_code is None:
                raise GoogleCalendarError("Google Agenda injoignable") from exc
            raise GoogleCalendarError(
                f"Google Agenda a refusé l'appel ({exc.status_code})",
                needs_reconnect=exc.status_code == 401,
                status_code=exc.status_code,
            ) from exc
        email = profile.get("email")
        return str(email) if email and profile.get("verified_email") else None

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
            reasons = [str(error.get("reason")) for error in entry["errors"] if isinstance(error, dict)]
            # freeBusy answers 200 even for an agenda it cannot find: keep the status a client can act on.
            status_code = 404 if "notFound" in reasons else None
            raise GoogleCalendarError(
                f"Agenda illisible ({', '.join(reasons) or 'erreur inconnue'})", status_code=status_code
            )
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

    async def get_event(self, access_token: str, calendar_id: str, event_id: str) -> CalendarEventState | None:
        """
        What became of an event we created: still there (and when), cancelled, or gone.

        Args:
            access_token: A valid access token.
            calendar_id: The agenda.
            event_id: The event's id (ours).

        Returns:
            The event's state, or None when the agenda no longer has it.

        Raises:
            GoogleCalendarError: When the agenda cannot be read.
        """
        url = self.EVENT_URL.format(calendar_id=quote(calendar_id, safe=""), event_id=quote(event_id, safe=""))
        try:
            payload = await self._call("GET", url, access_token=access_token)
        except GoogleCalendarError as exc:
            if exc.status_code in (404, 410):
                return None
            raise
        start_value = (payload.get("start") or {}).get("dateTime")
        start = self._parse(str(start_value)) if start_value else None
        return CalendarEventState(cancelled=payload.get("status") == "cancelled", start=start)

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
            error = google_oauth_client.json_object(response).get("error")
            details = error if isinstance(error, dict) else {}
            reasons = {str(item.get("reason")) for item in details.get("errors") or [] if isinstance(item, dict)}
            logger.warning("Google Calendar call refused (%s): %s", response.status_code, details.get("message"))
            # Only a dead token or missing scopes call for a new consent (not a rate limit, not a read-only agenda).
            raise GoogleCalendarError(
                f"Google Agenda a refusé l'appel ({response.status_code})",
                needs_reconnect=response.status_code == 401 or "insufficientPermissions" in reasons,
                status_code=response.status_code,
            )
        return google_oauth_client.json_object(response)

    @staticmethod
    def _rfc3339(moment: datetime) -> str:
        """A naive UTC moment in RFC 3339."""
        return moment.replace(tzinfo=UTC).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _parse(value: str) -> datetime:
        """An RFC 3339 moment as naive UTC."""
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC).replace(tzinfo=None)


google_calendar_client = GoogleCalendarClient()
