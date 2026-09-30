"""
The receptionist's reading of its clients' Gmail: each new customer email gets a reply prepared as a draft in its own
thread, and a request the business follows like the widget's.

Every three minutes a pass lists, per connected mailbox, what arrived since the stored history id (Gmail's journal of
changes; the inbox's last day when the id is too old), sorts out before any model call what cannot be a customer's
request (``mail_filter``), asks the model whether the rest is one (``mail_triage``), writes each request's reply
(``mail_reply_writer``) and leaves it as a draft in the email's thread: nothing is ever sent. A reply the business
sends from Gmail marks its request handled. A mailbox reads at most 60 emails with the model and prepares at most 30
drafts per business day. Only the message ids are kept, never an email's content, and no log holds any of it.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, TypeVar

from sqlalchemy import func
from sqlalchemy.orm import Session

from core.clock import naive_utc_now
from core.database import SessionLocal
from enums.ai_assistant_mailbox import AiAssistantMailboxMessageOutcome, AiAssistantMailboxStatus
from enums.ai_assistant_request import AiAssistantRequestChannel, AiAssistantRequestStatus, AiAssistantRequestType
from enums.ai_assistant_status import AiAssistantStatus
from models.ai_assistant import AiAssistant
from models.ai_assistant_mailbox import AiAssistantMailbox
from models.ai_assistant_mailbox_message import AiAssistantMailboxMessage
from models.ai_assistant_request import AiAssistantRequest
from services.ai_assistant.assistant_service import ai_assistant_service
from services.ai_assistant.daily_message_cap import AiAssistantDailyMessageCap
from services.ai_assistant.gmail_client import GmailChanges, GmailError, GmailMessage, gmail_client
from services.ai_assistant.limits import AiAssistantLimits, AssistantLimit
from services.ai_assistant.mail_draft_builder import AiAssistantMailDraftBuilder, MailReplyDraft
from services.ai_assistant.mail_filter import AiAssistantMailFilter
from services.ai_assistant.mail_reply_writer import ai_assistant_mail_reply_writer
from services.ai_assistant.mail_triage import MailTriageVerdict, ai_assistant_mail_triage
from services.ai_assistant.mailbox_access import ai_assistant_mailbox_access
from services.ai_assistant.message_delivery import AiAssistantMessageDelivery
from services.ai_assistant.opening_hours import OpeningHoursCalendar
from services.ai_assistant.request_follow_up import ai_assistant_request_follow_up
from services.ai_assistant.request_service import ai_assistant_request_service
from services.conversation_service import strip_quoted_reply

logger = logging.getLogger(__name__)

T = TypeVar("T")

SYNC_INTERVAL_SECONDS = 180
# Emails read in one pass; a longer burst goes on at the next pass, from the same history id.
MAX_MESSAGES_PER_PASS = 50
DAILY_READ_CAP = 60
DAILY_DRAFT_CAP = 30
# An email the model or Gmail failed on is read again at the next passes, then given up.
MAX_READ_ATTEMPTS = 3
# The customer's words kept on the request and quoted under the reply.
CUSTOMER_WORDS_MAX_CHARS = 3000


@dataclass(frozen=True)
class MailboxContext:
    """What a pass needs of a receptionist and its mailbox, read once: no model call holds a database connection."""

    assistant_id: int
    user_id: int
    business_name: str
    assistant_name: str
    trade: str | None
    tone: str | None
    knowledge: dict[str, Any]
    limits: list[AssistantLimit]
    is_eu_only: bool
    mailbox_address: str
    connected_at: datetime


@dataclass
class MailboxDailyBudget:
    """What a mailbox may still do today (Paris): emails read by the model, drafts prepared."""

    reads_left: int
    drafts_left: int

    @property
    def is_spent(self) -> bool:
        """Whether the day's reads or drafts are all used: the next emails get no draft before tomorrow."""
        return self.reads_left <= 0 or self.drafts_left <= 0


class MailboxRetryLaterError(Exception):
    """An email failed for now (the model or Gmail unavailable): the pass stops, the next one reads it again."""


