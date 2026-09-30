"""
A sold receptionist's Gmail mailbox: its connection from the client space, where it stands, and its disconnection.

The operator switches the mailbox on per receptionist (``mailbox_enabled``): Gmail's reading scope is restricted by
Google, and an unverified application only lets its declared test users connect. The client then connects their Gmail
from the client space, and ``mailbox_sync`` reads it every few minutes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import ClassVar

from sqlalchemy import func
from sqlalchemy.orm import Session

from core.clock import naive_utc_now
from enums.ai_assistant_mailbox import (
    AiAssistantMailboxConnection,
    AiAssistantMailboxMessageOutcome,
    AiAssistantMailboxStatus,
)
from enums.ai_assistant_status import AiAssistantStatus
from enums.email_account_type import EmailAccountType
from models.ai_assistant import AiAssistant
from models.ai_assistant_calendar import AiAssistantCalendar
from models.ai_assistant_mailbox import AiAssistantMailbox
from models.ai_assistant_mailbox_message import AiAssistantMailboxMessage
from models.email_account import EmailAccount
from models.user import User
from services.activity_log_service import CATEGORY_ASSISTANT, STATUS_SUCCESS, activity_log_service
from services.ai_assistant.gmail_client import GMAIL_COMPOSE_SCOPE, GMAIL_READONLY_SCOPE, GmailError, gmail_client
from services.ai_assistant.mailbox_access import ai_assistant_mailbox_access
from services.ai_assistant.oauth_state import AiAssistantOAuthState
from services.ai_assistant.opening_hours import OpeningHoursCalendar
from services.encryption_service import encryption_service

logger = logging.getLogger(__name__)


class AiAssistantMailboxOAuthState(AiAssistantOAuthState):
    """The OAuth ``state`` of a mailbox connection."""

    _PURPOSE: ClassVar[str] = "assistant-mailbox-oauth"


@dataclass(frozen=True)
class MailboxView:
    """Where a receptionist's mailbox stands: its connection, the address it reads, its last error, its daily cap."""

    connection: AiAssistantMailboxConnection
    account_email: str | None = None
    last_error: str | None = None
    # The daily cap stopped the reading today (Paris).
    has_reached_daily_cap: bool = False


