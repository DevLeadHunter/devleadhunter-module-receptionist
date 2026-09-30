"""
« À relancer »: once its last automatic reminder (J+14) went, a sold receptionist whose « Pour démarrer » steps are
still missing is flagged for the operator to call, with those steps, in the dashboard list and on its detail page.
"""

import asyncio
from collections.abc import Iterator
from datetime import datetime
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

import api.v1.routes.ai_assistants as owner_routes
import services.ai_assistant.google_calendar_client as google_module
import services.ai_assistant.start_reminders as start_reminders_module
from enums.ai_assistant_calendar_status import AiAssistantCalendarStatus
from enums.ai_assistant_start_step import AiAssistantStartStep
from models.ai_assistant import AiAssistant
from models.ai_assistant_calendar import AiAssistantCalendar
from models.prospect_db import ProspectDB
from models.user import User
from services.ai_assistant.assistant_service import ai_assistant_service

_OPERATOR = SimpleNamespace(id=7, email="operateur@dibodev.fr")
_SOLD_ON = datetime(2026, 9, 1, 10, 0)


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    session = sessionmaker(bind=engine)()
    session.add(User(id=7, name="Dibodev", email="operateur@dibodev.fr", hashed_password="x"))
    session.commit()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def agenda_not_connected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Google is configured and no agenda is connected: the agenda counts as a missing step."""
    monkeypatch.setattr(google_module.settings, "google_client_id", "client-id")
    monkeypatch.setattr(google_module.settings, "google_client_secret", "client-secret")


def _assistant(db: Session, business_name: str, *, status: str = "delivered", **fields: Any) -> AiAssistant:
    prospect = ProspectDB(name=business_name, category="Couvreur", source="google", confidence=2, user_id=7)
    db.add(prospect)
    db.commit()
    assistant = ai_assistant_service.create(
        db, user_id=7, business_name=business_name, prospect_id=prospect.id, country="FR", use_brand_color=False
    )
    assistant.status = status
    for field, value in fields.items():
        setattr(assistant, field, value)
    db.commit()
    return assistant


def test_a_sold_receptionist_still_missing_steps_after_its_last_reminder_is_to_follow_up(db: Session) -> None:
    silent = _assistant(db, "Toitures Morel", delivered_at=_SOLD_ON, start_reminder_j14_sent_at=datetime(2026, 9, 15))
    halfway = _assistant(
        db,
        "Couverture Petit",
        delivered_at=_SOLD_ON,
        start_reminder_j14_sent_at=datetime(2026, 9, 15),
        alert_phone_e164="+33612345678",
        installed_at=datetime(2026, 9, 3),
        installed_host="couverture-petit.fr",
    )

    listed = {item.id: item for item in asyncio.run(owner_routes.list_assistants(None, _OPERATOR, db)).assistants}
    detail = asyncio.run(owner_routes.get_assistant(silent.id, _OPERATOR, db))

    assert listed[silent.id].needs_follow_up is True
    assert listed[silent.id].missing_start_steps == [
        AiAssistantStartStep.ALERT_PHONE,
        AiAssistantStartStep.GOOGLE_PROFILE_OR_WEBSITE,
        AiAssistantStartStep.GOOGLE_CALENDAR,
    ]
    assert (detail.needs_follow_up, detail.missing_start_steps) == (True, listed[silent.id].missing_start_steps)
    assert listed[halfway.id].needs_follow_up is True
    assert listed[halfway.id].missing_start_steps == [AiAssistantStartStep.GOOGLE_CALENDAR]


def test_no_follow_up_before_the_last_reminder_once_everything_is_in_place_or_for_a_demo(db: Session) -> None:
    reminders_running = _assistant(db, "Toitures Morel", delivered_at=_SOLD_ON)
    ready = _assistant(
        db,
        "Couverture Petit",
        delivered_at=_SOLD_ON,
        start_reminder_j14_sent_at=datetime(2026, 9, 15),
        alert_phone_e164="+33612345678",
        google_profile_linked_at=datetime(2026, 9, 2),
    )
    demo = _assistant(db, "Démo Dupont", status="active")
    db.add(AiAssistantCalendar(user_id=7, assistant_id=ready.id, status=AiAssistantCalendarStatus.CONNECTED.value))
    db.commit()

    listed = {item.id: item for item in asyncio.run(owner_routes.list_assistants(None, _OPERATOR, db)).assistants}

    assert listed[reminders_running.id].needs_follow_up is False
    assert len(listed[reminders_running.id].missing_start_steps) == 3
    assert (listed[ready.id].needs_follow_up, listed[ready.id].missing_start_steps) == (False, [])
    assert (listed[demo.id].needs_follow_up, listed[demo.id].missing_start_steps) == (False, [])


def test_the_reminder_email_words_each_missing_step_for_the_business(db: Session) -> None:
    assistant = _assistant(db, "Toitures Morel", delivered_at=_SOLD_ON)
    reminders = start_reminders_module.ai_assistant_start_reminders

    wording = [reminders.client_wording(step, assistant) for step in reminders.missing_steps(db, assistant)]

    assert wording == [
        "votre numéro de mobile, pour recevoir les demandes par SMS",
        f"l'adresse de {assistant.assistant_name} sur votre fiche Google, ou la ligne à coller sur votre site",
        "votre agenda Google, pour que les rendez-vous s'y posent tout seuls",
    ]


def test_the_list_reads_every_agenda_in_one_query_and_agrees_with_each_detail_page(db: Session, engine: Engine) -> None:
    # Sold, reminded at J+14, mobile and Google profile given: only the agenda sets them apart.
    all_steps_but_the_agenda = {
        "delivered_at": _SOLD_ON,
        "start_reminder_j14_sent_at": datetime(2026, 9, 15),
        "alert_phone_e164": "+33612345678",
        "google_profile_linked_at": datetime(2026, 9, 2),
    }
    connected = _assistant(db, "Toitures Morel", **all_steps_but_the_agenda)
    lost = _assistant(db, "Couverture Petit", **all_steps_but_the_agenda)
    never_connected = _assistant(db, "Charpente Leroy", **all_steps_but_the_agenda)
    demo = _assistant(db, "Démo Dupont", status="active")
    db.add_all(
        [
            AiAssistantCalendar(user_id=7, assistant_id=connected.id, status=AiAssistantCalendarStatus.CONNECTED.value),
            AiAssistantCalendar(user_id=7, assistant_id=lost.id, status=AiAssistantCalendarStatus.ERROR.value),
        ]
    )
    db.commit()
    calendar_queries: list[str] = []

    def record_calendar_query(_connection: Any, _cursor: Any, statement: str, *_: Any) -> None:
        if "ai_assistant_calendars" in statement:
            calendar_queries.append(statement)

    event.listen(engine, "before_cursor_execute", record_calendar_query)
    listed = {item.id: item for item in asyncio.run(owner_routes.list_assistants(None, _OPERATOR, db)).assistants}
    event.remove(engine, "before_cursor_execute", record_calendar_query)

    listed_steps_and_follow_up = {
        assistant_id: (item.missing_start_steps, item.needs_follow_up) for assistant_id, item in listed.items()
    }
    assert len(calendar_queries) == 1
    assert listed_steps_and_follow_up == {
        connected.id: ([], False),
        lost.id: ([AiAssistantStartStep.GOOGLE_CALENDAR], True),
        never_connected.id: ([AiAssistantStartStep.GOOGLE_CALENDAR], True),
        demo.id: ([], False),
    }
    for assistant_id, item in listed.items():
        detail = asyncio.run(owner_routes.get_assistant(assistant_id, _OPERATOR, db))
        assert (detail.missing_start_steps, detail.needs_follow_up) == (item.missing_start_steps, item.needs_follow_up)


def test_without_google_on_the_server_the_agenda_is_never_a_missing_step(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(google_module.settings, "google_client_id", "")
    assistant = _assistant(
        db, "Toitures Morel", delivered_at=_SOLD_ON, start_reminder_j14_sent_at=datetime(2026, 9, 15)
    )

    [listed] = asyncio.run(owner_routes.list_assistants(None, _OPERATOR, db)).assistants
    detail = asyncio.run(owner_routes.get_assistant(assistant.id, _OPERATOR, db))

    assert listed.missing_start_steps == [
        AiAssistantStartStep.ALERT_PHONE,
        AiAssistantStartStep.GOOGLE_PROFILE_OR_WEBSITE,
    ]
    assert detail.missing_start_steps == listed.missing_start_steps
