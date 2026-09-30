"""
The receptionist reading a connected Gmail: new emails sorted out or read by the model, a reply left as a draft in
each customer's thread, a request filed and announced, each email read once, the day's caps, a lost access, and a
reply sent from Gmail closing its request.

Gmail and the model are fakes; the email sender and the operator's push are mocked; the database is an in-memory
SQLite.
"""

import asyncio
import base64
from email import message_from_bytes, policy
from typing import Any

import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

import services.ai_assistant.gmail_client as gmail_module
import services.ai_assistant.mailbox_sync as sync_module
import services.ai_assistant.message_delivery as delivery_module
from enums.ai_assistant_mailbox import AiAssistantMailboxMessageOutcome, AiAssistantMailboxStatus
from enums.ai_assistant_request import AiAssistantRequestChannel, AiAssistantRequestStatus
from models.ai_assistant_mailbox import AiAssistantMailbox
from models.ai_assistant_mailbox_message import AiAssistantMailboxMessage
from models.ai_assistant_request import AiAssistantRequest
from services.ai_assistant.gmail_client import GmailError
from services.ai_assistant.mailbox_sync import ai_assistant_mailbox_sync
from services.ai_assistant.report_stats import AiAssistantReportStats
from services.ai_assistant.request_follow_up import AiAssistantRequestFollowUp
from tests.assistant_mailbox.mailbox_fakes import (
    MAILBOX_ADDRESS,
    FakeGmail,
    FakeModel,
    add_mailbox,
    add_mailbox_assistant,
    customer_email,
)


def _sync(db: Session, mailbox: AiAssistantMailbox) -> None:
    """One pass over the mailbox."""
    asyncio.run(ai_assistant_mailbox_sync.sync_mailbox(db, mailbox.id))
    db.expire_all()


def _outcomes(db: Session) -> dict[str, str]:
    """What became of each email read, by message id."""
    return {row.gmail_message_id: row.outcome for row in db.query(AiAssistantMailboxMessage).all()}


def _draft_of(gmail: FakeGmail, index: int = 0):
    """A draft left in Gmail, as a mail client reads it."""
    return message_from_bytes(base64.urlsafe_b64decode(gmail.drafts[index]["raw"]), policy=policy.default)


def test_a_customers_email_gets_a_draft_in_its_thread_and_a_request(
    db: Session, gmail: FakeGmail, model: FakeModel, outbox: dict[str, Any]
) -> None:
    assistant = add_mailbox_assistant(db)
    mailbox = add_mailbox(db, assistant)
    gmail.receive(customer_email())

    _sync(db, mailbox)

    [draft] = gmail.drafts
    parsed = _draft_of(gmail)
    assert draft["thread_id"] == "t1"
    assert (parsed["From"], parsed["To"]) == (MAILBOX_ADDRESS, "Hélène Dupré <helene.dupre@exemple.fr>")
    assert (parsed["Subject"], parsed["In-Reply-To"]) == ("Re: Fuite sur ma toiture", "<m1@mail.exemple.fr>")
    body = parsed.get_content()
    assert body.startswith("Bonjour Madame Dupré,") and "> J'ai une fuite sur le toit" in body
    [request] = db.query(AiAssistantRequest).all()
    assert request.channel == AiAssistantRequestChannel.EMAIL.value
    assert (request.type, request.language, request.name) == ("quote", "fr", "Hélène Dupré")
    assert request.contact == "helene.dupre@exemple.fr"
    assert request.need_summary == FakeModel.CUSTOMER_REQUEST["summary"]
    assert request.need is not None and "Merci pour votre visite" not in request.need
    assert request.session_id == "gmail:t1"
    assert _outcomes(db) == {"m1": AiAssistantMailboxMessageOutcome.DRAFTED.value}
    assert db.query(AiAssistantMailboxMessage).one().request_id == request.id
    assert mailbox.history_id == str(gmail.history_id) and mailbox.last_synced_at is not None
    [push] = outbox["push"].calls
    assert push["request_label"] == "Demande de devis par email"
    [alert] = outbox["email"].calls
    assert alert["recipient_email"] == "contact@garage-morel.fr"
    assert alert["subject"].startswith("Demande de devis par email — Hélène Dupré")
    assert f"https://mail.google.com/mail/?authuser={MAILBOX_ADDRESS}#drafts" in alert["body_html"]
    triage_prompt = model.triage_calls[0][1]["content"]
    assert "Objet : Fuite sur ma toiture" in triage_prompt and "Merci pour votre visite" not in triage_prompt


