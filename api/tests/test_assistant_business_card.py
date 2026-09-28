"""
The page a sold receptionist's customers reach: the business's card (phone, address, hours) on the public config.

A demo carries no card. A sold assistant carries what its receptionist may say: nothing from the Google listing once
the business switched that source off.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from types import SimpleNamespace
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from core.database import Base
from models.prospect_db import ProspectDB
from services.ai_assistant.assistant_service import ai_assistant_service
from services.ai_assistant.business_card import AiAssistantBusinessCard
from services.ai_assistant.opening_hours import OpeningHoursCalendar

_HOURS: list[dict[str, str]] = [
    {"day": "lundi", "hours": "08:00–12:00, 14:00–18:00"},
    {"day": "mardi", "hours": "08:00–12:00, 14:00–18:00"},
    {"day": "samedi (Assomption)", "hours": "Fermé"},
    {"day": "dimanche", "hours": "Fermé"},
]
_A_MONDAY = datetime(2026, 9, 28, 10, 0)
_A_MONDAY_LUNCH = datetime(2026, 9, 28, 12, 30)
_A_SUNDAY = datetime(2026, 9, 27, 10, 0)


def _sold_assistant(phone: str | None = None, **knowledge_changes: Any) -> SimpleNamespace:
    """A sold assistant as the card reads it: its dashboard phone and its knowledge."""
    knowledge: dict[str, Any] = {
        "identity": {
            "business_name": "Toitures Morel",
            "phone": "02 99 12 34 56",
            "address": "12 rue des Lilas, 35000 Rennes",
        },
        "opening_hours": _HOURS,
    }
    knowledge.update(knowledge_changes)
    return SimpleNamespace(phone=phone, knowledge_json=knowledge)


def test_the_fixed_days_are_the_weekdays_they_claim() -> None:
    assert _A_MONDAY.weekday() == 0
    assert _A_MONDAY_LUNCH.weekday() == 0
    assert _A_SUNDAY.weekday() == 6


def test_a_sold_business_card_carries_its_phone_address_and_hours() -> None:
    card = AiAssistantBusinessCard.of(_sold_assistant(), now=_A_MONDAY)

    assert card.phone == "02 99 12 34 56"
    assert card.address == "12 rue des Lilas, 35000 Rennes"
    assert [(row.day, row.hours) for row in card.opening_hours] == [(row["day"], row["hours"]) for row in _HOURS]


def test_today_is_pointed_out_in_the_hours() -> None:
    monday = AiAssistantBusinessCard.of(_sold_assistant(), now=_A_MONDAY)
    sunday = AiAssistantBusinessCard.of(_sold_assistant(), now=_A_SUNDAY)

    assert [row.is_today for row in monday.opening_hours] == [True, False, False, False]
    assert [row.is_today for row in sunday.opening_hours] == [False, False, False, True]


def test_the_card_says_whether_the_business_is_open_right_now() -> None:
    open_card = AiAssistantBusinessCard.of(_sold_assistant(), now=_A_MONDAY)
    closed_card = AiAssistantBusinessCard.of(_sold_assistant(), now=_A_MONDAY_LUNCH)
    unknown_card = AiAssistantBusinessCard.of(_sold_assistant(opening_hours=[]), now=_A_MONDAY)

    assert open_card.is_open_now is True
    assert closed_card.is_open_now is False
    assert unknown_card.is_open_now is None


def test_the_card_carries_the_listing_rating_and_drops_a_count_without_rating() -> None:
    rated = AiAssistantBusinessCard.of(_sold_assistant(), google_rating=4.8, google_reviews_count=57, now=_A_MONDAY)
    unrated = AiAssistantBusinessCard.of(_sold_assistant(), google_rating=None, google_reviews_count=57, now=_A_MONDAY)

    assert (rated.google_rating, rated.google_reviews_count) == (4.8, 57)
    assert (unrated.google_rating, unrated.google_reviews_count) == (None, None)


def test_the_phone_set_in_the_dashboard_wins_over_the_listing() -> None:
    card = AiAssistantBusinessCard.of(_sold_assistant(phone=" 06 11 22 33 44 "), now=_A_MONDAY)

    assert card.phone == "06 11 22 33 44"


def test_a_listing_switched_off_leaves_only_the_dashboard_phone() -> None:
    assistant = _sold_assistant(phone="06 11 22 33 44", sources={"listing": False})

    card = AiAssistantBusinessCard.of(assistant, google_rating=4.8, google_reviews_count=57, now=_A_MONDAY)

    assert card.phone == "06 11 22 33 44"
    assert card.address is None
    assert card.opening_hours == []
    assert card.is_open_now is None
    assert card.google_rating is None


def test_unreadable_rows_stay_out_of_the_hours() -> None:
    assistant = _sold_assistant(opening_hours=[{"day": "lundi", "hours": ""}, {"day": "", "hours": "09:00–18:00"}])

    card = AiAssistantBusinessCard.of(assistant, now=_A_MONDAY)

    assert card.opening_hours == []


def test_a_weekday_is_read_in_every_listing_language_and_through_annotations() -> None:
    assert OpeningHoursCalendar.weekday_of("lundi") == 0
    assert OpeningHoursCalendar.weekday_of("Samedi (Assomption)") == 5
    assert OpeningHoursCalendar.weekday_of("Montag") == 0
    assert OpeningHoursCalendar.weekday_of("zondag") == 6
    assert OpeningHoursCalendar.weekday_of("jour férié") is None


def test_the_public_config_carries_the_card_only_once_sold() -> None:
    from api.v1.routes.ai_assistant_widget import get_public_assistant

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db: Session = sessionmaker(bind=engine)()
    prospect = ProspectDB(
        name="Toitures Morel",
        category="Couvreur",
        source="google",
        confidence=2,
        user_id=7,
        google_rating=4.8,
        google_reviews_count=57,
    )
    db.add(prospect)
    db.commit()
    assistant = ai_assistant_service.create(
        db, user_id=7, business_name="Toitures Morel", prospect_id=prospect.id, country="FR", use_brand_color=False
    )
    assistant.knowledge_json = {
        "identity": {"business_name": "Toitures Morel", "phone": "02 99 12 34 56", "address": "12 rue des Lilas"},
        "opening_hours": _HOURS,
    }
    db.commit()

    demo = asyncio.run(get_public_assistant(assistant.slug, db))
    assistant.status = "delivered"
    db.commit()
    sold = asyncio.run(get_public_assistant(assistant.slug, db))

    assert demo.business is None
    assert sold.business is not None
    assert sold.business.phone == "02 99 12 34 56"
    assert sold.business.address == "12 rue des Lilas"
    assert len(sold.business.opening_hours) == len(_HOURS)
    assert (sold.business.google_rating, sold.business.google_reviews_count) == (4.8, 57)
