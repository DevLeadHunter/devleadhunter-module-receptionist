"""
The demo space a prospect opens from its demo page: only a live demo has one, it lists the requests of the visitor's
own widget sessions and nobody else's, completes them with flagged examples of the trade, keeps the client space's
contract, and reads without writing, counting or announcing anything.

The database is an in-memory SQLite; routes are called directly.
"""

import asyncio
import json
from collections.abc import Iterator
from datetime import UTC, datetime, time, timedelta
from typing import Any

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from starlette.routing import Match

import api.v1.routes.ai_assistant_client_space as routes
import api.v1.routes.ai_assistant_widget as widget_routes
import services.ai_assistant.message_delivery as delivery_module
from core.config import settings
from enums.ai_assistant_persona_gender import AiAssistantPersonaGender
from enums.ai_assistant_request import AiAssistantRequestStatus
from enums.ai_assistant_trade import AiAssistantTrade
from main import app
from models.ai_assistant import AiAssistant
from models.ai_assistant_conversation import AiAssistantConversation
from models.ai_assistant_message import AiAssistantMessage
from models.ai_assistant_request import AiAssistantRequest
from models.prospect_db import ProspectDB
from models.user import User
from schemas.ai_assistant_client_space import (
    AiAssistantClientRequestItem,
    AiAssistantClientSettingsUpdate,
    AiAssistantClientSpaceResponse,
)
from schemas.ai_assistant_demo_space import AiAssistantDemoSpaceRequest, AiAssistantDemoSpaceResponse
from services.ai_assistant.appointment_slots import AiAssistantAppointmentSlots, AppointmentSlot
from services.ai_assistant.assistant_service import ai_assistant_service
from services.ai_assistant.client_links import AiAssistantClientLinks
from services.ai_assistant.demo_space_examples import ai_assistant_demo_space_examples
from services.ai_assistant.demo_space_service import ai_assistant_demo_space_service
from services.ai_assistant.faq_service import ai_assistant_faq_service
from services.ai_assistant.opening_hours import OpeningHoursCalendar
from services.ai_assistant.request_volume import AiAssistantRequestVolume
from services.notification_service import notification_service
from services.rate_limiter import SlidingWindowRateLimiter
from tests.assistant_fakes import VISITOR_REQUEST