def test_each_email_is_read_once_even_when_the_history_is_listed_again(
    db: Session, gmail: FakeGmail, model: FakeModel, outbox: dict[str, Any]
) -> None:
    mailbox = add_mailbox(db, add_mailbox_assistant(db))
    gmail.receive(customer_email())
    _sync(db, mailbox)

    _sync(db, mailbox)
    gmail.is_history_expired = True
    _sync(db, mailbox)

    assert len(gmail.drafts) == 1 and len(model.triage_calls) == 1
    assert db.query(AiAssistantRequest).count() == 1 and len(outbox["push"].calls) == 1
    assert mailbox.history_id == str(gmail.history_id)


def test_what_cannot_be_a_request_never_reaches_the_model(
    db: Session, gmail: FakeGmail, model: FakeModel, outbox: dict[str, Any]
) -> None:
    mailbox = add_mailbox(db, add_mailbox_assistant(db))
    gmail.receive(
        customer_email("promo", labels=("INBOX", "CATEGORY_PROMOTIONS")),
        customer_email("letter", headers={"list-unsubscribe": "<https://exemple.fr/stop>"}),
        customer_email("robot", sender="no-reply@exemple.fr"),
        customer_email("mine", sender=MAILBOX_ADDRESS),
        customer_email("invite", has_calendar_invite=True),
    )

    _sync(db, mailbox)

    assert model.triage_calls == [] and gmail.drafts == []
    assert set(_outcomes(db).values()) == {AiAssistantMailboxMessageOutcome.SKIPPED.value}
    assert gmail.body_reads == ["invite"]
    assert db.query(AiAssistantRequest).count() == 0
    assert mailbox.history_id == str(gmail.history_id)


def test_an_email_that_is_not_a_customers_request_gets_no_draft(
    db: Session, gmail: FakeGmail, model: FakeModel, outbox: dict[str, Any]
) -> None:
    mailbox = add_mailbox(db, add_mailbox_assistant(db))
    model.verdicts = [FakeModel.NOT_A_REQUEST]
    gmail.receive(customer_email(subject="Proposition de référencement"))

    _sync(db, mailbox)

    assert gmail.drafts == [] and model.reply_calls == []
    assert _outcomes(db) == {"m1": AiAssistantMailboxMessageOutcome.IGNORED.value}
    assert db.query(AiAssistantRequest).count() == 0 and outbox["push"].calls == []


def test_an_email_the_model_fails_on_is_read_again_then_given_up(
    db: Session, gmail: FakeGmail, model: FakeModel, outbox: dict[str, Any]
) -> None:
    mailbox = add_mailbox(db, add_mailbox_assistant(db))
    gmail.receive(customer_email("m1"), customer_email("m2", thread_id="t2"))
    model.verdicts = [None, None]

    _sync(db, mailbox)
    first_history_id = mailbox.history_id
    _sync(db, mailbox)
    after_two_failures = db.query(AiAssistantMailboxMessage).filter_by(gmail_message_id="m1").one().attempts
    model.verdicts = [None]
    _sync(db, mailbox)

    assert first_history_id == "1000"
    assert after_two_failures == 2
    assert _outcomes(db) == {
        "m1": AiAssistantMailboxMessageOutcome.FAILED.value,
        "m2": AiAssistantMailboxMessageOutcome.DRAFTED.value,
    }
    assert [draft["thread_id"] for draft in gmail.drafts] == ["t2"]
    assert mailbox.history_id == str(gmail.history_id)


def test_a_draft_gmail_refuses_is_retried_like_a_model_failure(
    db: Session, gmail: FakeGmail, model: FakeModel, outbox: dict[str, Any]
) -> None:
    mailbox = add_mailbox(db, add_mailbox_assistant(db))
    gmail.receive(customer_email())
    gmail.draft_failure = GmailError("Gmail a refusé l'appel (400)", status_code=400)

    _sync(db, mailbox)
    gmail.draft_failure = None
    _sync(db, mailbox)

    assert len(gmail.drafts) == 1 and len(model.triage_calls) == 2
    assert _outcomes(db) == {"m1": AiAssistantMailboxMessageOutcome.DRAFTED.value}
    assert db.query(AiAssistantRequest).count() == 1


