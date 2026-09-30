"""
Connecting a sold receptionist's Gmail: the operator's switch, the consent and its signed state, the client space's
section, the disconnection that revokes (unless the account still serves here), and the migrations.

Gmail is a fake client; the email sender is mocked; the database is an in-memory SQLite. Routes are called directly.
"""

import asyncio
import html
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import api.v1.routes.ai_assistant_client_space as client_routes
import api.v1.routes.ai_assistants as owner_routes
import migrations.add_ai_assistant_mailbox_enabled as enabled_migration
import migrations.add_ai_assistant_mailbox_tables as tables_migration
import services.ai_assistant.gmail_client as gmail_module
from enums.ai_assistant_mailbox import (
    AiAssistantMailboxConnection,
    AiAssistantMailboxMessageOutcome,
    AiAssistantMailboxStatus,
)
from enums.email_account_type import EmailAccountType
from models.ai_assistant_calendar import AiAssistantCalendar
from models.ai_assistant_mailbox import AiAssistantMailbox
from models.ai_assistant_mailbox_message import AiAssistantMailboxMessage
from models.email_account import EmailAccount
from schemas.ai_assistant import AiAssistantUpdateRequest
from services.ai_assistant.calendar_service import AiAssistantCalendarState
from services.ai_assistant.client_links import AiAssistantClientLinks
from services.ai_assistant.gmail_client import GmailError
from services.ai_assistant.mailbox_service import AiAssistantMailboxOAuthState, ai_assistant_mailbox_service
from services.encryption_service import encryption_service
from tests.assistant_fakes import VISITOR_REQUEST
from tests.assistant_mailbox.mailbox_fakes import MAILBOX_ADDRESS, FakeGmail, add_mailbox, add_mailbox_assistant

_OPERATOR = SimpleNamespace(id=7, email="operateur@dibodev.fr")


def test_the_oauth_state_names_its_receptionist_expires_and_never_opens_the_agenda() -> None:
    now = datetime(2026, 10, 1, 8, 0)
    state = AiAssistantMailboxOAuthState.sign(42, now=now)
    agenda_state = AiAssistantCalendarState.sign(42, now=now)

    assert AiAssistantMailboxOAuthState.read(state, now=now + timedelta(minutes=14)) == 42
    assert AiAssistantMailboxOAuthState.read(state, now=now + timedelta(minutes=16)) is None
    assert AiAssistantMailboxOAuthState.read(state.replace("42.", "43.", 1), now=now) is None
    assert AiAssistantMailboxOAuthState.read(agenda_state, now=now) is None
    assert AiAssistantCalendarState.read(state, now=now) is None


def test_the_client_connects_then_disconnects_its_gmail(db: Session, gmail: FakeGmail, outbox: dict[str, Any]) -> None:
    assistant = add_mailbox_assistant(db)
    token = AiAssistantClientLinks.token(assistant)
    before = asyncio.run(client_routes.get_client_space(token, VISITOR_REQUEST, db))

    consent = asyncio.run(client_routes.connect_client_mailbox(token, VISITOR_REQUEST, db))
    state = consent.url.split("state=")[1]
    page = asyncio.run(client_routes.google_mailbox_callback(VISITOR_REQUEST, code="ok", state=state, error="", db=db))
    mailbox = db.query(AiAssistantMailbox).one()
    connected = asyncio.run(client_routes.get_client_space(token, VISITOR_REQUEST, db))
    disconnected = asyncio.run(client_routes.disconnect_client_mailbox(token, VISITOR_REQUEST, db))

    assert before.mailbox is not None and before.mailbox.status is AiAssistantMailboxConnection.DISCONNECTED
    assert "gmail.readonly" in consent.url and "gmail.compose" in consent.url
    assert "Gmail est connecté" in page.body.decode() and page.headers["referrer-policy"] == "no-referrer"
    assert (mailbox.account_email, mailbox.history_id, mailbox.status) == (MAILBOX_ADDRESS, "1000", "connected")
    assert encryption_service.decrypt(mailbox.refresh_token_encrypted) == "refresh-1"
    assert connected.mailbox is not None and connected.mailbox.status is AiAssistantMailboxConnection.CONNECTED
    assert connected.mailbox.account_email == MAILBOX_ADDRESS
    assert connected.mailbox.drafts_url == f"https://mail.google.com/mail/?authuser={MAILBOX_ADDRESS}#drafts"
    [notice] = outbox["email"].calls
    assert notice["subject"] == "Votre boîte Gmail est connectée" and MAILBOX_ADDRESS in notice["body_html"]
    assert disconnected.status is AiAssistantMailboxConnection.DISCONNECTED
    assert db.query(AiAssistantMailbox).count() == 0
    assert gmail.revoked == ["refresh-1"]