_VISITOR_SESSION = "0b6f1c2e-6c1d-4c55-9a7e-3f1f2d9c8a10"
_OTHER_VISITOR_SESSION = "9d2a4e61-1b7c-4f0e-8c3a-5e6f7a8b9c0d"
# Monday to Saturday, 8:00 to 18:00; closed on Sunday.
_WORKING_WEEK = [
    {"day": day, "hours": "08:00–18:00"} for day in ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi")
] + [{"day": "dimanche", "hours": "Fermé"}]


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
def fresh_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each test starts with empty rate-limit buckets."""
    monkeypatch.setattr(routes, "assistant_demo_space_limiter", SlidingWindowRateLimiter(60, 300))
    monkeypatch.setattr(routes, "assistant_client_limiter", SlidingWindowRateLimiter(120, 300))


def _demo(
    db: Session, *, business_name: str = "Toitures Durand", category: str = "Couvreur", **fields: Any
) -> AiAssistant:
    prospect = ProspectDB(
        name=business_name, category=category, source="google", confidence=2, user_id=7, website="toitures-durand.fr"
    )
    db.add(prospect)
    db.commit()
    assistant = ai_assistant_service.create(
        db, user_id=7, business_name=business_name, prospect_id=prospect.id, country="FR", use_brand_color=False
    )
    for field, value in fields.items():
        setattr(assistant, field, value)
    db.commit()
    return assistant


def _request(db: Session, assistant: AiAssistant, **fields: Any) -> AiAssistantRequest:
    values: dict[str, Any] = {
        "user_id": assistant.user_id,
        "prospect_id": assistant.prospect_id,
        "assistant_id": assistant.id,
        "session_id": _VISITOR_SESSION,
        "name": "Léo Testeur",
        "contact": "06 39 98 00 01",
        "type": "quote",
        "need": "Des tuiles ont bougé",
        "created_at": datetime(2026, 9, 30, 8, 5),
    }
    values.update(fields)
    record = AiAssistantRequest(**values)
    db.add(record)
    db.commit()
    return record


def _space(db: Session, slug: str, *session_ids: str) -> AiAssistantDemoSpaceResponse:
    payload = AiAssistantDemoSpaceRequest(session_ids=list(session_ids))
    return asyncio.run(routes.read_demo_space(slug, payload, VISITOR_REQUEST, db))


def _status_of(call: Any) -> int:
    with pytest.raises(HTTPException) as caught:
        asyncio.run(call)
    return caught.value.status_code


def test_only_a_live_demo_opens_a_demo_space(db: Session) -> None:
    """A sold, expired, deleted or counted-out demo has no space, and an unknown slug neither."""
    live = _demo(db, expires_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(days=3))
    sold = _demo(db, business_name="Couverture Petit", status="delivered")
    expired = _demo(db, business_name="Zinguerie Morel", status="expired")
    deleted = _demo(db, business_name="Toits Bernard", deleted_at=datetime(2026, 9, 1))
    counted_out = _demo(db, business_name="Ardoises Leroy", expires_at=datetime(2026, 9, 1))

    assert _space(db, live.slug).is_demo is True
    for assistant in (sold, expired, deleted, counted_out):
        payload = AiAssistantDemoSpaceRequest()
        assert _status_of(routes.read_demo_space(assistant.slug, payload, VISITOR_REQUEST, db)) == 404
    assert _status_of(routes.read_demo_space("inconnue", AiAssistantDemoSpaceRequest(), VISITOR_REQUEST, db)) == 404


def test_the_space_lists_the_requests_of_the_visitor_sessions_and_never_another_visitor_s(db: Session) -> None:
    demo = _demo(db)
    other_demo = _demo(db, business_name="Charpentes Lefèvre", category="Charpentier")
    own = _request(db, demo, name="Léo Testeur", contact="06 39 98 00 01")
    _request(db, demo, session_id=_OTHER_VISITOR_SESSION, name="Marie Voisine", contact="06 11 22 33 44")
    _request(db, demo, session_id=None, name="Sans Session", contact="sans.session@example.org")
    _request(db, other_demo, name="Même Session Ailleurs", contact="ailleurs@example.org")

    space = _space(db, demo.slug, _VISITOR_SESSION)

    visitor_items = [item for item in space.requests if not item.is_example]
    assert [item.id for item in visitor_items] == [own.id]
    dumped = json.dumps(space.model_dump(mode="json"), ensure_ascii=False)
    for foreign in ("Marie Voisine", "06 11 22 33 44", "Sans Session", "Même Session Ailleurs"):
        assert foreign not in dumped
    # Without a session the visitor left nothing: only the examples show.
    assert all(item.is_example for item in _space(db, demo.slug).requests)


def test_a_visitor_request_carries_its_conversation_photos_and_details(db: Session) -> None:
    demo = _demo(db)
    conversation = AiAssistantConversation(
        user_id=7, assistant_id=demo.id, session_id=_VISITOR_SESSION, message_count=2, is_test=False
    )
    db.add(conversation)
    db.flush()
    db.add_all(
        [
            AiAssistantMessage(conversation_id=conversation.id, role="user", content="Des tuiles ont bougé."),
            AiAssistantMessage(
                conversation_id=conversation.id,
                role="user",
                content="Photo envoyée",
                photo_url="https://cdn.example/photo-1.jpg",
            ),
            AiAssistantMessage(conversation_id=conversation.id, role="assistant", content="Je transmets en urgence."),
            AiAssistantMessage(conversation_id=conversation.id, role="system", content="(note interne)"),
        ]
    )
    db.commit()
    own = _request(
        db,
        demo,
        conversation_id=conversation.id,
        type="urgent",
        need_summary="Tuiles déplacées après la tempête.",
        photos_json=[{"url": "https://cdn.example/photo-1.jpg"}],
        received_outside_hours=True,
    )

    item = next(item for item in _space(db, demo.slug, _VISITOR_SESSION).requests if item.id == own.id)

    assert (item.type.value, item.status.value, item.is_example) == ("urgent", "new", False)
    assert (item.name, item.contact, item.summary) == (
        "Léo Testeur",
        "06 39 98 00 01",
        "Tuiles déplacées après la tempête.",
    )
    assert item.photo_urls == ["https://cdn.example/photo-1.jpg"]
    assert item.received_label == "30/09 à 10:05" and item.received_outside_hours is True
    assert [(line.role, line.content, line.photo_url) for line in item.conversation] == [
        ("user", "Des tuiles ont bougé.", None),
        ("user", "Photo envoyée", "https://cdn.example/photo-1.jpg"),
        ("assistant", "Je transmets en urgence.", None),
    ]


def test_examples_complete_fewer_than_two_visitor_requests_and_are_always_flagged(db: Session) -> None:
    demo = _demo(db)

    alone = _space(db, demo.slug, _VISITOR_SESSION)
    first = _request(db, demo, created_at=datetime(2026, 9, 30, 9, 0))
    with_one = _space(db, demo.slug, _VISITOR_SESSION)
    _request(db, demo, session_id=_OTHER_VISITOR_SESSION, name="Marie Voisine")
    with_one_and_another_visitor = _space(db, demo.slug, _VISITOR_SESSION)
    second = _request(db, demo, session_id=_OTHER_VISITOR_SESSION.replace("9d2a", "1111"))
    with_two = _space(db, demo.slug, _VISITOR_SESSION, _OTHER_VISITOR_SESSION.replace("9d2a", "1111"))

    assert [item.is_example for item in alone.requests] == [True, True, True]
    assert [item.is_example for item in with_one.requests] == [False, True, True]
    assert with_one.requests[0].id == first.id
    assert [item.is_example for item in with_one_and_another_visitor.requests] == [False, True, True]
    assert [item.is_example for item in with_two.requests] == [False, False]
    assert {item.id for item in with_two.requests} == {first.id, second.id}
    for item in alone.requests:
        # Negative ids, fictional names and contacts that reach no one, a conversation of their own.
        assert item.id < 0
        assert item.contact.startswith("06 39 98") or item.contact.endswith("@example.com")
        assert item.conversation and demo.business_name in " ".join(line.content for line in item.conversation)
    # The client space's order: the waiting ones first, the newest first.
    statuses = [item.status for item in alone.requests]
    assert statuses == sorted(statuses, key=lambda value: value is not AiAssistantRequestStatus.NEW)
    assert alone.pending_count == sum(1 for item in alone.requests if item.status is AiAssistantRequestStatus.NEW)


@pytest.mark.parametrize(
    ("category", "summary_word", "photo"),
    [
        ("Couvreur", "tuiles", "toiture.jpg"),
        ("Charpentier", "Lucarne", "toiture.jpg"),
        ("Atelier de carrosserie automobile", "Portière", "carrosserie.jpg"),
        ("Garage automobile", "Portière", "carrosserie.jpg"),
        ("Plombier chauffagiste", "évier", None),
        ("Restaurant", "Anniversaire", None),
        ("Food truck", "Anniversaire", None),
        ("Salon de coiffure", "renseignement", None),
        (None, "renseignement", None),
    ],
)
def test_the_examples_follow_the_trade(db: Session, category: str | None, summary_word: str, photo: str | None) -> None:
    demo = _demo(db, category=category or "")

    first = _space(db, demo.slug).requests[0]

    assert summary_word in (first.summary or "")
    assert first.photo_urls == (
        [f"{settings.demo_host_base_url.rstrip('/')}/showroom/examples/{photo}"] if photo else []
    )


def test_the_food_trades_are_read_from_the_category() -> None:
    assert AiAssistantRequestVolume.for_category("Food truck").trade is AiAssistantTrade.FOOD_TRUCK
    assert AiAssistantRequestVolume.for_category("Foodtruck burgers").label == "un food truck"
    assert AiAssistantRequestVolume.for_category("Pizzeria").trade is AiAssistantTrade.RESTAURANT
    assert AiAssistantRequestVolume.for_category("Institut de formation").trade is AiAssistantTrade.OTHER


def test_the_examples_fit_the_business_hours_and_its_next_half_days(db: Session) -> None:
    demo = _demo(db, knowledge_json={"opening_hours": _WORKING_WEEK})
    now = datetime(2026, 10, 1, 9, 30, tzinfo=OpeningHoursCalendar.business_timezone())

    examples = ai_assistant_demo_space_examples.requests(demo, "Couvreur", count=3, now=now)
    unknown_hours = ai_assistant_demo_space_examples.requests(
        _demo(db, business_name="Toits Sans Horaires"), None, count=3, now=now
    )

    by_time = {item.received_time: item for item in examples}
    assert by_time["21:43"].received_outside_hours is True
    assert by_time["12:10"].received_outside_hours is False
    assert all(item.received_outside_hours is None for item in unknown_hours)
    offered = AiAssistantAppointmentSlots.offer_for(demo, today=now.date())
    appointment = next(item for item in examples if item.type.value == "appointment")
    assert appointment.appointment_slots == [
        AiAssistantAppointmentSlots.label(AppointmentSlot(day=day.day, period=day.periods[0])) for day in offered[:2]
    ]
    assert appointment.received_day == "2026-09-30"


def test_the_space_keeps_the_client_space_contract_and_adds_what_a_demo_needs(db: Session) -> None:
    demo = _demo(db, assistant_name="Nathan", languages=["fr", "en"])

    space = _space(db, demo.slug, _VISITOR_SESSION)
    dumped = space.model_dump(mode="json")

    assert set(AiAssistantClientSpaceResponse.model_fields) <= set(dumped)
    assert all(set(AiAssistantClientRequestItem.model_fields) <= set(item) for item in dumped["requests"])
    assert (space.is_demo, space.is_example, space.fresh_token, space.subscription) == (True, False, None, None)
    assert space.assistant_gender is AiAssistantPersonaGender.MASCULINE
    assert space.subscribe_url.endswith(f"/api/v1/ai-assistants/public/{demo.slug}/subscribe?interval=month")
    assert space.monthly_price_label == "79 €"
    assert space.website_url == "https://toitures-durand.fr"
    assert space.embed_snippet is not None and f'data-slug="{demo.slug}"' in space.embed_snippet
    assert space.google_profile is not None and space.google_profile.page_url.endswith(f"/ia/{demo.slug}")
    # The example month of the trade, read like a real report, in the receptionist's languages.
    assert space.report is not None and space.report.is_example is True
    assert space.report.languages_line == "français 90 %, anglais 10 %"
    assert space.report.won_line == "Nathan vous a apporté 4 clients ce mois-ci."


def test_the_start_steps_are_not_done_and_nothing_private_of_the_demo_shows(db: Session) -> None:
    """What the operator set on the demo, and the visitors' unanswered questions, never reach the page."""
    demo = _demo(
        db,
        alert_phone_e164="+33612345678",
        installed_host="test.dibodev.fr",
        installed_at=datetime(2026, 9, 20, 10, 0),
        # 23:30 UTC on 30/10 is already 31/10 in Paris (UTC+1 once summer time is over).
        expires_at=datetime(2026, 10, 30, 23, 30),
    )
    ai_assistant_faq_service.record_unanswered(db, demo, "Je m'appelle Marie Voisine, vous passez au 3 rue des Lilas ?")
    ai_assistant_faq_service.add_faq(db, demo, "Faites-vous le démoussage ?", "Oui, avec un traitement hydrofuge.")

    space = _space(db, demo.slug)

    assert space.settings.alert_phone is None
    assert space.installed is None
    assert space.google_profile is not None and space.google_profile.is_linked is False
    assert space.calendar.status.value in {"disconnected", "unavailable"} and space.calendar.account_email is None
    assert space.mailbox is None and space.appointments == []
    assert space.unanswered == [] and "Marie Voisine" not in space.model_dump_json()
    assert [entry.question for entry in space.faq] == ["Faites-vous le démoussage ?"]
    # The demo's last day, in business time.
    assert space.link_expires_label == "31/10/2026"
    assert _space(db, _demo(db, business_name="Démo Pas Envoyée").slug).link_expires_label == ""