@pytest.mark.parametrize(("read_cap", "draft_cap"), [(2, 30), (60, 2)])
def test_the_days_caps_stop_the_reading_and_tell_the_operator_once(
    db: Session,
    gmail: FakeGmail,
    model: FakeModel,
    outbox: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    read_cap: int,
    draft_cap: int,
) -> None:
    monkeypatch.setattr(sync_module, "DAILY_READ_CAP", read_cap)
    monkeypatch.setattr(sync_module, "DAILY_DRAFT_CAP", draft_cap)
    warnings: list[dict[str, Any]] = []
    monkeypatch.setattr(delivery_module.activity_log_service, "record", lambda **fields: warnings.append(fields))
    mailbox = add_mailbox(db, add_mailbox_assistant(db))
    gmail.receive(*(customer_email(f"m{index}", thread_id=f"t{index}") for index in range(3)))

    _sync(db, mailbox)
    gmail.receive(customer_email("late", thread_id="t9"))
    _sync(db, mailbox)

    assert len(gmail.drafts) == 2
    assert set(_outcomes(db)) == {"m0", "m1"}
    assert mailbox.capped_on is not None and mailbox.history_id == str(gmail.history_id)
    assert [warning["action"] for warning in warnings] == ["assistant_mailbox_capped"]


def test_a_lost_access_puts_the_mailbox_in_error_and_out_of_the_passes(
    db: Session, gmail: FakeGmail, model: FakeModel, outbox: dict[str, Any]
) -> None:
    assistant = add_mailbox_assistant(db)
    mailbox = add_mailbox(db, assistant, token_expires_at=None)
    gmail.receive(customer_email())
    gmail.refresh_failure = GmailError("Google a refusé l'accès (invalid_grant)", needs_reconnect=True)

    _sync(db, mailbox)

    assert mailbox.status == AiAssistantMailboxStatus.ERROR.value
    assert mailbox.last_error is not None and "reconnectez-la" in mailbox.last_error
    assert mailbox.history_id == "1000" and gmail.drafts == []
    assert ai_assistant_mailbox_sync.readable_mailbox_ids(db) == []


