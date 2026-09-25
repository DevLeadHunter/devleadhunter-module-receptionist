"""
The client space of a sold assistant: what its client sees and changes through the magic link.

Behind a signed link (``client_links``) and nothing else: the assistant's requests (tests excluded,
the ones still waiting first) with a « traitée » button, its latest monthly report, a few settings (the
assistant's first name, its languages, the alert mobile and channels) and the Stripe billing portal of
its subscription. Only a sold assistant has a client space, and a token only ever reaches its own
assistant. A new alert mobile is announced to the business address, which the space cannot change.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar

from sqlalchemy.orm import Session

from enums.ai_assistant_request import AiAssistantRequestStatus
from enums.ai_assistant_status import AiAssistantStatus
from enums.assistant_subscription_status import AssistantSubscriptionStatus
from enums.assistant_widget_language import AssistantWidgetLanguage
from models.ai_assistant import AiAssistant
from models.ai_assistant_report import AiAssistantReport
from models.ai_assistant_request import AiAssistantRequest
from models.ai_assistant_subscription import AiAssistantSubscription
from services.activity_log_service import CATEGORY_ASSISTANT, STATUS_WARNING, activity_log_service
from services.ai_assistant.assistant_service import ai_assistant_service
from services.ai_assistant.business_mailer import AiAssistantBusinessMailer
from services.ai_assistant.client_links import AiAssistantClientLinks, ClientLinkToken
from services.ai_assistant.client_space_email import AiAssistantClientSpaceEmail
from services.ai_assistant.embed_snippet import AiAssistantEmbedSnippet
from services.ai_assistant.opening_hours import OpeningHoursCalendar
from services.ai_assistant.request_email import RenderedEmail
from services.ai_assistant.request_service import ai_assistant_request_service
from services.assistant_subscription_service import assistant_subscription_service
from services.sms.phone_normalizer import to_served_mobile

logger = logging.getLogger(__name__)

# An expired link still asks for a fresh one this long after its expiry; an older one opens nothing.
RENEWABLE_AFTER_EXPIRY = timedelta(days=90)


class ClientSpaceAccessError(Exception):
    """The link opens no client space: forged, too old, of an assistant no longer sold, or expired."""

    def __init__(self, *, is_expired: bool) -> None:
        super().__init__("expired" if is_expired else "invalid")
        self.is_expired = is_expired


@dataclass(frozen=True)
class ClientLinkDelivery:
    """A client-space link just issued, and where it was emailed."""

    url: str
    expires_at: datetime
    sent_to: str | None = None
    send_error: str | None = None


class AiAssistantClientSpaceService:
    """Resolves a client-space link and serves the reads and edits its page offers."""

    RECENT_REQUESTS: ClassVar[int] = 30
    MAX_PENDING_LISTED: ClassVar[int] = 100
    SETTINGS_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "assistant_name",
            "languages",
            "alert_phone",
            "alert_sms_enabled",
            "alert_email_enabled",
            "alert_sms_types",
            "alert_quiet_start_hour",
            "alert_quiet_end_hour",
        }
    )

    @staticmethod
    def resolve(
        db: Session, token: str, *, allow_expired: bool = False, now: datetime | None = None
    ) -> tuple[AiAssistant, ClientLinkToken]:
        """
        The sold assistant a client-space link opens.

        Args:
            db: Active database session.
            token: The token from the page URL.
            allow_expired: Accept a link expired less than ``RENEWABLE_AFTER_EXPIRY`` ago (to email a
                fresh one to the business).
            now: Current time (tests); defaults to now.

        Returns:
            The assistant and the checked token.

        Raises:
            ClientSpaceAccessError: When the link is malformed, forged, of an assistant that is not sold
                any more, or expired (``is_expired``; an expired link past the renewal window is invalid).
        """
        link = AiAssistantClientLinks.read(token, now=now)
        if link is None:
            raise ClientSpaceAccessError(is_expired=False)
        assistant = db.get(AiAssistant, link.assistant_id)
        if (
            assistant is None
            or assistant.deleted_at is not None
            or assistant.status != AiAssistantStatus.DELIVERED.value
        ):
            raise ClientSpaceAccessError(is_expired=False)
        if link.is_expired:
            current = (now or datetime.now(UTC)).replace(tzinfo=None)
            if link.expires_at < current - RENEWABLE_AFTER_EXPIRY:
                raise ClientSpaceAccessError(is_expired=False)
            if not allow_expired:
                raise ClientSpaceAccessError(is_expired=True)
        return assistant, link

    def recent_requests(self, db: Session, assistant: AiAssistant) -> list[AiAssistantRequest]:
        """
        The assistant's requests to show: every one still waiting (newest first), then the latest others.

        Args:
            db: Active database session.
            assistant: The assistant.

        Returns:
            The waiting requests (at most ``MAX_PENDING_LISTED``), then others up to ``RECENT_REQUESTS``
            in all; tests excluded.
        """
        real = (AiAssistantRequest.assistant_id == assistant.id, AiAssistantRequest.is_test.is_(False))
        newest = (AiAssistantRequest.created_at.desc(), AiAssistantRequest.id.desc())
        pending = (
            db.query(AiAssistantRequest)
            .filter(*real, AiAssistantRequest.status == AiAssistantRequestStatus.NEW.value)
            .order_by(*newest)
            .limit(self.MAX_PENDING_LISTED)
            .all()
        )
        room = self.RECENT_REQUESTS - len(pending)
        if room <= 0:
            return pending
        others = (
            db.query(AiAssistantRequest)
            .filter(*real, AiAssistantRequest.status != AiAssistantRequestStatus.NEW.value)
            .order_by(*newest)
            .limit(room)
            .all()
        )
        return pending + others

    @staticmethod
    def pending_count(db: Session, assistant: AiAssistant) -> int:
        """How many of the assistant's real requests still wait for handling."""
        return (
            db.query(AiAssistantRequest)
            .filter(
                AiAssistantRequest.assistant_id == assistant.id,
                AiAssistantRequest.is_test.is_(False),
                AiAssistantRequest.status == AiAssistantRequestStatus.NEW.value,
            )
            .count()
        )

    @staticmethod
    def latest_report(db: Session, assistant: AiAssistant) -> AiAssistantReport | None:
        """The assistant's latest monthly report with its figures, if any."""
        return (
            db.query(AiAssistantReport)
            .filter(AiAssistantReport.assistant_id == assistant.id, AiAssistantReport.stats_json.is_not(None))
            .order_by(AiAssistantReport.month.desc())
            .first()
        )

    @staticmethod
    def current_subscription(db: Session, assistant: AiAssistant) -> AiAssistantSubscription | None:
        """The assistant's latest subscription that was paid at least once (running, retrying or ended)."""
        return (
            db.query(AiAssistantSubscription)
            .filter(
                AiAssistantSubscription.ai_assistant_id == assistant.id,
                AiAssistantSubscription.status != AssistantSubscriptionStatus.INCOMPLETE.value,
            )
            .order_by(AiAssistantSubscription.created_at.desc(), AiAssistantSubscription.id.desc())
            .first()
        )

    @staticmethod
    def mark_handled(db: Session, assistant: AiAssistant, request_id: int) -> AiAssistantRequest | None:
        """
        Mark one of the assistant's requests handled.

        Args:
            db: Active database session (committed).
            assistant: The assistant the link opens.
            request_id: The request.

        Returns:
            The request, or None when it is not one of this assistant's real requests.
        """
        request = (
            db.query(AiAssistantRequest)
            .filter(
                AiAssistantRequest.id == request_id,
                AiAssistantRequest.assistant_id == assistant.id,
                AiAssistantRequest.is_test.is_(False),
            )
            .first()
        )
        if request is None:
            return None
        ai_assistant_request_service.mark_handled(db, request)
        db.refresh(request)
        return request

    async def update_settings(self, db: Session, assistant: AiAssistant, fields: dict[str, Any]) -> AiAssistant:
        """
        Apply a client's settings edit like the dashboard does, within what a client may change.

        A missing or null field is left as is. The languages the space does not offer (set by the
        operator) are kept. A new alert mobile must be one of the module's countries, and is announced
        by email to the business address and in the operator's activity log.

        Args:
            db: Active database session (committed).
            assistant: The assistant the link opens.
            fields: The provided fields (``model_dump(exclude_unset=True, mode="json")``).

        Returns:
            The refreshed assistant.

        Raises:
            ValueError: When the alert number cannot receive an SMS or is out of the module's countries
                (nothing is saved).
        """
        allowed = {key: value for key, value in fields.items() if key in self.SETTINGS_FIELDS and value is not None}
        if "languages" in allowed:
            offered = {language.value for language in AssistantWidgetLanguage}
            kept = [code for code in (assistant.languages or []) if code not in offered]
            allowed["languages"] = [*allowed["languages"], *kept]
        previous_phone = assistant.alert_phone_e164
        if "alert_phone" in allowed:
            self._check_alert_phone(db, assistant, str(allowed["alert_phone"]))
        updated = ai_assistant_service.update(db, assistant, allowed)
        if updated.alert_phone_e164 != previous_phone:
            await self._announce_alert_phone(db, updated, previous_phone)
        return updated

    async def billing_portal_url(self, db: Session, assistant: AiAssistant, *, return_url: str) -> str | None:
        """
        A Stripe billing portal session for the assistant's subscription (invoices, card, cancellation).

        Args:
            db: Active database session.
            assistant: The assistant the link opens.
            return_url: Where Stripe sends the client back (the client space).

        Returns:
            The portal URL, or None when no Stripe customer is known for the assistant.

        Raises:
            ValueError: When Stripe is not configured.
        """
        subscription = self.current_subscription(db, assistant)
        if subscription is None or not subscription.stripe_customer_id:
            return None
        customer_id = subscription.stripe_customer_id
        # The Stripe client is synchronous: off the event loop, so the API keeps answering meanwhile.
        return await asyncio.to_thread(
            assistant_subscription_service.billing_portal_url, customer_id, return_url=return_url
        )

    async def issue_link(
        self, db: Session, assistant: AiAssistant, *, send: bool, now: datetime | None = None
    ) -> ClientLinkDelivery:
        """
        Sign a fresh client-space link and, when asked, email it to the business from the operator's identity.

        Args:
            db: Active database session.
            assistant: A sold assistant.
            send: Email the link to the business.
            now: Current time (tests); defaults to now.

        Returns:
            The link, its expiry and where it went (never raises on a failed send).
        """
        current = (now or datetime.now(UTC)).replace(tzinfo=None)
        url = AiAssistantClientLinks.url(assistant.id, now=current)
        expires_at = current + timedelta(days=AiAssistantClientLinks.TTL_DAYS)
        if not send:
            return ClientLinkDelivery(url=url, expires_at=expires_at)
        rendered = AiAssistantClientSpaceEmail.render(
            business_name=assistant.business_name,
            assistant_name=assistant.assistant_name,
            url=url,
            expires_on=OpeningHoursCalendar.to_business_time(expires_at).date(),
        )
        recipient, send_error = await self._email_business(db, assistant, rendered)
        return ClientLinkDelivery(url=url, expires_at=expires_at, sent_to=recipient, send_error=send_error)

    async def send_welcome(
        self, db: Session, assistant: AiAssistant, *, now: datetime | None = None
    ) -> ClientLinkDelivery:
        """
        Welcome a business that just subscribed: the line to paste on its site and its client-space link.

        Args:
            db: Active database session.
            assistant: The assistant just sold.
            now: Current time (tests); defaults to now.

        Returns:
            The link, its expiry and where the email went (never raises on a failed send).
        """
        current = (now or datetime.now(UTC)).replace(tzinfo=None)
        url = AiAssistantClientLinks.url(assistant.id, now=current)
        expires_at = current + timedelta(days=AiAssistantClientLinks.TTL_DAYS)
        rendered = AiAssistantClientSpaceEmail.render_welcome(
            business_name=assistant.business_name,
            assistant_name=assistant.assistant_name,
            url=url,
            expires_on=OpeningHoursCalendar.to_business_time(expires_at).date(),
            embed_snippet=AiAssistantEmbedSnippet.render(assistant.slug),
        )
        recipient, send_error = await self._email_business(db, assistant, rendered)
        if send_error is not None:
            logger.warning("Assistant %s: welcome email not sent (%s)", assistant.id, send_error)
        return ClientLinkDelivery(url=url, expires_at=expires_at, sent_to=recipient, send_error=send_error)

    @staticmethod
    def _check_alert_phone(db: Session, assistant: AiAssistant, raw_phone: str) -> None:
        """Refuse an alert mobile outside the module's countries (an empty one clears the SMS alerts)."""
        if not raw_phone.strip():
            return
        if to_served_mobile(raw_phone, country=ai_assistant_service.business_country(db, assistant)) is None:
            raise ValueError(
                "Numéro d'alerte refusé : un mobile français, belge, luxembourgeois, suisse ou allemand est requis"
            )

    @staticmethod
    def _masked_phone(phone: str | None) -> str:
        """A mobile as the activity log keeps it: its last two digits only."""
        return f"…{phone[-2:]}" if phone else "aucun"

    async def _announce_alert_phone(self, db: Session, assistant: AiAssistant, previous_phone: str | None) -> None:
        """Tell the business (by email) and the operator (activity log) that the alert mobile changed."""
        new_phone = assistant.alert_phone_e164
        activity_log_service.record(
            category=CATEGORY_ASSISTANT,
            action="assistant_client_alert_phone_changed",
            status=STATUS_WARNING,
            title=f"{assistant.business_name} · mobile d'alerte changé depuis l'espace client",
            detail=f"{self._masked_phone(previous_phone)} → {self._masked_phone(new_phone)}",
            user_id=assistant.user_id,
            entity_type="prospect",
            entity_id=assistant.prospect_id,
        )
        rendered = AiAssistantClientSpaceEmail.render_alert_phone_changed(
            assistant_name=assistant.assistant_name, new_phone=new_phone
        )
        _recipient, send_error = await self._email_business(db, assistant, rendered)
        if send_error:
            logger.warning("Alert-mobile notice of assistant %s not sent: %s", assistant.id, send_error)

    async def announce_calendar_connected(self, db: Session, assistant: AiAssistant, account_email: str | None) -> None:
        """
        Tell the business, by email, that a Google agenda was connected to its assistant.

        Args:
            db: Active database session.
            assistant: The sold assistant.
            account_email: The connected Google account, when known.
        """
        rendered = AiAssistantClientSpaceEmail.render_calendar_connected(
            assistant_name=assistant.assistant_name, business_name=assistant.business_name, account_email=account_email
        )
        _recipient, send_error = await self._email_business(db, assistant, rendered)
        if send_error:
            logger.warning("Agenda notice of assistant %s not sent: %s", assistant.id, send_error)

    @staticmethod
    async def _email_business(
        db: Session, assistant: AiAssistant, rendered: RenderedEmail
    ) -> tuple[str | None, str | None]:
        """Email the business from the operator's identity; returns (address, None) or (None, why not)."""
        recipient = AiAssistantBusinessMailer.business_email(db, assistant)
        if not recipient:
            return None, "Aucune adresse email du commerçant."
        failure = await AiAssistantBusinessMailer.send(
            db, assistant, rendered, recipient=recipient, recipient_name=assistant.business_name
        )
        return (recipient, None) if failure is None else (None, failure)


ai_assistant_client_space_service = AiAssistantClientSpaceService()