class AiAssistantMailboxService:
    """Connects a sold receptionist's Gmail, tells where it stands, and disconnects it."""

    RETENTION: ClassVar[timedelta] = timedelta(days=90)

    @staticmethod
    def authorization_url(assistant: AiAssistant) -> str:
        """
        The Google consent page that connects a receptionist's Gmail.

        Args:
            assistant: The sold receptionist, its mailbox switched on.

        Returns:
            The consent URL, with a signed state valid 15 minutes.

        Raises:
            ValueError: When Google or the mailboxes' redirect address is not configured on the server.
        """
        if not gmail_client.is_configured:
            raise ValueError("La connexion Gmail n'est pas configurée sur le serveur")
        return gmail_client.authorization_url(AiAssistantMailboxOAuthState.sign(assistant.id))

    async def connect(self, db: Session, *, code: str, state: str) -> tuple[AiAssistant, AiAssistantMailbox]:
        """
        Finish a consent: store the account's tokens (encrypted) and start reading from its current history id.

        Args:
            db: Active database session.
            code: The consent code.
            state: The state signed by :meth:`authorization_url`.

        Returns:
            The receptionist and its connected mailbox.

        Raises:
            ValueError: When the state is invalid, the receptionist cannot read a mailbox, an access was not granted
                or the account has no Gmail.
            GmailError: When Google refuses the code or the profile.
        """
        assistant_id = AiAssistantMailboxOAuthState.read(state)
        if assistant_id is None:
            raise ValueError("Lien de connexion expiré : recommencez depuis votre espace")
        assistant = (
            db.query(AiAssistant)
            .filter(
                AiAssistant.id == assistant_id,
                AiAssistant.deleted_at.is_(None),
                AiAssistant.status == AiAssistantStatus.DELIVERED.value,
                AiAssistant.mailbox_enabled.is_(True),
            )
            .first()
        )
        if assistant is None:
            raise ValueError("Cette réceptionniste ne peut pas lire de boîte mail")
        tokens = await gmail_client.exchange_code(code)
        # Google lets the client untick a permission: without both, nothing is stored.
        if not {GMAIL_READONLY_SCOPE, GMAIL_COMPOSE_SCOPE} <= tokens.scopes:
            raise ValueError("Cochez les deux accès à Gmail dans la fenêtre de Google")
        if not tokens.refresh_token:
            raise ValueError("Google n'a pas donné d'accès durable : recommencez")
        try:
            profile = await gmail_client.get_profile(tokens.access_token)
        except GmailError as exc:
            if exc.status_code == 400:
                raise ValueError("Ce compte Google n'a pas de boîte Gmail") from exc
            raise

        mailbox = ai_assistant_mailbox_access.mailbox_of(db, assistant)
        if mailbox is None:
            mailbox = AiAssistantMailbox(user_id=assistant.user_id, assistant_id=assistant.id)
            db.add(mailbox)
        mailbox.provider = "gmail"
        mailbox.account_email = profile.email_address
        mailbox.access_token_encrypted = encryption_service.encrypt(tokens.access_token)
        mailbox.refresh_token_encrypted = encryption_service.encrypt(tokens.refresh_token)
        mailbox.token_expires_at = tokens.expires_at
        mailbox.history_id = profile.history_id
        mailbox.status = AiAssistantMailboxStatus.CONNECTED.value
        mailbox.last_error = None
        mailbox.capped_on = None
        mailbox.connected_at = naive_utc_now()
        mailbox.last_synced_at = None
        db.commit()
        db.refresh(mailbox)
        activity_log_service.record(
            category=CATEGORY_ASSISTANT,
            action="assistant_mailbox_connected",
            status=STATUS_SUCCESS,
            title=f"{assistant.business_name} · boîte Gmail connectée depuis l'espace client",
            detail=profile.email_address,
            user_id=assistant.user_id,
            entity_type="prospect",
            entity_id=assistant.prospect_id,
        )
        return assistant, mailbox

    async def disconnect(self, db: Session, assistant: AiAssistant) -> None:
        """
        Forget a receptionist's mailbox: its tokens are deleted here and its grant revoked at Google.

        The grant is kept when the same Google account still serves here (an agenda, another mailbox, a sending
        account, Postmaster): a revocation covers every access of the account, theirs included.

        Args:
            db: Active database session.
            assistant: The receptionist.
        """
        mailbox = ai_assistant_mailbox_access.mailbox_of(db, assistant)
        if mailbox is None:
            return
        refresh_token = ai_assistant_mailbox_access.decrypt(mailbox.refresh_token_encrypted)
        is_account_shared = self._is_account_shared(db, mailbox, erased_assistant_id=None)
        account_email = mailbox.account_email
        db.delete(mailbox)
        db.commit()
        if refresh_token and not is_account_shared:
            await gmail_client.revoke(refresh_token)
        activity_log_service.record(
            category=CATEGORY_ASSISTANT,
            action="assistant_mailbox_disconnected",
            status=STATUS_SUCCESS,
            title=f"{assistant.business_name} · boîte Gmail déconnectée",
            detail=account_email or "adresse du compte inconnue",
            user_id=assistant.user_id,
            entity_type="prospect",
            entity_id=assistant.prospect_id,
        )

    async def revoke_for_erased_assistant(self, db: Session, assistant: AiAssistant) -> None:
        """
        Revoke a deleted receptionist's Gmail grant before its rows are erased (its own agenda goes with them).

        Args:
            db: Active database session.
            assistant: The deleted receptionist.
        """
        mailbox = ai_assistant_mailbox_access.mailbox_of(db, assistant)
        if mailbox is None:
            return
        refresh_token = ai_assistant_mailbox_access.decrypt(mailbox.refresh_token_encrypted)
        if refresh_token and not self._is_account_shared(db, mailbox, erased_assistant_id=assistant.id):
            await gmail_client.revoke(refresh_token)

    @staticmethod
    def view(assistant: AiAssistant, mailbox: AiAssistantMailbox | None, *, today: date | None = None) -> MailboxView:
        """
        Where a receptionist's mailbox stands.

        Args:
            assistant: The receptionist.
            mailbox: Its mailbox row, if any.
            today: The business day (tests); defaults to today in Paris.

        Returns:
            The view: off, unavailable on the server, to connect, connected or to reconnect.
        """
        if not assistant.mailbox_enabled:
            return MailboxView(connection=AiAssistantMailboxConnection.DISABLED)
        if not gmail_client.is_configured:
            return MailboxView(connection=AiAssistantMailboxConnection.UNAVAILABLE)
        if mailbox is None:
            return MailboxView(connection=AiAssistantMailboxConnection.DISCONNECTED)
        connection = (
            AiAssistantMailboxConnection.ERROR
            if mailbox.status == AiAssistantMailboxStatus.ERROR.value
            else AiAssistantMailboxConnection.CONNECTED
        )
        business_day = today or OpeningHoursCalendar.business_now().date()
        return MailboxView(
            connection=connection,
            account_email=mailbox.account_email,
            last_error=mailbox.last_error if connection is AiAssistantMailboxConnection.ERROR else None,
            has_reached_daily_cap=mailbox.capped_on == business_day,
        )

    def views_for_assistants(self, db: Session, assistants: list[AiAssistant]) -> dict[int, MailboxView]:
        """
        The mailbox of each receptionist of a list, in one query.

        Args:
            db: Active database session.
            assistants: The receptionists listed.

        Returns:
            Views keyed by receptionist id (every id present).
        """
        enabled_ids = [assistant.id for assistant in assistants if assistant.mailbox_enabled]
        rows = (
            db.query(AiAssistantMailbox).filter(AiAssistantMailbox.assistant_id.in_(enabled_ids)).all()
            if enabled_ids
            else []
        )
        by_assistant = {row.assistant_id: row for row in rows}
        return {assistant.id: self.view(assistant, by_assistant.get(assistant.id)) for assistant in assistants}

    @staticmethod
    def drafts_this_month(db: Session, assistant: AiAssistant, *, now: datetime | None = None) -> int:
        """
        How many reply drafts the receptionist prepared since the first of the month (Paris).

        Args:
            db: Active database session.
            assistant: The receptionist.
            now: Current business time, aware (tests); defaults to now.

        Returns:
            The count of drafted emails.
        """
        local_now = OpeningHoursCalendar.localize(now or OpeningHoursCalendar.business_now())
        month_start = datetime.combine(
            local_now.date().replace(day=1), time.min, tzinfo=OpeningHoursCalendar.business_timezone()
        )
        return (
            db.query(func.count(AiAssistantMailboxMessage.id))
            .filter(
                AiAssistantMailboxMessage.assistant_id == assistant.id,
                AiAssistantMailboxMessage.outcome == AiAssistantMailboxMessageOutcome.DRAFTED.value,
                AiAssistantMailboxMessage.created_at >= OpeningHoursCalendar.to_utc(month_start),
            )
            .scalar()
            or 0
        )

    def purge_old_messages(self, db: Session, *, now: datetime | None = None) -> int:
        """
        Forget the emails read more than 90 days ago (their ids, and what became of them).

        Args:
            db: Active database session (committed).
            now: Current naive UTC time (tests); defaults to now.

        Returns:
            How many rows were deleted.
        """
        cutoff = (now or naive_utc_now()) - self.RETENTION
        deleted = (
            db.query(AiAssistantMailboxMessage)
            .filter(AiAssistantMailboxMessage.created_at < cutoff)
            .delete(synchronize_session=False)
        )
        db.commit()
        return int(deleted or 0)

    @staticmethod
    def _is_account_shared(db: Session, mailbox: AiAssistantMailbox, *, erased_assistant_id: int | None) -> bool:
        """Whether the mailbox's Google account also serves here: an agenda, another mailbox, a sending account."""
        address = (mailbox.account_email or "").strip().lower()
        if not address:
            return False
        calendars = db.query(AiAssistantCalendar.id).filter(func.lower(AiAssistantCalendar.account_email) == address)
        if erased_assistant_id is not None:
            calendars = calendars.filter(AiAssistantCalendar.assistant_id != erased_assistant_id)
        other_mailboxes = db.query(AiAssistantMailbox.id).filter(
            func.lower(AiAssistantMailbox.account_email) == address, AiAssistantMailbox.id != mailbox.id
        )
        senders = db.query(EmailAccount.id).filter(
            func.lower(EmailAccount.email) == address,
            EmailAccount.account_type == EmailAccountType.GMAIL_OAUTH.value,
        )
        postmaster = db.query(User.id).filter(func.lower(User.postmaster_google_email) == address)
        return any(query.first() is not None for query in (calendars, other_mailboxes, senders, postmaster))


ai_assistant_mailbox_service = AiAssistantMailboxService()
