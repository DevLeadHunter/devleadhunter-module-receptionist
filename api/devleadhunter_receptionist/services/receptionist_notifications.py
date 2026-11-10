"""The receptionist's notifications: its leads, subscriptions, alerts and video page, pushed like the core's."""

from __future__ import annotations

from sqlalchemy.orm import Session

from devleadhunter_receptionist.activity import CATEGORY_ASSISTANT
from services.activity_log_service import STATUS_SUCCESS, STATUS_WARNING, activity_log_service
from services.notification_service import notification_service
from services.robot_visit_detector import VisitorBrowser

RECEPTIONIST_MODULE_KEY: str = "ai-assistant"
# Which product a notification belongs to, shown first in the body (both modules otherwise look alike in a push).
_MODULE_TAG_ASSISTANT = "🤖 Assistant IA"
# Deep links opened when a notification is tapped.
_PROSPECTS_URL = "/dashboard/my-prospects"
_ASSISTANTS_URL = "/dashboard/ai-assistants"
_SUBSCRIPTIONS_URL = "/dashboard/subscriptions"
_DASHBOARD_URL = "/dashboard"

# Receptionist video page (/va) events, as (emoji, level, body): the site video's pushes, under the assistant module.
_ASSISTANT_VIDEO_EVENT_NOTIFS: dict[str, tuple[str, str, str]] = {
    "assistant_video_opened": ("🎬", "success", "A ouvert ta vidéo"),
    "assistant_video_play": ("▶️", "success", "Lance ta vidéo"),
    "assistant_video_complete": ("✅", "success", "A vu ta vidéo en entier"),
    "assistant_video_replay": ("🔁", "success", "Revoit ta vidéo"),
}


