"""
What the agenda tests share: a Google that never leaves the process, a garage's assistant, its agenda, a request.

Times are September 2026 in Paris (UTC+2); stored times are naive UTC.
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

import services.ai_assistant.google_calendar_client as google_module
from enums.ai_assistant_calendar_status import AiAssistantCalendarStatus
from models.ai_assistant import AiAssistant
from models.ai_assistant_calendar import AiAssistantCalendar
from models.ai_assistant_request import AiAssistantRequest
from models.prospect_db import ProspectDB
from models.sms_config import SmsConfig
from services.ai_assistant.assistant_service import ai_assistant_service
from services.ai_assistant.google_calendar_client import (
    BusyPeriod,
    CalendarEventDraft,
    CalendarEventState,
    GoogleCalendarError,
)
from services.encryption_service import encryption_service
from services.google_oauth_client import GoogleTokens

PARIS = ZoneInfo("Europe/Paris")
# Monday 21 September 2026, 10:00 in Paris (08:00 UTC).
MONDAY_10H = datetime(2026, 9, 21, 10, 0, tzinfo=PARIS)
WEEK = [
    {"day": name, "hours": "08:00–12:00, 14:00–18:00"} for name in ("lundi", "mardi", "mercredi", "jeudi", "vendredi")
] + [{"day": "samedi", "hours": "Fermé"}, {"day": "dimanche", "hours": "Fermé"}]
GRANTED_SCOPES = frozenset(
    {
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        google_module.GOOGLE_CALENDAR_EVENTS_SCOPE,
        google_module.GOOGLE_CALENDAR_FREEBUSY_SCOPE,
    }
)


def paris(day: int, hour: int, minute: int = 0) -> datetime:
    """A moment of September 2026 in Paris."""
    return datetime(2026, 9, day, hour, minute, tzinfo=PARIS)


def utc(moment: datetime) -> datetime:
    """A moment as the database stores it: naive UTC."""
    return moment.astimezone(UTC).replace(tzinfo=None)


class FakeGoogle:
    """What Google answers: busy periods, created events, tokens."""

    def __init__(self) -> None:
        self.busy: list[BusyPeriod] = []
        self.busy_calls: list[tuple[datetime, datetime]] = []
        self.inserted: list[CalendarEventDraft] = []
        self.refreshed: list[str] = []
        self.failure: GoogleCalendarError | None = None
        # Failures answered to the next free/busy calls, one each, before the agenda answers normally.
        self.busy_failures: list[GoogleCalendarError] = []
        self.insert_failures: list[GoogleCalendarError] = []
        self.insert_calls = 0
        self.account = "garage.morel@gmail.com"
        self.scopes: frozenset[str] = GRANTED_SCOPES
        # What ``get_event`` answers per event id; an inserted event not listed here still stands at its time.
        self.event_states: dict[str, CalendarEventState | None] = {}
        self.event_reads: list[str] = []

    async def busy_periods(self, access_token: str, calendar_id: str, *, start: datetime, end: datetime) -> list:
        if self.failure is not None:
            raise self.failure
        if self.busy_failures:
            raise self.busy_failures.pop(0)
        self.busy_calls.append((start, end))
        return list(self.busy)

    async def get_event(self, access_token: str, calendar_id: str, event_id: str) -> CalendarEventState | None:
        if self.failure is not None:
            raise self.failure
        self.event_reads.append(event_id)
        if event_id in self.event_states:
            return self.event_states[event_id]
        for draft in self.inserted:
            if draft.event_id == event_id:
                return CalendarEventState(cancelled=False, start=draft.start.astimezone(UTC).replace(tzinfo=None))
        return None

    async def insert_event(self, access_token: str, calendar_id: str, draft: CalendarEventDraft) -> str:
        self.insert_calls += 1
        if self.failure is not None:
            raise self.failure
        if self.insert_failures:
            raise self.insert_failures.pop(0)
        self.inserted.append(draft)
        return draft.event_id

    async def refresh(self, refresh_token: str) -> GoogleTokens:
        if self.failure is not None:
            raise self.failure
        self.refreshed.append(refresh_token)
        return GoogleTokens(
            access_token="fresh-access",
            refresh_token=refresh_token,
            expires_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=1),
            scopes=self.scopes,
        )

    async def exchange_code(self, code: str) -> GoogleTokens:
        if code == "refused":
            raise GoogleCalendarError("Google a refusé l'accès (invalid_grant)")
        return GoogleTokens(
            access_token="access-1",
            refresh_token="refresh-1",
            expires_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=1),
            scopes=self.scopes,
        )

    async def account_email(self, access_token: str) -> str | None:
        return self.account


def add_assistant(db: Session, *, status: str = "delivered", hours: list[dict[str, str]] | None = WEEK) -> AiAssistant:
    """A garage's assistant (sold by default) with its hours, phone and address, and the operator's SMS sender."""
    prospect = ProspectDB(name="Garage Morel", category="Garage", source="google", confidence=2, user_id=7)
    db.add(prospect)
    db.commit()
    assistant = ai_assistant_service.create(
        db, user_id=7, business_name="Garage Morel", prospect_id=prospect.id, country="FR", use_brand_color=False
    )
    assistant.knowledge_json = {
        **(assistant.knowledge_json or {}),
        "opening_hours": hours,
        "identity": {
            "business_name": "Garage Morel",
            "phone": "03 83 12 34 56",
            "address": "12 rue des Lilas, 54000 Nancy",
        },
    }
    assistant.status = status
    assistant.email = "contact@garage-morel.fr"
    if db.query(SmsConfig).filter(SmsConfig.user_id == 7).first() is None:
        db.add(SmsConfig(user_id=7, sender="Dibodev"))
    db.commit()
    return assistant


def add_calendar(db: Session, assistant: AiAssistant, **fields: Any) -> AiAssistantCalendar:
    """The assistant's Google agenda, connected, its tokens encrypted (``fields`` override the defaults)."""
    values: dict[str, Any] = {
        "user_id": assistant.user_id,
        "assistant_id": assistant.id,
        "account_email": "garage.morel@gmail.com",
        "access_token_encrypted": encryption_service.encrypt("access-0"),
        "refresh_token_encrypted": encryption_service.encrypt("refresh-0"),
        "token_expires_at": datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=1),
        "status": AiAssistantCalendarStatus.CONNECTED.value,
    }
    values.update(fields)
    calendar = AiAssistantCalendar(**values)
    db.add(calendar)
    db.commit()
    return calendar


def add_request(db: Session, assistant: AiAssistant, **fields: Any) -> AiAssistantRequest:
    """Julie Roux's request to the assistant, a mobile as contact (``fields`` override the defaults)."""
    values: dict[str, Any] = {
        "user_id": assistant.user_id,
        "prospect_id": assistant.prospect_id,
        "assistant_id": assistant.id,
        "name": "Julie Roux",
        "contact": "06 11 22 33 44",
        "need": "Vidange et plaquettes",
        "language": "fr",
        "session_id": "session-1",
    }
    values.update(fields)
    request = AiAssistantRequest(**values)
    db.add(request)
    db.commit()
    return request