def test_reading_the_space_writes_counts_and_announces_nothing(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    demo = _demo(db)
    _request(db, demo)
    announced: list[str] = []

    def record_announce(name: str) -> Any:
        async def announce(*_args: Any, **_kwargs: Any) -> None:
            announced.append(name)

        return announce

    for name in ("notify_assistant_lead", "notify_assistant_interest", "notify_error"):
        monkeypatch.setattr(notification_service, name, record_announce(name))
    monkeypatch.setattr(delivery_module.activity_log_service, "record", lambda **kwargs: announced.append("activity"))
    flushes: list[int] = []
    event.listen(db, "before_flush", lambda *_args: flushes.append(1))

    _space(db, demo.slug, _VISITOR_SESSION)

    assert announced == [] and flushes == [] and not db.dirty and not db.new


def test_the_space_is_rate_limited_per_visitor(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    demo = _demo(db)
    monkeypatch.setattr(routes, "assistant_demo_space_limiter", SlidingWindowRateLimiter(2, 300))

    _space(db, demo.slug)
    _space(db, demo.slug)

    assert _status_of(routes.read_demo_space(demo.slug, AiAssistantDemoSpaceRequest(), VISITOR_REQUEST, db)) == 429


@pytest.mark.parametrize(
    "session_ids",
    [
        [f"{_VISITOR_SESSION[:-1]}{index}" for index in range(6)],
        ["court"],
        ["x" * 65],
        ["une session"],
        ["<script>"],
    ],
)
def test_malformed_or_too_many_session_ids_are_refused(session_ids: list[str]) -> None:
    with pytest.raises(ValidationError):
        AiAssistantDemoSpaceRequest(session_ids=session_ids)


def test_the_widget_session_ids_are_accepted() -> None:
    fallback = "mg7k2x3a-4fzq9k1b2c"

    assert AiAssistantDemoSpaceRequest(session_ids=[_VISITOR_SESSION, fallback]).session_ids == [
        _VISITOR_SESSION,
        fallback,
    ]


def test_the_public_config_tells_a_live_demo_has_a_demo_space(db: Session) -> None:
    live = _demo(db)
    sold = _demo(db, business_name="Couverture Petit", status="delivered")
    counted_out = _demo(db, business_name="Ardoises Leroy", expires_at=datetime(2026, 9, 1))

    assert asyncio.run(widget_routes.get_public_assistant(live.slug, db)).has_demo_space is True
    assert asyncio.run(widget_routes.get_public_assistant(sold.slug, db)).has_demo_space is False
    assert asyncio.run(widget_routes.get_public_assistant(counted_out.slug, db)).has_demo_space is False


def test_a_demo_never_opens_the_client_space_writes(db: Session) -> None:
    """The writes stay behind a client link, which only a sold receptionist's opens."""
    demo = _demo(db)
    own = _request(db, demo)
    demo_token = AiAssistantClientLinks.token(demo)

    assert (
        _status_of(routes.update_client_settings(demo_token, AiAssistantClientSettingsUpdate(), VISITOR_REQUEST, db))
        == 404
    )
    assert _status_of(routes.mark_client_request_handled(demo_token, own.id, VISITOR_REQUEST, db)) == 404
    db.refresh(own)
    assert own.status == "new"


def test_the_demo_space_route_is_the_one_its_address_reaches() -> None:
    """No owner route with a path parameter catches « /public/{slug}/space » first."""
    scope = {
        "type": "http",
        "method": "POST",
        "path": f"{settings.api_prefix}/ai-assistants/public/toitures-durand/space",
    }

    first_match = next(route for route in app.router.routes if route.matches(scope)[0] is Match.FULL)

    assert first_match.endpoint is routes.read_demo_space


def test_the_demo_last_day_reads_an_expiry_just_set_or_read_back() -> None:
    aware = AiAssistant(status="active", expires_at=datetime(2026, 10, 31, 9, 0, tzinfo=UTC))
    naive = AiAssistant(status="active", expires_at=datetime(2026, 10, 31, 9, 0))
    now = datetime(2026, 10, 31, 8, 59)

    assert ai_assistant_demo_space_service.is_open(aware, now=now) is True
    assert ai_assistant_demo_space_service.is_open(naive, now=now) is True
    assert ai_assistant_demo_space_service.is_open(naive, now=datetime.combine(now.date(), time(9, 0))) is False