def test_a_consent_without_both_accesses_a_lasting_one_or_a_gmail_stores_nothing(db: Session, gmail: FakeGmail) -> None:
    assistant = add_mailbox_assistant(db)

    def callback() -> str:
        state = AiAssistantMailboxOAuthState.sign(assistant.id)
        page = asyncio.run(
            client_routes.google_mailbox_callback(VISITOR_REQUEST, code="ok", state=state, error="", db=db)
        )
        return html.unescape(page.body.decode())

    gmail.scopes = frozenset({"openid", gmail_module.GMAIL_READONLY_SCOPE})
    unticked = callback()
    gmail.scopes = frozenset({gmail_module.GMAIL_READONLY_SCOPE, gmail_module.GMAIL_COMPOSE_SCOPE})
    gmail.gives_refresh_token = False
    fleeting = callback()
    gmail.gives_refresh_token = True
    gmail.profile_failure = GmailError("Gmail a refusé l'appel (400)", status_code=400)
    no_gmail = callback()
    refused = asyncio.run(
        client_routes.google_mailbox_callback(
            VISITOR_REQUEST, code="refused", state=AiAssistantMailboxOAuthState.sign(assistant.id), error="", db=db
        )
    )
    denied = asyncio.run(
        client_routes.google_mailbox_callback(VISITOR_REQUEST, code="", state="", error="access_denied", db=db)
    )
    forged = asyncio.run(
        client_routes.google_mailbox_callback(
            VISITOR_REQUEST, code="ok", state="9.9.AAAAAAAAAAAAAAAAAAAAAA", error="", db=db
        )
    )

    assert "Cochez les deux accès à Gmail" in unticked
    assert "Google n'a pas donné d'accès durable" in fleeting
    assert "Ce compte Google n'a pas de boîte Gmail" in no_gmail
    assert "Google n'a pas confirmé la connexion" in html.unescape(refused.body.decode())
    assert "Connexion annulée" in denied.body.decode()
    assert "Lien de connexion expiré" in forged.body.decode()
    assert db.query(AiAssistantMailbox).count() == 0


def test_a_receptionist_whose_mailbox_is_off_offers_nothing_and_accepts_no_consent(
    db: Session, gmail: FakeGmail
) -> None:
    switched_off = add_mailbox_assistant(db, is_mailbox_enabled=False)
    demo = add_mailbox_assistant(db, status="active")
    token = AiAssistantClientLinks.token(switched_off)

    space = asyncio.run(client_routes.get_client_space(token, VISITOR_REQUEST, db))
    with pytest.raises(HTTPException) as refused_connect:
        asyncio.run(client_routes.connect_client_mailbox(token, VISITOR_REQUEST, db))
    with pytest.raises(HTTPException) as refused_disconnect:
        asyncio.run(client_routes.disconnect_client_mailbox(token, VISITOR_REQUEST, db))
    pages = [
        asyncio.run(
            client_routes.google_mailbox_callback(
                VISITOR_REQUEST, code="ok", state=AiAssistantMailboxOAuthState.sign(assistant.id), error="", db=db
            )
        ).body.decode()
        for assistant in (switched_off, demo)
    ]
    pages = [html.unescape(page) for page in pages]

    assert space.mailbox is None
    assert refused_connect.value.status_code == refused_disconnect.value.status_code == 404
    assert all("ne peut pas lire de boîte mail" in page for page in pages)
    assert db.query(AiAssistantMailbox).count() == 0


def test_without_its_redirect_address_the_server_offers_no_mailbox(
    db: Session, gmail: FakeGmail, monkeypatch: pytest.MonkeyPatch
) -> None:
    assistant = add_mailbox_assistant(db)
    token = AiAssistantClientLinks.token(assistant)
    monkeypatch.setattr(gmail_module.settings, "google_mailbox_redirect_uri", "")

    space = asyncio.run(client_routes.get_client_space(token, VISITOR_REQUEST, db))
    with pytest.raises(HTTPException) as refused:
        asyncio.run(client_routes.connect_client_mailbox(token, VISITOR_REQUEST, db))
    listed = asyncio.run(owner_routes.get_assistant(assistant.id, _OPERATOR, db))

    assert space.mailbox is None
    assert refused.value.status_code == 503
    assert listed.mailbox_status is AiAssistantMailboxConnection.UNAVAILABLE


def test_the_dashboard_shows_where_each_mailbox_stands(db: Session, gmail: FakeGmail) -> None:
    off = add_mailbox_assistant(db, is_mailbox_enabled=False)
    waiting = add_mailbox_assistant(db)
    connected = add_mailbox_assistant(db)
    lost = add_mailbox_assistant(db)
    add_mailbox(db, connected)
    add_mailbox(db, lost, account_email="perdu@gmail.com", status=AiAssistantMailboxStatus.ERROR.value)

    listed = {item.id: item for item in asyncio.run(owner_routes.list_assistants(None, _OPERATOR, db)).assistants}

    assert (listed[off.id].mailbox_enabled, listed[off.id].mailbox_status) == (
        False,
        AiAssistantMailboxConnection.DISABLED,
    )
    assert listed[waiting.id].mailbox_status is AiAssistantMailboxConnection.DISCONNECTED
    assert (listed[connected.id].mailbox_status, listed[connected.id].mailbox_address) == (
        AiAssistantMailboxConnection.CONNECTED,
        MAILBOX_ADDRESS,
    )
    assert listed[lost.id].mailbox_status is AiAssistantMailboxConnection.ERROR