def test_a_token_google_dropped_early_is_refreshed_and_the_call_replayed(
    db: Session, gmail: FakeGmail, model: FakeModel, outbox: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    mailbox = add_mailbox(db, add_mailbox_assistant(db))
    gmail.receive(customer_email())
    original = gmail.changes_since
    calls: list[str] = []

    async def dropped_once(access_token: str, history_id: str):
        calls.append(access_token)
        if len(calls) == 1:
            raise GmailError("Gmail a refusé l'appel (401)", needs_reconnect=True, status_code=401)
        return await original(access_token, history_id)

    monkeypatch.setattr(sync_module.gmail_client, "changes_since", dropped_once)

    _sync(db, mailbox)

    assert calls == ["access-0", "fresh-access"]
    assert gmail.refreshed == ["refresh-0"] and len(gmail.drafts) == 1
    assert mailbox.status == AiAssistantMailboxStatus.CONNECTED.value


def test_a_transient_gmail_failure_leaves_the_emails_for_the_next_pass(
    db: Session, gmail: FakeGmail, model: FakeModel, outbox: dict[str, Any]
) -> None:
    mailbox = add_mailbox(db, add_mailbox_assistant(db))
    gmail.receive(customer_email())
    gmail.failure = GmailError("Gmail a refusé l'appel (503)", status_code=503)

    _sync(db, mailbox)
    gmail.failure = None
    _sync(db, mailbox)

    assert mailbox.status == AiAssistantMailboxStatus.CONNECTED.value
    assert len(gmail.drafts) == 1


def test_a_reply_sent_from_gmail_closes_its_request_and_a_thread_being_answered_is_left_alone(
    db: Session, gmail: FakeGmail, model: FakeModel, outbox: dict[str, Any]
) -> None:
    mailbox = add_mailbox(db, add_mailbox_assistant(db))
    gmail.receive(customer_email("m1", thread_id="t1"))
    _sync(db, mailbox)

    gmail.answer("t1")
    gmail.receive(customer_email("m2", thread_id="t2"))
    gmail.answer("t2")
    _sync(db, mailbox)

    [request] = db.query(AiAssistantRequest).all()
    assert request.status == AiAssistantRequestStatus.HANDLED.value and request.handled_at is not None
    assert [draft["thread_id"] for draft in gmail.drafts] == ["t1"]
    assert "m2" not in _outcomes(db)


def test_a_second_email_of_the_thread_updates_its_request_without_a_second_alert(
    db: Session, gmail: FakeGmail, model: FakeModel, outbox: dict[str, Any]
) -> None:
    mailbox = add_mailbox(db, add_mailbox_assistant(db))
    gmail.receive(customer_email("m1", thread_id="t1"))
    _sync(db, mailbox)
    model.verdicts = [{**FakeModel.CUSTOMER_REQUEST, "type": "urgent", "summary": "La fuite s'aggrave."}]
    gmail.receive(customer_email("m2", thread_id="t1", text="La fuite s'aggrave, ça coule dans le salon."))

    _sync(db, mailbox)

    [request] = db.query(AiAssistantRequest).all()
    assert (request.type, request.need_summary) == ("urgent", "La fuite s'aggrave.")
    assert request.need == "La fuite s'aggrave, ça coule dans le salon."
    assert len(gmail.drafts) == 2 and len(outbox["push"].calls) == 1


def test_a_pass_reads_only_the_connected_mailboxes_of_sold_receptionists_switched_on(
    engine: Engine,
    db: Session,
    gmail: FakeGmail,
    model: FakeModel,
    outbox: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    read = add_mailbox(db, add_mailbox_assistant(db))
    add_mailbox(db, add_mailbox_assistant(db, status="active"))
    add_mailbox(db, add_mailbox_assistant(db, is_mailbox_enabled=False))
    add_mailbox(db, add_mailbox_assistant(db), status=AiAssistantMailboxStatus.ERROR.value)
    monkeypatch.setattr(sync_module, "SessionLocal", sessionmaker(bind=engine))
    gmail.receive(customer_email())

    assert ai_assistant_mailbox_sync.readable_mailbox_ids(db) == [read.id]
    assert asyncio.run(ai_assistant_mailbox_sync.run_pass()) == 1
    assert len(gmail.drafts) == 1


def test_without_its_redirect_address_a_pass_does_nothing(
    db: Session, gmail: FakeGmail, model: FakeModel, monkeypatch: pytest.MonkeyPatch
) -> None:
    add_mailbox(db, add_mailbox_assistant(db))
    gmail.receive(customer_email())
    monkeypatch.setattr(gmail_module.settings, "google_mailbox_redirect_uri", "")

    assert asyncio.run(ai_assistant_mailbox_sync.run_pass()) == 0
    assert gmail.drafts == [] and model.triage_calls == []


def test_a_lost_email_announcement_is_picked_up_without_a_second_reading(
    engine: Engine, db: Session, gmail: FakeGmail, model: FakeModel, outbox: dict[str, Any]
) -> None:
    assistant = add_mailbox_assistant(db)
    request = AiAssistantRequest(
        user_id=7,
        assistant_id=assistant.id,
        name="Hélène Dupré",
        contact="helene.dupre@exemple.fr",
        need="Une fuite",
        need_summary="Fuite sur le toit.",
        type="quote",
        channel=AiAssistantRequestChannel.EMAIL.value,
    )
    db.add(request)
    db.commit()

    asyncio.run(AiAssistantRequestFollowUp().follow_up(db, request, assistant))

    assert model.triage_calls == []
    assert request.need_summary == "Fuite sur le toit." and request.owner_notified_at is not None
    [push] = outbox["push"].calls
    assert push["request_label"] == "Demande de devis par email"


def test_the_monthly_figures_count_the_requests_that_came_by_email(db: Session, model: FakeModel) -> None:
    assistant = add_mailbox_assistant(db)
    for channel in ("email", "email", "site"):
        db.add(AiAssistantRequest(user_id=7, assistant_id=assistant.id, name="X", contact="x@y.fr", channel=channel))
    db.commit()
    start = min(row.created_at for row in db.query(AiAssistantRequest).all())

    stats = asyncio.run(
        AiAssistantReportStats.compute(
            db, assistant, start=start.replace(microsecond=0), end=start.replace(year=start.year + 1)
        )
    )

    assert (stats.requests, stats.email_requests) == (3, 2)