class ReceptionistNotifications:
    """Composes the receptionist's notifications; the core's notification service stores and pushes them."""

    async def notify_assistant_video_event(
        self,
        db: Session,
        *,
        user_id: int,
        prospect_id: int | None,
        event_name: str,
        fallback_name: str,
        channel: str | None = None,
        browser: VisitorBrowser | None = None,
    ) -> None:
        """
        Raise a notification for a behavioural event on a receptionist's prospection video page (/va).

        An event a robot's browser beaconed is only logged in the activity feed, like on a demo.

        Args:
            db: Active database session (to resolve the prospect's name).
            user_id: Owner of the assistant, the notification recipient.
            prospect_id: Prospect the assistant was generated for, when known.
            event_name: Beaconed event name (e.g. ``assistant_video_play``).
            fallback_name: Name shown when the prospect can't be resolved (e.g. the slug).
            channel: Marketing channel that brought the visit ('email' / 'sms' / 'direct').
            browser: What the visitor's browser told of itself, None when the beacon said nothing.
        """
        await notification_service.notify_module_page_event(
            db,
            module_key=RECEPTIONIST_MODULE_KEY,
            page_events=_ASSISTANT_VIDEO_EVENT_NOTIFS,
            activity_category=CATEGORY_ASSISTANT,
            user_id=user_id,
            prospect_id=prospect_id,
            event_name=event_name,
            fallback_name=fallback_name,
            channel=channel,
            browser=browser,
        )

    async def notify_assistant_subscription(
        self,
        db: Session,
        *,
        user_id: int,
        prospect_id: int | None,
        fallback_name: str,
        amount_cents: int,
        interval: str,
    ) -> None:
        """
        Raise a notification when a client subscribes to their AI assistant — the sale's final step.

        Args:
            db: Active database session (to resolve the prospect's name).
            user_id: Owner of the assistant — the notification recipient.
            prospect_id: Prospect the assistant was sold to, when known.
            fallback_name: Name shown when the prospect can't be resolved.
            amount_cents: The locked subscription amount in cents.
            interval: ``"month"`` or ``"year"``.
        """
        prospect_name = notification_service.prospect_display_name(db, prospect_id, fallback_name)
        plan = f"{self.format_amount(amount_cents, 'eur')}{'/an' if interval == 'year' else '/mois'}"
        activity_log_service.record(
            category=CATEGORY_ASSISTANT,
            action="assistant_subscribed",
            status=STATUS_SUCCESS,
            title=f"{prospect_name} · Abonné à l'assistant {plan}",
            user_id=user_id,
            entity_type="prospect" if prospect_id else None,
            entity_id=prospect_id,
        )
        await notification_service.notify_module_event(
            user_id=user_id,
            category="assistant",
            level="success",
            title=f"🎉 {prospect_name}",
            body=f"{_MODULE_TAG_ASSISTANT} · S'est abonné — {plan}",
            url=f"{_PROSPECTS_URL}?open={prospect_id}" if prospect_id else _DASHBOARD_URL,
            tag=f"assistant-sub-{prospect_id}" if prospect_id else None,
        )

    async def notify_assistant_payment_failed(
        self,
        db: Session,
        *,
        user_id: int,
        prospect_id: int | None,
        fallback_name: str,
        invoice_id: str,
    ) -> None:
        """
        Warn the operator that Stripe could not charge a subscriber: the subscription is now past due.

        Args:
            db: Active database session (to resolve the prospect's name).
            user_id: Owner of the assistant — the notification recipient.
            prospect_id: Prospect the assistant was sold to, when known.
            fallback_name: Name shown when the prospect can't be resolved.
            invoice_id: The Stripe invoice whose payment failed.
        """
        prospect_name = notification_service.prospect_display_name(db, prospect_id, fallback_name)
        activity_log_service.record(
            category=CATEGORY_ASSISTANT,
            action="assistant_payment_failed",
            status=STATUS_WARNING,
            title=f"{prospect_name} · Paiement refusé (abonnement réceptionniste)",
            detail=f"Facture Stripe {invoice_id}",
            user_id=user_id,
            entity_type="prospect" if prospect_id else None,
            entity_id=prospect_id,
        )
        await notification_service.notify_module_event(
            user_id=user_id,
            category="assistant",
            level="warning",
            title=f"💳 {prospect_name}",
            body=f"{_MODULE_TAG_ASSISTANT} · Paiement refusé : {prospect_name} (abonnement réceptionniste)",
            url=_SUBSCRIPTIONS_URL,
            tag=f"assistant-payment-failed-{prospect_id}" if prospect_id else None,
        )

    async def notify_assistant_lead(
        self,
        db: Session,
        *,
        user_id: int,
        prospect_id: int | None,
        fallback_name: str,
        lead_name: str,
        need: str,
        request_label: str | None = None,
        received_outside_hours: bool | None = None,
    ) -> None:
        """
        Raise a notification when a visitor leaves their details through an AI assistant.

        Args:
            db: Active database session (to resolve the prospect's name).
            user_id: Owner of the assistant — the notification recipient.
            prospect_id: Prospect the assistant was generated for, when known.
            fallback_name: Name shown when the prospect can't be resolved.
            lead_name: Name the visitor gave.
            need: What the visitor is after (may be empty).
            request_label: The request type in French (« Demande de devis »…), when typed.
            received_outside_hours: True when it came in while the business was closed.
        """
        prospect_name = notification_service.prospect_display_name(db, prospect_id, fallback_name)
        summary = need.strip() or "Demande de rappel"
        label = request_label or "Nouvelle demande"
        activity_log_service.record(
            category=CATEGORY_ASSISTANT,
            action="assistant_lead",
            status=STATUS_SUCCESS,
            title=f"{prospect_name} · {label} via l'assistant IA",
            user_id=user_id,
            entity_type="prospect" if prospect_id else None,
            entity_id=prospect_id,
        )
        outside_hours = " (hors horaires)" if received_outside_hours else ""
        await notification_service.notify_module_event(
            user_id=user_id,
            category="assistant",
            level="success",
            title=f"🙋 {lead_name}",
            body=f"{_MODULE_TAG_ASSISTANT} · {label}{outside_hours} pour {prospect_name} — {summary}",
            url=f"{_PROSPECTS_URL}?open={prospect_id}" if prospect_id else _DASHBOARD_URL,
            tag=f"assistant-lead-{prospect_id}" if prospect_id else None,
        )

    async def notify_assistant_requests_waiting(
        self,
        db: Session,
        *,
        user_id: int,
        prospect_id: int | None,
        fallback_name: str,
        waiting_count: int,
    ) -> None:
        """
        Warn the operator that a subscriber leaves requests unanswered for 48 h (a churn signal).

        Args:
            db: Active database session (to resolve the prospect's name).
            user_id: Owner of the assistant — the notification recipient.
            prospect_id: Prospect the assistant was sold to, when known.
            fallback_name: Name shown when the prospect can't be resolved.
            waiting_count: How many of its requests have waited 48 h or more without being handled.
        """
        prospect_name = notification_service.prospect_display_name(db, prospect_id, fallback_name)
        waiting = "1 demande non traitée" if waiting_count == 1 else f"{waiting_count} demandes non traitées"
        activity_log_service.record(
            category=CATEGORY_ASSISTANT,
            action="assistant_requests_waiting",
            status=STATUS_WARNING,
            title=f"{prospect_name} · {waiting} depuis 48 h",
            user_id=user_id,
            entity_type="prospect" if prospect_id else None,
            entity_id=prospect_id,
        )
        await notification_service.notify_module_event(
            user_id=user_id,
            category="assistant",
            level="warning",
            title=f"⏳ {prospect_name}",
            body=f"{_MODULE_TAG_ASSISTANT} · Abonné {prospect_name} : {waiting} depuis 48 h (risque de désabonnement)",
            url=_ASSISTANTS_URL,
            tag=f"assistant-waiting-{prospect_id}" if prospect_id else None,
        )

    async def notify_assistant_inactive(
        self,
        db: Session,
        *,
        user_id: int,
        prospect_id: int | None,
        fallback_name: str,
        month_label: str,
    ) -> None:
        """
        Warn the operator that a subscriber's assistant had no visit at all over a month (a churn signal).

        Args:
            db: Active database session (to resolve the prospect's name).
            user_id: Owner of the assistant — the notification recipient.
            prospect_id: Prospect the assistant was sold to, when known.
            fallback_name: Name shown when the prospect can't be resolved.
            month_label: The silent month, in French (« septembre 2026 »).
        """
        prospect_name = notification_service.prospect_display_name(db, prospect_id, fallback_name)
        activity_log_service.record(
            category=CATEGORY_ASSISTANT,
            action="assistant_month_inactive",
            status=STATUS_WARNING,
            title=f"{prospect_name} · aucune activité en {month_label}",
            user_id=user_id,
            entity_type="prospect" if prospect_id else None,
            entity_id=prospect_id,
        )
        await notification_service.notify_module_event(
            user_id=user_id,
            category="assistant",
            level="warning",
            title=f"💤 {prospect_name}",
            body=f"{_MODULE_TAG_ASSISTANT} · Abonné {prospect_name} : aucune visite en {month_label} (risque de désabonnement)",
            url=_ASSISTANTS_URL,
            tag=f"assistant-inactive-{prospect_id}" if prospect_id else None,
        )

    async def notify_assistant_daily_cap_reached(
        self,
        db: Session,
        *,
        user_id: int,
        prospect_id: int | None,
        fallback_name: str,
        cap: int,
    ) -> None:
        """
        Warn the operator that an assistant answered its daily cap of visitor messages (fixed replies until midnight).

        Args:
            db: Active database session (to resolve the prospect's name).
            user_id: Owner of the assistant — the notification recipient.
            prospect_id: Prospect the assistant was generated for, when known.
            fallback_name: Name shown when the prospect can't be resolved.
            cap: The visitor messages a day the model answers.
        """
        prospect_name = notification_service.prospect_display_name(db, prospect_id, fallback_name)
        activity_log_service.record(
            category=CATEGORY_ASSISTANT,
            action="assistant_daily_cap_reached",
            status=STATUS_WARNING,
            title=f"{prospect_name} · plafond de {cap} messages atteint aujourd'hui",
            user_id=user_id,
            entity_type="prospect" if prospect_id else None,
            entity_id=prospect_id,
        )
        await notification_service.notify_module_event(
            user_id=user_id,
            category="assistant",
            level="warning",
            title=f"🧯 {prospect_name}",
            body=(
                f"{_MODULE_TAG_ASSISTANT} · {cap} messages de visiteurs aujourd'hui : "
                "la réceptionniste propose le rappel jusqu'à minuit"
            ),
            url=_ASSISTANTS_URL,
            tag=f"assistant-daily-cap-{prospect_id}" if prospect_id else None,
        )

    async def notify_assistant_interest(
        self,
        db: Session,
        *,
        user_id: int,
        prospect_id: int | None,
        fallback_name: str,
        message: str,
    ) -> None:
        """
        Raise a notification when a prospect raises their hand on their assistant sales page.

        This is the business owner asking to be contacted — the strongest buy signal for the
        AI-assistant module, distinct from a customer lead captured inside the widget.

        Args:
            db: Active database session (to resolve the prospect's name).
            user_id: Owner of the assistant — the notification recipient.
            prospect_id: Prospect the assistant was generated for, when known.
            fallback_name: Name shown when the prospect can't be resolved.
            message: The prospect's optional message (may be empty).
        """
        prospect_name = notification_service.prospect_display_name(db, prospect_id, fallback_name)
        summary = message.strip() or "veut être recontacté"
        activity_log_service.record(
            category=CATEGORY_ASSISTANT,
            action="assistant_interest",
            status=STATUS_SUCCESS,
            title=f"{prospect_name} · Intéressé par l'assistant IA",
            detail=message.strip() or None,
            user_id=user_id,
            entity_type="prospect" if prospect_id else None,
            entity_id=prospect_id,
        )
        await notification_service.notify_module_event(
            user_id=user_id,
            category="assistant",
            level="success",
            title=f"🔥 {prospect_name} veut son assistant",
            body=f"{_MODULE_TAG_ASSISTANT} · Depuis la page démo — {summary}",
            url=f"{_PROSPECTS_URL}?open={prospect_id}" if prospect_id else _DASHBOARD_URL,
            tag=f"assistant-interest-{prospect_id}" if prospect_id else None,
        )

    @staticmethod
    def format_amount(amount_cents: int, currency: str) -> str:
        """
        Format a cents amount into a short human label (e.g. ``79 €``).

        Args:
            amount_cents: Amount in cents.
            currency: ISO currency code.

        Returns:
            The formatted amount with its currency symbol.
        """
        symbols = {"eur": "€", "usd": "$", "gbp": "£"}
        symbol = symbols.get(currency.lower(), currency.upper())
        amount = amount_cents / 100
        text = f"{amount:.0f}" if amount == int(amount) else f"{amount:.2f}"
        return f"{text} {symbol}"


receptionist_notifications = ReceptionistNotifications()
