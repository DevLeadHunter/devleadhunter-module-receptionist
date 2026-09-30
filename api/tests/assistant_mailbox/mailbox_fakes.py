"""
What the mailbox tests share: a Gmail that never leaves the process, a model that answers on cue, a garage's
receptionist with its connected mailbox, and customer emails.

Times are naive UTC, as stored; the mailbox is connected before every email of the tests.
"""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar

from sqlalchemy.orm import Session

from models.ai_assistant import AiAssistant
from models.ai_assistant_mailbox import AiAssistantMailbox
from services.ai_assistant.gmail_client import (
    GMAIL_COMPOSE_SCOPE,
    GMAIL_READONLY_SCOPE,
    GmailChanges,
    GmailError,
    GmailMessage,
    GmailMessageRef,
    GmailProfile,
)
from services.encryption_service import encryption_service
from services.google_oauth_client import GoogleTokens
from tests.assistant_calendar.calendar_fakes import add_assistant

MAILBOX_ADDRESS = "garage.morel@gmail.com"
CONNECTED_AT = datetime(2026, 9, 30, 8, 0)
GRANTED_SCOPES = frozenset(
    {"openid", "https://www.googleapis.com/auth/userinfo.email", GMAIL_READONLY_SCOPE, GMAIL_COMPOSE_SCOPE}
)
CUSTOMER_TEXT = (
    "Bonjour,\n\nJ'ai une fuite sur le toit, à côté de la cheminée. Pouvez-vous passer faire un devis ?\n\n"
    "Hélène Dupré\n\nLe mar. 29 sept. 2026, Garage Morel a écrit :\n> Merci pour votre visite"
)


def customer_email(
    message_id: str = "m1",
    *,
    thread_id: str = "t1",
    sender: str = "Hélène Dupré <helene.dupre@exemple.fr>",
    subject: str = "Fuite sur ma toiture",
    text: str = CUSTOMER_TEXT,
    labels: tuple[str, ...] = ("INBOX", "UNREAD", "CATEGORY_PERSONAL"),
    headers: dict[str, str] | None = None,
    received_at: datetime | None = None,
    has_calendar_invite: bool = False,
) -> GmailMessage:
    """A customer's email as Gmail hands it, read in full (``headers`` add to or replace the defaults)."""
    all_headers = {
        "from": sender,
        "to": MAILBOX_ADDRESS,
        "subject": subject,
        "message-id": f"<{message_id}@mail.exemple.fr>",
    }
    all_headers.update(headers or {})
    return GmailMessage(
        message_id=message_id,
        thread_id=thread_id,
        label_ids=frozenset(labels),
        headers=all_headers,
        received_at=received_at or CONNECTED_AT + timedelta(hours=2),
        text=text,
        has_calendar_invite=has_calendar_invite,
    )