class AiAssistantMailboxSync:
    """Reads the connected mailboxes and prepares a reply draft to each new customer email."""

    async def run_loop(self, interval_seconds: int = SYNC_INTERVAL_SECONDS) -> None:
        """
        Read every connected mailbox, then wait; a failing pass is logged and the next one runs.

        Args:
            interval_seconds: Delay between two passes.
        """
        while True:
            try:
                await self.run_pass()
            except Exception:
                logger.exception("Mailbox pass failed")
            await asyncio.sleep(interval_seconds)

    async def run_pass(self) -> int:
        """
        One pass over the readable mailboxes, each on its own session: a failing one never stops the others.

        Returns:
            How many mailboxes were read (none, without a query, while Gmail is not configured).
        """
        if not gmail_client.is_configured:
            return 0
        db = SessionLocal()
        try:
            mailbox_ids = self.readable_mailbox_ids(db)
        finally:
            db.close()
        for mailbox_id in mailbox_ids:
            db = SessionLocal()
            try:
                await self.sync_mailbox(db, mailbox_id)
            except Exception:
                logger.exception("Mailbox %s pass failed", mailbox_id)
                db.rollback()
            finally:
                db.close()
        return len(mailbox_ids)

    @staticmethod
    def readable_mailbox_ids(db: Session) -> list[int]:
        """
        The mailboxes to read: connected, of a sold receptionist whose mailbox the operator switched on.

        Args:
            db: Active database session.

        Returns:
            Their ids.
        """
        rows = (
            db.query(AiAssistantMailbox.id)
            .join(AiAssistant, AiAssistant.id == AiAssistantMailbox.assistant_id)
            .filter(
                AiAssistantMailbox.status == AiAssistantMailboxStatus.CONNECTED.value,
                AiAssistant.mailbox_enabled.is_(True),
                AiAssistant.status == AiAssistantStatus.DELIVERED.value,
                AiAssistant.deleted_at.is_(None),
            )
            .order_by(AiAssistantMailbox.id)
            .all()
        )
        return [row[0] for row in rows]

    async def sync_mailbox(self, db: Session, mailbox_id: int, *, now: datetime | None = None) -> None:
        """
        Read what arrived in one mailbox since its history id, and prepare the replies.

        The history id moves on once every email of the batch is read, sorted out, or given up; a lost access puts
        the mailbox in error, and any other Gmail failure leaves it for the next pass.

        Args:
            db: Active database session.
            mailbox_id: The mailbox.
            now: Current business time, aware (tests); defaults to now.
        """
        mailbox = db.get(AiAssistantMailbox, mailbox_id)
        assistant = db.get(AiAssistant, mailbox.assistant_id) if mailbox is not None else None
        if mailbox is None or assistant is None:
            return
        context = MailboxContext(
            assistant_id=assistant.id,
            user_id=assistant.user_id,
            business_name=assistant.business_name,
            assistant_name=assistant.assistant_name,
            trade=ai_assistant_service.business_category(db, assistant),
            tone=assistant.tone,
            knowledge=dict(assistant.knowledge_json or {}),
            limits=AiAssistantLimits.effective(assistant),
            is_eu_only=bool(assistant.eu_only),
            mailbox_address=(mailbox.account_email or "").strip().lower(),
            connected_at=mailbox.connected_at,
        )
        local_now = OpeningHoursCalendar.localize(now or OpeningHoursCalendar.business_now())
        try:
            changes = await self._fetch_changes(db, mailbox)
            self._close_answered_requests(db, context, changes.answered_thread_ids)
            is_batch_read = await self._read_received(db, mailbox, assistant, context, changes, local_now)
        except GmailError as exc:
            if exc.needs_reconnect:
                ai_assistant_mailbox_access.record_lost_access(db, assistant, mailbox, exc)
            else:
                logger.info("Mailbox of assistant %s unreachable for now (%s)", context.assistant_id, exc.status_code)
            return
        if is_batch_read:
            mailbox.history_id = changes.history_id
        mailbox.last_synced_at = naive_utc_now()
        db.commit()

    async def _fetch_changes(self, db: Session, mailbox: AiAssistantMailbox) -> GmailChanges:
        """What arrived since the history id; the inbox's last day, from the current id on, when it is too old."""
        history_id = mailbox.history_id
        if history_id:
            changes = await self._call_gmail(db, mailbox, lambda token: gmail_client.changes_since(token, history_id))
            if changes is not None:
                return changes
        profile = await self._call_gmail(db, mailbox, gmail_client.get_profile)
        received = await self._call_gmail(db, mailbox, gmail_client.recent_inbox) if history_id else []
        return GmailChanges(received=received, answered_thread_ids=frozenset(), history_id=profile.history_id)

    async def _read_received(
        self,
        db: Session,
        mailbox: AiAssistantMailbox,
        assistant: AiAssistant,
        context: MailboxContext,
        changes: GmailChanges,
        local_now: datetime,
    ) -> bool:
        """
        Read the emails received, oldest first; a thread the business answered meanwhile is left to it.

        Returns:
            Whether the whole batch is read (or the day's cap reached): False when some wait for the next pass.
        """
        received = [ref for ref in changes.received if ref.thread_id not in changes.answered_thread_ids]
        known = self._known_messages(db, context.assistant_id, [ref.message_id for ref in received])
        pending = [ref for ref in received if not self._is_settled(known.get(ref.message_id))]
        budget = self._daily_budget(db, context.assistant_id, local_now)
        for ref in pending[:MAX_MESSAGES_PER_PASS]:
            if budget.is_spent:
                self._note_daily_cap(db, assistant, mailbox, local_now.date())
                return True
            try:
                await self._read_message(
                    db, mailbox, assistant, context, ref.message_id, known.get(ref.message_id), budget
                )
            except MailboxRetryLaterError:
                return False
        return len(pending) <= MAX_MESSAGES_PER_PASS

    async def _read_message(
        self,
        db: Session,
        mailbox: AiAssistantMailbox,
        assistant: AiAssistant,
        context: MailboxContext,
        message_id: str,
        record: AiAssistantMailboxMessage | None,
        budget: MailboxDailyBudget,
    ) -> None:
        """Read one email: its headers first, sorted out when they say it cannot be a request, else in full."""
        message = await self._call_gmail(
            db, mailbox, lambda token: gmail_client.get_message(token, message_id, with_body=False)
        )
        if message is None:
            return
        if AiAssistantMailFilter.skip_reason(
            message, mailbox_address=context.mailbox_address, connected_at=context.connected_at
        ):
            self._record(db, context, message, AiAssistantMailboxMessageOutcome.SKIPPED, record)
            return
        message = await self._call_gmail(
            db, mailbox, lambda token: gmail_client.get_message(token, message_id, with_body=True)
        )
        if message is None:
            return
        if AiAssistantMailFilter.body_skip_reason(message):
            self._record(db, context, message, AiAssistantMailboxMessageOutcome.SKIPPED, record)
            return
        await self._answer(db, mailbox, assistant, context, message, record, budget)

    async def _answer(
        self,
        db: Session,
        mailbox: AiAssistantMailbox,
        assistant: AiAssistant,
        context: MailboxContext,
        message: GmailMessage,
        record: AiAssistantMailboxMessage | None,
        budget: MailboxDailyBudget,
    ) -> None:
        """Ask the model whether the email is a request; if so write the reply, leave its draft, file the request."""
        subject = message.headers.get("subject", "")
        words = strip_quoted_reply(message.text)[:CUSTOMER_WORDS_MAX_CHARS]
        budget.reads_left -= 1
        # The model may take tens of seconds: the pool connection goes back meanwhile.
        db.commit()
        triage = await ai_assistant_mail_triage.classify(
            business_name=context.business_name,
            trade=context.trade,
            sender=message.headers.get("reply-to") or message.headers.get("from", ""),
            subject=subject,
            text=words,
            eu_only=context.is_eu_only,
        )
        if triage is None:
            self._record_failed_read(db, context, message, record)
            return
        if not triage.is_customer_request:
            self._record(db, context, message, AiAssistantMailboxMessageOutcome.IGNORED, record)
            return
        reply = await ai_assistant_mail_reply_writer.write(
            business_name=context.business_name,
            assistant_name=context.assistant_name,
            knowledge=context.knowledge,
            limits=context.limits,
            tone=context.tone,
            customer_name=self._customer_name(message, triage),
            language=triage.language,
            subject=subject,
            text=words,
            eu_only=context.is_eu_only,
        )
        if reply is None:
            self._record_failed_read(db, context, message, record)
            return
        raw = AiAssistantMailDraftBuilder.raw(self._reply_draft(context, message, triage, reply, words))
        try:
            await self._call_gmail(
                db, mailbox, lambda token: gmail_client.create_draft(token, thread_id=message.thread_id, raw=raw)
            )
        except GmailError as exc:
            if exc.needs_reconnect:
                raise
            self._record_failed_read(db, context, message, record)
            return
        budget.drafts_left -= 1
        request, is_new_request = self._file_request(db, assistant, message, triage, words)
        self._record(db, context, message, AiAssistantMailboxMessageOutcome.DRAFTED, record, request_id=request.id)
        if is_new_request:
            await self._announce(db, request, assistant)

    async def _call_gmail(self, db: Session, mailbox: AiAssistantMailbox, call: Callable[[str], Awaitable[T]]) -> T:
        """A Gmail call with a valid token (refreshed once on a 401)."""
        return await ai_assistant_mailbox_access.with_fresh_token(db, mailbox, call)

    def _file_request(
        self,
        db: Session,
        assistant: AiAssistant,
        message: GmailMessage,
        triage: MailTriageVerdict,
        words: str,
    ) -> tuple[AiAssistantRequest, bool]:
        """
        The request of a customer's email, as the widget files one: a new email of the same thread within a day
        updates its request while it waits.
        """
        contact = AiAssistantMailFilter.customer_address(message) or ""
        received_utc = message.received_at or naive_utc_now()
        request, is_new_request = ai_assistant_request_service.capture(
            db,
            assistant=assistant,
            name=self._customer_name(message, triage) or contact.split("@", 1)[0],
            contact=contact,
            need=words or message.headers.get("subject"),
            language=triage.language,
            session_id=f"gmail:{message.thread_id}",
            channel=AiAssistantRequestChannel.EMAIL,
            now=OpeningHoursCalendar.to_business_time(received_utc),
        )
        if request.type != AiAssistantRequestType.URGENT.value:
            request.type = triage.request_type.value
        request.need_summary = triage.summary or request.need
        db.commit()
        return request, is_new_request

    @staticmethod
    async def _announce(db: Session, request: AiAssistantRequest, assistant: AiAssistant) -> None:
        """Announce a new email request (push, alerts); a failure is left to the runner's recovery."""
        try:
            await ai_assistant_request_follow_up.announce(db, request, assistant, [])
        except Exception:
            logger.exception("Mailbox request %s announcement failed", request.id)
            db.rollback()

    @classmethod
    def _reply_draft(
        cls, context: MailboxContext, message: GmailMessage, triage: MailTriageVerdict, reply: str, words: str
    ) -> MailReplyDraft:
        """The draft of the reply: to the customer, in the email's thread, their words quoted under it."""
        return MailReplyDraft(
            from_address=context.mailbox_address,
            to_address=AiAssistantMailFilter.customer_address(message) or "",
            to_name=cls._customer_name(message, triage),
            subject=message.headers.get("subject", ""),
            message_id=message.headers.get("message-id"),
            references=message.headers.get("references"),
            body=reply,
            quoted_text=words,
            quoted_at=OpeningHoursCalendar.to_business_time(message.received_at) if message.received_at else None,
        )

    @staticmethod
    def _customer_name(message: GmailMessage, triage: MailTriageVerdict) -> str | None:
        """The customer's name as they signed, else as their address carries it."""
        return triage.customer_name or AiAssistantMailFilter.customer_display_name(message)

    @staticmethod
    def _close_answered_requests(db: Session, context: MailboxContext, thread_ids: frozenset[str]) -> None:
        """Mark handled the waiting requests whose thread the business just answered from Gmail."""
        if not thread_ids:
            return
        requests = (
            db.query(AiAssistantRequest)
            .join(AiAssistantMailboxMessage, AiAssistantMailboxMessage.request_id == AiAssistantRequest.id)
            .filter(
                AiAssistantMailboxMessage.assistant_id == context.assistant_id,
                AiAssistantMailboxMessage.gmail_thread_id.in_(sorted(thread_ids)),
                AiAssistantRequest.status == AiAssistantRequestStatus.NEW.value,
            )
            .distinct()
            .all()
        )
        for request in requests:
            ai_assistant_request_service.mark_handled(db, request)

    @staticmethod
    def _known_messages(db: Session, assistant_id: int, message_ids: list[str]) -> dict[str, AiAssistantMailboxMessage]:
        """The emails of a batch already read, by message id."""
        if not message_ids:
            return {}
        rows = (
            db.query(AiAssistantMailboxMessage)
            .filter(
                AiAssistantMailboxMessage.assistant_id == assistant_id,
                AiAssistantMailboxMessage.gmail_message_id.in_(message_ids),
            )
            .all()
        )
        return {row.gmail_message_id: row for row in rows}

    @staticmethod
    def _is_settled(record: AiAssistantMailboxMessage | None) -> bool:
        """Whether an email needs no more reading: done, or failed too many times."""
        if record is None:
            return False
        return record.outcome != AiAssistantMailboxMessageOutcome.FAILED.value or record.attempts >= MAX_READ_ATTEMPTS

    @staticmethod
    def _daily_budget(db: Session, assistant_id: int, local_now: datetime) -> MailboxDailyBudget:
        """What is left of the day's reads and drafts (Paris), from the emails read since midnight."""
        rows = (
            db.query(AiAssistantMailboxMessage.outcome, func.count(AiAssistantMailboxMessage.id))
            .filter(
                AiAssistantMailboxMessage.assistant_id == assistant_id,
                AiAssistantMailboxMessage.outcome != AiAssistantMailboxMessageOutcome.SKIPPED.value,
                AiAssistantMailboxMessage.created_at >= AiAssistantDailyMessageCap.day_start(local_now),
            )
            .group_by(AiAssistantMailboxMessage.outcome)
            .all()
        )
        counts = {outcome: int(count) for outcome, count in rows}
        return MailboxDailyBudget(
            reads_left=DAILY_READ_CAP - sum(counts.values()),
            drafts_left=DAILY_DRAFT_CAP - counts.get(AiAssistantMailboxMessageOutcome.DRAFTED.value, 0),
        )

    @staticmethod
    def _note_daily_cap(db: Session, assistant: AiAssistant, mailbox: AiAssistantMailbox, today: date) -> None:
        """Keep the day the cap stopped the reading, and tell the operator once that day."""
        if mailbox.capped_on == today:
            return
        mailbox.capped_on = today
        db.commit()
        AiAssistantMessageDelivery.record_warning(
            assistant,
            action="assistant_mailbox_capped",
            title="boîte mail : limite du jour atteinte",
            detail=(
                f"{DAILY_READ_CAP} emails lus ou {DAILY_DRAFT_CAP} brouillons aujourd'hui : les emails suivants "
                "n'ont pas de brouillon."
            ),
        )

    @staticmethod
    def _record(
        db: Session,
        context: MailboxContext,
        message: GmailMessage,
        outcome: AiAssistantMailboxMessageOutcome,
        record: AiAssistantMailboxMessage | None,
        *,
        request_id: int | None = None,
    ) -> AiAssistantMailboxMessage:
        """Note what became of an email (its ids only), so it is never read twice."""
        row = record
        if row is None:
            row = AiAssistantMailboxMessage(
                user_id=context.user_id,
                assistant_id=context.assistant_id,
                gmail_message_id=message.message_id,
                gmail_thread_id=message.thread_id,
                attempts=0,
            )
            db.add(row)
        row.outcome = outcome.value
        if request_id is not None:
            row.request_id = request_id
        db.commit()
        return row

    def _record_failed_read(
        self,
        db: Session,
        context: MailboxContext,
        message: GmailMessage,
        record: AiAssistantMailboxMessage | None,
    ) -> None:
        """
        Count a failed read of an email.

        Raises:
            MailboxRetryLaterError: While it may be read again (the pass stops there).
        """
        row = self._record(db, context, message, AiAssistantMailboxMessageOutcome.FAILED, record)
        row.attempts = (row.attempts or 0) + 1
        db.commit()
        if row.attempts < MAX_READ_ATTEMPTS:
            raise MailboxRetryLaterError(message.message_id)
        logger.warning(
            "Mailbox of assistant %s gave up message %s after %s attempts",
            context.assistant_id,
            message.message_id,
            row.attempts,
        )


ai_assistant_mailbox_sync = AiAssistantMailboxSync()