def test_the_operator_switches_the_mailbox_on_and_off_which_disconnects_it(
    db: Session, gmail: FakeGmail, monkeypatch: pytest.MonkeyPatch
) -> None:
    assistant = add_mailbox_assistant(db, is_mailbox_enabled=False)

    switched_on = asyncio.run(
        owner_routes.update_assistant(assistant.id, AiAssistantUpdateRequest(mailbox_enabled=True), _OPERATOR, db)
    )
    add_mailbox(db, assistant)
    switched_off = asyncio.run(
        owner_routes.update_assistant(assistant.id, AiAssistantUpdateRequest(mailbox_enabled=False), _OPERATOR, db)
    )
    monkeypatch.setattr(gmail_module.settings, "google_mailbox_redirect_uri", "")
    with pytest.raises(HTTPException) as refused:
        asyncio.run(
            owner_routes.update_assistant(assistant.id, AiAssistantUpdateRequest(mailbox_enabled=True), _OPERATOR, db)
        )

    assert (switched_on.mailbox_enabled, switched_on.mailbox_status) == (
        True,
        AiAssistantMailboxConnection.DISCONNECTED,
    )
    assert (switched_off.mailbox_enabled, switched_off.mailbox_status) == (
        False,
        AiAssistantMailboxConnection.DISABLED,
    )
    assert db.query(AiAssistantMailbox).count() == 0 and gmail.revoked == ["refresh-0"]
    assert refused.value.status_code == 422 and str(refused.value.detail).startswith("Boîte mail Gmail impossible")
    db.refresh(assistant)
    assert assistant.mailbox_enabled is False


@pytest.mark.parametrize("shared_by", ["agenda", "other_mailbox", "sender"])
def test_an_account_that_still_serves_here_is_disconnected_without_revoking_its_grant(
    db: Session, gmail: FakeGmail, shared_by: str
) -> None:
    assistant = add_mailbox_assistant(db)
    add_mailbox(db, assistant)
    if shared_by == "agenda":
        db.add(AiAssistantCalendar(user_id=7, assistant_id=assistant.id, account_email="Garage.Morel@gmail.com"))
    elif shared_by == "other_mailbox":
        add_mailbox(db, add_mailbox_assistant(db))
    else:
        db.add(
            EmailAccount(
                user_id=7, account_type=EmailAccountType.GMAIL_OAUTH.value, email=MAILBOX_ADDRESS, name="Dibodev"
            )
        )
    db.commit()

    asyncio.run(ai_assistant_mailbox_service.disconnect(db, assistant))

    assert db.query(AiAssistantMailbox).filter(AiAssistantMailbox.assistant_id == assistant.id).count() == 0
    assert gmail.revoked == []


def test_old_emails_read_are_forgotten_after_90_days(db: Session) -> None:
    now = datetime(2026, 10, 1, 8, 0)
    for message_id, age in (("old", 91), ("recent", 89)):
        db.add(
            AiAssistantMailboxMessage(
                user_id=7,
                assistant_id=1,
                gmail_message_id=message_id,
                gmail_thread_id="t",
                outcome=AiAssistantMailboxMessageOutcome.SKIPPED.value,
                created_at=now - timedelta(days=age),
            )
        )
    db.commit()

    assert ai_assistant_mailbox_service.purge_old_messages(db, now=now) == 1
    assert [row.gmail_message_id for row in db.query(AiAssistantMailboxMessage).all()] == ["recent"]


def test_the_migrations_add_the_switch_and_the_tables_once(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE ai_assistants (id INTEGER PRIMARY KEY, slug VARCHAR(120))"))
        conn.execute(text("INSERT INTO ai_assistants (id, slug) VALUES (1, 'garage-morel')"))
        conn.commit()
    monkeypatch.setattr(enabled_migration, "engine", engine)
    monkeypatch.setattr(tables_migration, "engine", engine)

    for _run in range(2):
        enabled_migration.run_migration()
        tables_migration.run_migration()

    columns = {column["name"] for column in inspect(engine).get_columns("ai_assistants")}
    with engine.connect() as conn:
        switch = conn.execute(text("SELECT mailbox_enabled FROM ai_assistants WHERE id = 1")).scalar()
    assert "mailbox_enabled" in columns and switch == 0
    assert {"ai_assistant_mailboxes", "ai_assistant_mailbox_messages"} <= set(inspect(engine).get_table_names())
