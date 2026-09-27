"""
« Couper les anciens liens »: a sold assistant's client-space links carry a version, and a cut stops every link
signed before it, alert SMS included. Links sent before the version existed keep opening until the first cut.
"""

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import api.v1.routes.ai_assistant_client_space as routes
import api.v1.routes.ai_assistants as owner_routes
import migrations.add_ai_assistant_client_link_version as version_migration
import services.ai_assistant.client_space_service as client_space_module
from models.ai_assistant import AiAssistant
from models.prospect_db import ProspectDB
from models.user import User
from services.ai_assistant.assistant_service import ai_assistant_service
from services.ai_assistant.client_links import AiAssistantClientLinks
from services.ai_assistant.client_space_service import ai_assistant_client_space_service
from services.rate_limiter import SlidingWindowRateLimiter
from tests.assistant_fakes import VISITOR_REQUEST

_OPERATOR = SimpleNamespace(id=7, email="operateur@dibodev.fr")


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    session = sessionmaker(bind=engine)()
    session.add(User(id=7, name="Dibodev", email="operateur@dibodev.fr", hashed_password="x"))
    session.add(User(id=8, name="Autre", email="autre@exemple.fr", hashed_password="x"))
    session.commit()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def fresh_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each test starts with empty rate-limit buckets."""
    monkeypatch.setattr(routes, "assistant_client_limiter", SlidingWindowRateLimiter(120, 300))
    monkeypatch.setattr(routes, "assistant_client_renew_limiter", SlidingWindowRateLimiter(3, 3600))
    monkeypatch.setattr(routes, "assistant_client_renew_daily_limiter", SlidingWindowRateLimiter(6, 86400))


@pytest.fixture
def activity(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """The activity log entries written by the tested code."""
    logged: list[dict[str, Any]] = []
    monkeypatch.setattr(client_space_module.activity_log_service, "record", lambda **kwargs: logged.append(kwargs))
    return logged


def _assistant(db: Session, *, status: str = "delivered", business_name: str = "Toitures Morel") -> AiAssistant:
    prospect = ProspectDB(name=business_name, category="Couvreur", source="google", confidence=2, user_id=7)
    db.add(prospect)
    db.commit()
    assistant = ai_assistant_service.create(
        db, user_id=7, business_name=business_name, prospect_id=prospect.id, country="FR", use_brand_color=False
    )
    assistant.status = status
    assistant.email = "patron@toitures-morel.fr"
    db.commit()
    return assistant


def _opens(db: Session, token: str) -> bool:
    """Whether the client-space page opens with this token."""
    try:
        asyncio.run(routes.get_client_space(token, VISITOR_REQUEST, db))
    except HTTPException as exc:
        assert exc.status_code == 404 and exc.detail == "Ce lien n'ouvre aucun espace."
        return False
    return True


def _token_of(url: str) -> str:
    """The token carried by a client-space URL (with or without scheme, with or without a request anchor)."""
    return url.split("/client/")[1].split("#")[0]


def test_a_link_signed_before_the_versions_keeps_opening_until_the_first_cut(
    db: Session, activity: list[dict[str, Any]]
) -> None:
    assistant = _assistant(db)
    first_link = AiAssistantClientLinks.token(assistant)

    assert assistant.client_link_version == 0
    assert _opens(db, first_link)

    ai_assistant_client_space_service.revoke_links(db, assistant, operator_email="operateur@dibodev.fr")
    new_link = AiAssistantClientLinks.token(assistant)

    assert assistant.client_link_version == 1
    assert _opens(db, first_link) is False
    assert _opens(db, new_link)
    assert new_link.split(".")[0] == first_link.split(".")[0] and len(new_link) == len(first_link)
    assert [entry["action"] for entry in activity] == ["assistant_client_links_revoked"]


def test_a_second_cut_stops_the_links_of_the_first_one(db: Session, activity: list[dict[str, Any]]) -> None:
    assistant = _assistant(db)
    ai_assistant_client_space_service.revoke_links(db, assistant, operator_email="operateur@dibodev.fr")
    link_of_the_first_cut = AiAssistantClientLinks.token(assistant)
    ai_assistant_client_space_service.revoke_links(db, assistant, operator_email="operateur@dibodev.fr")

    assert assistant.client_link_version == 2
    assert _opens(db, link_of_the_first_cut) is False
    assert _opens(db, AiAssistantClientLinks.token(assistant))


def test_every_link_built_after_a_cut_opens_the_space(db: Session, activity: list[dict[str, Any]]) -> None:
    assistant = _assistant(db)
    ai_assistant_client_space_service.revoke_links(db, assistant, operator_email="operateur@dibodev.fr")

    alert_sms_link = AiAssistantClientLinks.sms_link(assistant, request_id=3)
    email_link = AiAssistantClientLinks.url(assistant, request_id=3)
    issued = asyncio.run(ai_assistant_client_space_service.issue_link(db, assistant, send=False))
    page = asyncio.run(routes.get_client_space(_token_of(issued.url), VISITOR_REQUEST, db))

    assert _opens(db, _token_of(alert_sms_link))
    assert _opens(db, _token_of(email_link))
    assert page.fresh_token is not None and _opens(db, page.fresh_token)


def test_an_expired_link_of_an_older_version_cannot_ask_for_a_new_one(
    db: Session, activity: list[dict[str, Any]]
) -> None:
    assistant = _assistant(db)
    expired = AiAssistantClientLinks.token(assistant, now=datetime.now(UTC) - timedelta(days=40))
    ai_assistant_client_space_service.revoke_links(db, assistant, operator_email="operateur@dibodev.fr")

    with pytest.raises(HTTPException) as caught:
        asyncio.run(routes.renew_client_link(expired, VISITOR_REQUEST, db))

    assert caught.value.status_code == 404


def test_the_operator_cuts_the_links_of_a_sold_assistant_of_theirs_only(
    db: Session, activity: list[dict[str, Any]]
) -> None:
    sold = _assistant(db)
    demo = _assistant(db, status="active", business_name="Démo Dupont")

    response = asyncio.run(owner_routes.revoke_assistant_client_links(sold.id, _OPERATOR, db))
    refused = []
    for assistant_id, user in ((demo.id, _OPERATOR), (sold.id, SimpleNamespace(id=8, email="autre@exemple.fr"))):
        with pytest.raises(HTTPException) as caught:
            asyncio.run(owner_routes.revoke_assistant_client_links(assistant_id, user, db))
        refused.append(caught.value.status_code)

    db.refresh(sold)
    db.refresh(demo)
    assert response.id == sold.id and sold.client_link_version == 1
    assert demo.client_link_version == 0
    assert refused == [400, 404]
    assert activity[0]["detail"] == "Par operateur@dibodev.fr"


def test_the_migration_adds_the_version_once_and_the_links_already_sent_stay_at_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE ai_assistants (id INTEGER PRIMARY KEY, slug VARCHAR(120))"))
        conn.execute(text("INSERT INTO ai_assistants (id, slug) VALUES (1, 'toitures-morel')"))
        conn.commit()
    monkeypatch.setattr(version_migration, "engine", engine)

    version_migration.run_migration()
    version_migration.run_migration()

    columns = {column["name"] for column in inspect(engine).get_columns("ai_assistants")}
    with engine.connect() as conn:
        version = conn.execute(text("SELECT client_link_version FROM ai_assistants WHERE id = 1")).scalar_one()
    assert "client_link_version" in columns
    assert version == 0