class FakeGmail:
    """What Gmail and Google answer for one mailbox: its emails, its history, the drafts left, the tokens."""

    def __init__(self) -> None:
        self.address = MAILBOX_ADDRESS
        self.history_id = 1000
        self.messages: dict[str, GmailMessage] = {}
        # Each email received and each thread answered, with the history step it happened at.
        self.received: list[tuple[int, GmailMessageRef]] = []
        self.answered: list[tuple[int, str]] = []
        self.drafts: list[dict[str, str]] = []
        self.revoked: list[str] = []
        self.refreshed: list[str] = []
        self.body_reads: list[str] = []
        self.is_history_expired = False
        self.failure: GmailError | None = None
        self.draft_failure: GmailError | None = None
        self.refresh_failure: GmailError | None = None
        self.profile_failure: GmailError | None = None
        self.scopes: frozenset[str] = GRANTED_SCOPES
        self.gives_refresh_token = True

    def receive(self, *messages: GmailMessage) -> None:
        """Emails arrive in the inbox, each a new step of the history."""
        for message in messages:
            self.history_id += 1
            self.messages[message.message_id] = message
            self.received.append(
                (self.history_id, GmailMessageRef(message.message_id, message.thread_id, message.label_ids))
            )

    def answer(self, thread_id: str) -> None:
        """The business sends a reply in a thread from Gmail."""
        self.history_id += 1
        self.answered.append((self.history_id, thread_id))

    async def get_profile(self, access_token: str) -> GmailProfile:
        if self.profile_failure is not None:
            raise self.profile_failure
        return GmailProfile(email_address=self.address, history_id=str(self.history_id))

    async def changes_since(self, access_token: str, history_id: str) -> GmailChanges | None:
        if self.failure is not None:
            raise self.failure
        if self.is_history_expired:
            return None
        start = int(history_id)
        return GmailChanges(
            received=[ref for step, ref in self.received if step > start],
            answered_thread_ids=frozenset(thread_id for step, thread_id in self.answered if step > start),
            history_id=str(self.history_id),
        )

    async def recent_inbox(self, access_token: str) -> list[GmailMessageRef]:
        return [GmailMessageRef(ref.message_id, ref.thread_id) for _step, ref in self.received]

    async def get_message(self, access_token: str, message_id: str, *, with_body: bool) -> GmailMessage | None:
        if self.failure is not None:
            raise self.failure
        message = self.messages.get(message_id)
        if message is None:
            return None
        if with_body:
            self.body_reads.append(message_id)
            return message
        return replace(message, text="", has_calendar_invite=False)

    async def create_draft(self, access_token: str, *, thread_id: str, raw: str) -> str:
        if self.draft_failure is not None:
            raise self.draft_failure
        self.drafts.append({"thread_id": thread_id, "raw": raw})
        return f"r-{len(self.drafts)}"

    async def refresh(self, refresh_token: str) -> GoogleTokens:
        if self.refresh_failure is not None:
            raise self.refresh_failure
        self.refreshed.append(refresh_token)
        return GoogleTokens(
            access_token="fresh-access",
            refresh_token=refresh_token,
            expires_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=1),
            scopes=self.scopes,
        )

    async def exchange_code(self, code: str) -> GoogleTokens:
        if code == "refused":
            raise GmailError("Google a refusé l'accès (invalid_grant)")
        return GoogleTokens(
            access_token="access-1",
            refresh_token="refresh-1" if self.gives_refresh_token else None,
            expires_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=1),
            scopes=self.scopes,
        )

    async def revoke(self, token: str) -> bool:
        self.revoked.append(token)
        return True


class FakeModel:
    """The model behind the triage and the reply: its answers, in order, and what it was asked."""

    CUSTOMER_REQUEST: ClassVar[dict[str, Any]] = {
        "is_customer_request": True,
        "type": "quote",
        "language": "fr",
        "name": "Hélène Dupré",
        "summary": "Fuite sur le toit près de la cheminée, demande un devis.",
    }
    NOT_A_REQUEST: ClassVar[dict[str, Any]] = {"is_customer_request": False, "type": "other", "language": "fr"}
    REPLY = (
        "Bonjour Madame Dupré,\n\nMerci pour votre message. Nous revenons vers vous pour convenir d'un passage.\n\n"
        "Bien cordialement,\nGarage Morel"
    )

    def __init__(self) -> None:
        self.verdicts: list[dict[str, Any] | None] = []
        self.replies: list[str | None] = []
        self.triage_calls: list[list[dict[str, Any]]] = []
        self.reply_calls: list[list[dict[str, Any]]] = []

    async def complete_json(self, usage: Any, messages: list[dict[str, Any]], **_: Any) -> dict[str, Any] | None:
        self.triage_calls.append(messages)
        return self.verdicts.pop(0) if self.verdicts else self.CUSTOMER_REQUEST

    async def chat(self, usage: Any, messages: list[dict[str, Any]], **_: Any) -> str | None:
        self.reply_calls.append(messages)
        return self.replies.pop(0) if self.replies else self.REPLY


def add_mailbox_assistant(db: Session, *, status: str = "delivered", is_mailbox_enabled: bool = True) -> AiAssistant:
    """The garage's receptionist (sold by default), its mailbox switched on by the operator."""
    assistant = add_assistant(db, status=status)
    assistant.mailbox_enabled = is_mailbox_enabled
    db.commit()
    return assistant


def add_mailbox(db: Session, assistant: AiAssistant, **fields: Any) -> AiAssistantMailbox:
    """The receptionist's Gmail, connected, its tokens encrypted (``fields`` override the defaults)."""
    values: dict[str, Any] = {
        "user_id": assistant.user_id,
        "assistant_id": assistant.id,
        "account_email": MAILBOX_ADDRESS,
        "access_token_encrypted": encryption_service.encrypt("access-0"),
        "refresh_token_encrypted": encryption_service.encrypt("refresh-0"),
        "token_expires_at": datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=1),
        "history_id": "1000",
        "connected_at": CONNECTED_AT,
    }
    values.update(fields)
    mailbox = AiAssistantMailbox(**values)
    db.add(mailbox)
    db.commit()
    return mailbox
