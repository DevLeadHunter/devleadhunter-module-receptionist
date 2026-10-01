"""
The demo space: the client space a prospect opens from its demo page (« /ia/{slug}/espace »), before buying.

It reads like the space the business gets on the day of the sale, filled from its own receptionist: the business and
the receptionist (first name, portrait, accent, languages, opening hours, imposed and learned answers), the address
for its Google profile and the line for its website, the « Pour démarrer » steps (none done yet), and the requests the
visitor left while testing the demo, with their conversations and photos.

Demo slugs are business names, so anyone can guess one: the space never shows what another visitor left. The page
sends the widget sessions its browser kept, and only the requests of those sessions are listed; below two of them,
examples of the business's trade complete the list, flagged as examples. The unanswered questions stay out too (they
are visitors' words, whatever their session), and so does what the operator set on the demo: its alert mobile, the
site its widget was seen on.

Nothing can be saved from it (every write of the client space takes a client link, which a demo never has), and
reading it counts nothing and announces nothing.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import ClassVar

from sqlalchemy.orm import Session

from core.clock import naive_utc_now
from enums.ai_assistant_request import AiAssistantRequestStatus
from enums.ai_assistant_status import AiAssistantStatus
from models.ai_assistant import AiAssistant
from models.ai_assistant_request import AiAssistantRequest
from schemas.ai_assistant_demo_space import AiAssistantDemoSpaceRequestItem, AiAssistantDemoSpaceResponse
from services.ai_assistant.assistant_service import ai_assistant_service
from services.ai_assistant.business_card import AiAssistantBusinessCard
from services.ai_assistant.calendar_booking import ai_assistant_calendar_booking
from services.ai_assistant.client_space_payload import ai_assistant_client_space_payload
from services.ai_assistant.client_space_service import ai_assistant_client_space_service
from services.ai_assistant.config_builder import ai_assistant_config_builder
from services.ai_assistant.demo_space_examples import ai_assistant_demo_space_examples
from services.ai_assistant.embed_snippet import AiAssistantEmbedSnippet
from services.ai_assistant.faq_service import ai_assistant_faq_service
from services.ai_assistant.limits import AiAssistantLimits
from services.ai_assistant.opening_hours import OpeningHoursCalendar
from services.ai_assistant.request_attachments import AiAssistantRequestAttachments
from services.assistant_pricing_service import AssistantPricingService
from services.assistant_subscription_service import assistant_subscription_service


class AiAssistantDemoSpaceService:
    """Opens the demo space of a live demo and builds what it shows."""

    # The visitor's own requests listed at most, like the client space.
    MAX_VISITOR_REQUESTS: ClassVar[int] = 30
    # From this many requests of their own, the visitor's list shows no example.
    VISITOR_REQUESTS_WITHOUT_EXAMPLES: ClassVar[int] = 2
    # The requests a list completed with examples counts, the visitor's own included.
    REQUESTS_LISTED_WITH_EXAMPLES: ClassVar[int] = 3

    @staticmethod
    def is_open(assistant: AiAssistant, *, now: datetime | None = None) -> bool:
        """
        Whether a receptionist has a demo space: a live demo, neither sold, deleted nor past its countdown.

        Args:
            assistant: The receptionist.
            now: Current time, naive UTC (tests); defaults to now.

        Returns:
            True for a demo whose page still opens.
        """
        if assistant.deleted_at is not None or assistant.status != AiAssistantStatus.ACTIVE.value:
            return False
        expires_at = assistant.expires_at
        if expires_at is None:
            return True
        # Read back from the database the expiry is naive UTC; just set by the countdown it is still aware.
        naive_expiry = expires_at.astimezone(UTC).replace(tzinfo=None) if expires_at.tzinfo else expires_at
        return naive_expiry > (now or naive_utc_now())

    def open_demo(self, db: Session, slug: str, *, now: datetime | None = None) -> AiAssistant | None:
        """
        The live demo a slug names, when it has a demo space.

        Args:
            db: Active database session.
            slug: The demo's public slug.
            now: Current time, naive UTC (tests); defaults to now.

        Returns:
            The demo receptionist, or None for an unknown slug, a sold, deleted or expired receptionist.
        """
        assistant = ai_assistant_service.get_by_slug(db, slug)
        return assistant if assistant is not None and self.is_open(assistant, now=now) else None

    def visitor_requests(self, db: Session, assistant: AiAssistant, session_ids: list[str]) -> list[AiAssistantRequest]:
        """
        The requests a visitor left from their own widget sessions, and no other.

        Args:
            db: Active database session.
            assistant: The demo receptionist.
            session_ids: The widget sessions the visitor's browser kept for this demo.

        Returns:
            Their requests, the waiting ones first, newest first (``MAX_VISITOR_REQUESTS`` at most); none without a
            session. The operator's own tests (« ?internal=1 ») are theirs too, so they are listed.
        """
        distinct_sessions = list(dict.fromkeys(session_ids))
        if not distinct_sessions:
            return []
        return (
            db.query(AiAssistantRequest)
            .filter(
                AiAssistantRequest.assistant_id == assistant.id,
                AiAssistantRequest.session_id.in_(distinct_sessions),
            )
            .order_by(
                AiAssistantRequest.status != AiAssistantRequestStatus.NEW.value,
                AiAssistantRequest.created_at.desc(),
                AiAssistantRequest.id.desc(),
            )
            .limit(self.MAX_VISITOR_REQUESTS)
            .all()
        )

    @classmethod
    def example_count(cls, visitor_request_count: int) -> int:
        """
        How many examples complete the visitor's own requests.

        Args:
            visitor_request_count: The requests the visitor left.

        Returns:
            Enough to list ``REQUESTS_LISTED_WITH_EXAMPLES`` in all, and none from
            ``VISITOR_REQUESTS_WITHOUT_EXAMPLES`` requests of their own.
        """
        if visitor_request_count >= cls.VISITOR_REQUESTS_WITHOUT_EXAMPLES:
            return 0
        return cls.REQUESTS_LISTED_WITH_EXAMPLES - visitor_request_count

    def build(
        self, db: Session, assistant: AiAssistant, session_ids: list[str], *, now: datetime | None = None
    ) -> AiAssistantDemoSpaceResponse:
        """
        Everything the demo space shows: the client space as the business gets it on the day of the sale.

        Args:
            db: Active database session, only read.
            assistant: A live demo (see :meth:`open_demo`).
            session_ids: The widget sessions the visitor's browser kept for this demo.
            now: Current business time, aware (tests); defaults to now.

        Returns:
            The space, read-only (``is_demo``).
        """
        current = now or OpeningHoursCalendar.business_now()
        payload = ai_assistant_client_space_payload
        category = ai_assistant_service.business_category(db, assistant)
        records = self.visitor_requests(db, assistant, session_ids)
        booked = ai_assistant_calendar_booking.booked_labels(db, [record.id for record in records])
        requests = [self._visitor_request_item(db, record, booked.get(record.id)) for record in records]
        requests += ai_assistant_demo_space_examples.requests(
            assistant, category, count=self.example_count(len(records)), now=current
        )
        return AiAssistantDemoSpaceResponse(
            is_demo=True,
            business_name=assistant.business_name,
            business=AiAssistantBusinessCard.of(assistant, now=current),
            assistant_name=assistant.assistant_name,
            assistant_gender=ai_assistant_config_builder.resolve_persona_gender(assistant.assistant_name),
            accent_color=ai_assistant_service.accent_color(assistant),
            link_expires_label=self._last_day_label(assistant),
            pending_count=sum(1 for item in requests if item.status is AiAssistantRequestStatus.NEW),
            requests=requests,
            report=ai_assistant_demo_space_examples.report(assistant, category, now=current),
            # The « Pour démarrer » steps as on the day of the sale: none done.
            settings=payload.settings(assistant).model_copy(update={"alert_phone": None}),
            google_profile=payload.google_profile(assistant).model_copy(
                update={"is_linked": False, "linked_at_label": None}
            ),
            installed=None,
            calendar=payload.calendar_before_connection(),
            mailbox=payload.mailbox_before_connection(assistant),
            language_options=payload.language_options(),
            limits=payload.limits(AiAssistantLimits.effective(assistant)),
            faq=ai_assistant_faq_service.faq_and_unanswered(assistant).faq,
            # The questions it could not answer are visitors' words, whatever their session.
            unanswered=[],
            appointments=[],
            subscription=None,
            fresh_token=None,
            website_url=ai_assistant_client_space_service.website_url(db, assistant),
            embed_snippet=AiAssistantEmbedSnippet.render(assistant.slug),
            subscribe_url=assistant_subscription_service.subscription_link(assistant, "month"),
            monthly_price_label=AssistantPricingService.format_price(
                AssistantPricingService.monthly_price_cents(db, assistant.user_id)
            ),
        )

    @staticmethod
    def _visitor_request_item(
        db: Session, record: AiAssistantRequest, booked: str | None
    ) -> AiAssistantDemoSpaceRequestItem:
        """A request the visitor left, as the client space shows it, with the conversation it came out of."""
        item = ai_assistant_client_space_payload.request_item(record, booked)
        return AiAssistantDemoSpaceRequestItem(
            **item.model_dump(), conversation=AiAssistantRequestAttachments.conversation(db, record)
        )

    @staticmethod
    def _last_day_label(assistant: AiAssistant) -> str:
        """The demo's last day (« 31/10/2026 »), empty while its countdown has not started."""
        if assistant.expires_at is None:
            return ""
        return ai_assistant_client_space_payload.business_label(assistant.expires_at, "%d/%m/%Y")


ai_assistant_demo_space_service = AiAssistantDemoSpaceService()
