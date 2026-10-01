"""
The sections of a client space as its page reads them, built from the receptionist's rows: its requests, the agenda,
the Gmail mailbox, the appointments, the monthly report, the subscription, the Google profile address, the imposed
answers, the installed widget and the settings.

The page's read and each of its actions (which answer with the section they changed) build them here, so a section
always reads the same.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import ClassVar

from sqlalchemy.orm import Session

from enums.ai_assistant_calendar_status import AiAssistantCalendarConnection
from enums.ai_assistant_mailbox import AiAssistantMailboxConnection
from enums.ai_assistant_request import (
    AiAssistantRequestChannel,
    AiAssistantRequestOutcome,
    AiAssistantRequestStatus,
    AiAssistantRequestType,
)
from enums.ai_assistant_subscription_status import AiAssistantSubscriptionStatus
from enums.ai_assistant_widget_language import AiAssistantWidgetLanguage
from models.ai_assistant import AiAssistant
from models.ai_assistant_appointment import AiAssistantAppointment
from models.ai_assistant_calendar import AiAssistantCalendar
from models.ai_assistant_report import AiAssistantReport
from models.ai_assistant_request import AiAssistantRequest
from models.ai_assistant_subscription import AiAssistantSubscription
from schemas.ai_assistant_client_space import (
    AiAssistantClientAppointmentItem,
    AiAssistantClientCalendar,
    AiAssistantClientEvent,
    AiAssistantClientGoogleProfile,
    AiAssistantClientInstalled,
    AiAssistantClientLanguageOption,
    AiAssistantClientLimit,
    AiAssistantClientMailbox,
    AiAssistantClientReport,
    AiAssistantClientRequestItem,
    AiAssistantClientSettings,
    AiAssistantClientSubscription,
)
from services.ai_assistant.alert_settings import AlertSettings
from services.ai_assistant.appointment_slots import AiAssistantAppointmentSlots
from services.ai_assistant.assistant_service import ai_assistant_service
from services.ai_assistant.calendar_booking import ai_assistant_calendar_booking
from services.ai_assistant.calendar_service import ai_assistant_calendar_service
from services.ai_assistant.calendar_settings import DURATION_CHOICES, MIN_NOTICE_CHOICES, CalendarSettings
from services.ai_assistant.client_space_service import ai_assistant_client_space_service
from services.ai_assistant.gmail_client import GmailClient
from services.ai_assistant.knowledge_builder import LANGUAGE_NAMES
from services.ai_assistant.limits import AssistantLimit
from services.ai_assistant.mailbox_access import ai_assistant_mailbox_access
from services.ai_assistant.mailbox_service import MailboxView, ai_assistant_mailbox_service
from services.ai_assistant.opening_hours import OpeningHoursCalendar
from services.ai_assistant.report_email import AiAssistantReportEmail, MonthlyStats
from services.ai_assistant.report_service import ReportPeriod
from services.ai_assistant.request_analyzer import AiAssistantRequestAnalyzer
from services.ai_assistant.request_attachments import AiAssistantRequestAttachments
from services.assistant_pricing_service import AssistantPricingService
from services.french_date_formatter import FrenchDateFormatter


class AiAssistantClientSpacePayload:
    """Builds each section of a client space from the receptionist's rows."""

    # Mailbox states whose section stays hidden: switched off by the operator, or Gmail not configured on the server.
    _HIDDEN_MAILBOX_CONNECTIONS: ClassVar[frozenset[AiAssistantMailboxConnection]] = frozenset(
        {AiAssistantMailboxConnection.DISABLED, AiAssistantMailboxConnection.UNAVAILABLE}
    )

    @staticmethod
    def business_label(moment: datetime, pattern: str) -> str:
        """
        A stored moment as business-time text.

        Args:
            moment: A UTC moment, naive as the database stores it or aware.
            pattern: The ``strftime`` pattern of the text.

        Returns:
            The moment in Paris time, formatted.
        """
        naive_utc = moment.astimezone(UTC).replace(tzinfo=None) if moment.tzinfo else moment
        return OpeningHoursCalendar.to_business_time(naive_utc).strftime(pattern)

    def request_item(self, record: AiAssistantRequest, booked: str | None = None) -> AiAssistantClientRequestItem:
        """
        One request as its client sees it.

        Args:
            record: The request.
            booked: The appointment booked for it in the agenda (« mar. 29/09 à 14:30 (Révision) »), if any.

        Returns:
            The request, its dates in business time.
        """
        return AiAssistantClientRequestItem(
            id=record.id,
            type=AiAssistantRequestType(record.type),
            status=AiAssistantRequestStatus(record.status),
            channel=AiAssistantRequestChannel(record.channel),
            name=record.name,
            contact=record.contact,
            summary=(record.need_summary or record.need or "").strip() or None,
            received_label=self.business_label(record.created_at, "%d/%m à %H:%M"),
            received_day=self.business_label(record.created_at, "%Y-%m-%d"),
            received_time=self.business_label(record.created_at, "%H:%M"),
            received_outside_hours=record.received_outside_hours,
            photo_urls=AiAssistantRequestAttachments.photo_urls(record),
            appointment_slots=AiAssistantAppointmentSlots.labels(record.appointment_slots_json),
            appointment_booked=booked,
            outcome=AiAssistantRequestOutcome(record.outcome) if record.outcome else None,
            event=self.event(record.event_json),
        )

    @staticmethod
    def event(event_json: object) -> AiAssistantClientEvent | None:
        """
        What an event request said of the event.

        Args:
            event_json: The request's ``event_json``, as the analyzer stored it.

        Returns:
            The event, or None when nothing of it is known.
        """
        if not isinstance(event_json, dict):
            return None
        guests = event_json.get("guests")
        event = AiAssistantClientEvent(
            date=AiAssistantRequestAnalyzer.date_text(event_json.get("date")),
            place=str(event_json.get("place")) if event_json.get("place") else None,
            guests=int(guests) if isinstance(guests, int) and not isinstance(guests, bool) else None,
            budget=str(event_json.get("budget")) if event_json.get("budget") else None,
        )
        return event if any((event.date, event.place, event.guests, event.budget)) else None

    def calendar(self, db: Session, assistant: AiAssistant) -> AiAssistantClientCalendar:
        """
        The agenda section: its connection and the booking settings, defaults applied.

        Args:
            db: Active database session.
            assistant: The receptionist.

        Returns:
            The section, with the choices the page offers.
        """
        state, calendar = ai_assistant_calendar_service.connection(db, assistant)
        return self._calendar_section(state, calendar)

    def calendar_before_connection(self) -> AiAssistantClientCalendar:
        """
        The agenda section of a receptionist whose business has not connected an agenda yet.

        Returns:
            The section to connect (unavailable while Google Calendar is not configured on the server), defaults
            applied.
        """
        return self._calendar_section(ai_assistant_calendar_service.state_before_connection(), None)

    @staticmethod
    def _calendar_section(
        state: AiAssistantCalendarConnection, calendar: AiAssistantCalendar | None
    ) -> AiAssistantClientCalendar:
        """The agenda section of a connection state and of the agenda row, if any."""
        booking = CalendarSettings.of(calendar) if calendar is not None else CalendarSettings.defaults()
        return AiAssistantClientCalendar(
            status=state,
            account_email=calendar.account_email if calendar is not None else None,
            calendar_id=booking.calendar_id,
            duration_minutes=booking.duration_minutes,
            min_notice_hours=booking.min_notice_hours,
            appointment_types=list(booking.appointment_types),
            last_error=calendar.last_error if calendar is not None else None,
            duration_choices=list(DURATION_CHOICES),
            min_notice_choices=list(MIN_NOTICE_CHOICES),
        )

    def mailbox(self, db: Session, assistant: AiAssistant) -> AiAssistantClientMailbox | None:
        """
        The Gmail section, only once the operator switched the mailbox on and Gmail is configured on the server.

        Args:
            db: Active database session.
            assistant: The receptionist.

        Returns:
            The section, or None while it stays hidden.
        """
        mailbox = ai_assistant_mailbox_access.mailbox_of(db, assistant)
        view = ai_assistant_mailbox_service.view(assistant, mailbox)
        if view.connection in self._HIDDEN_MAILBOX_CONNECTIONS:
            return None
        return self._mailbox_section(view, ai_assistant_mailbox_service.drafts_this_month(db, assistant))

    def mailbox_before_connection(self, assistant: AiAssistant) -> AiAssistantClientMailbox | None:
        """
        The Gmail section of a receptionist whose business has not connected its mailbox yet.

        Args:
            assistant: The receptionist.

        Returns:
            The section to connect, or None while the operator has not switched the mailbox on (or Gmail is not
            configured on the server).
        """
        view = ai_assistant_mailbox_service.view(assistant, None)
        if view.connection in self._HIDDEN_MAILBOX_CONNECTIONS:
            return None
        return self._mailbox_section(view, drafts_this_month=0)

    @staticmethod
    def _mailbox_section(view: MailboxView, drafts_this_month: int) -> AiAssistantClientMailbox:
        """The Gmail section of a mailbox view and of the reply drafts prepared since the first of the month."""
        return AiAssistantClientMailbox(
            status=view.connection,
            account_email=view.account_email,
            drafts_this_month=drafts_this_month,
            last_error=view.last_error,
            has_reached_daily_cap=view.has_reached_daily_cap,
            drafts_url=GmailClient.drafts_url(view.account_email),
        )

    @staticmethod
    def appointment(
        appointment: AiAssistantAppointment, record: AiAssistantRequest
    ) -> AiAssistantClientAppointmentItem:
        """
        An upcoming appointment the receptionist booked.

        Args:
            appointment: The appointment.
            record: The request it was booked for.

        Returns:
            The appointment, its start in business time.
        """
        return AiAssistantClientAppointmentItem(
            id=appointment.id,
            start_label=ai_assistant_calendar_booking.start_label(appointment),
            type_label=appointment.type_label,
            name=record.name,
            contact=record.contact,
        )

    def report(self, report: AiAssistantReport, assistant_name: str) -> AiAssistantClientReport:
        """
        A monthly report with the sentences of its email.

        Args:
            report: The report row (its ``stats_json`` holds the figures).
            assistant_name: The receptionist's first name, for the clients-won sentence.

        Returns:
            The report.
        """
        return self.report_of_figures(
            MonthlyStats.from_json(report.stats_json or {}), ReportPeriod.of_key(report.month).first_day, assistant_name
        )

    @staticmethod
    def report_of_figures(stats: MonthlyStats, month: date, assistant_name: str) -> AiAssistantClientReport:
        """
        A month's figures as its report reads them, with the sentences of the report email.

        Args:
            stats: The month's figures.
            month: Any day of the month.
            assistant_name: The receptionist's first name, for the clients-won sentence.

        Returns:
            The report.
        """
        return AiAssistantClientReport(
            month_label=FrenchDateFormatter.month_year(month),
            conversations=stats.conversations,
            requests=stats.requests,
            quotes=stats.quotes,
            appointments=stats.appointments,
            urgent=stats.urgent,
            photo_requests=stats.photo_requests,
            outside_hours_pct=stats.outside_hours_pct,
            languages_line=AiAssistantReportEmail.language_line(stats.languages),
            handling_line=AiAssistantReportEmail.handling_line(stats),
            top_questions=list(stats.top_questions),
            won=stats.won,
            won_line=AiAssistantReportEmail.won_line(stats, assistant_name),
            email_requests=stats.email_requests,
        )

    def subscription(self, subscription: AiAssistantSubscription) -> AiAssistantClientSubscription:
        """
        The client's subscription, read from its local copy.

        Args:
            subscription: The subscription row.

        Returns:
            The subscription, its price as locked at subscription.
        """
        per = "/an" if subscription.interval == "year" else "/mois"
        return AiAssistantClientSubscription(
            status=AiAssistantSubscriptionStatus(subscription.status),
            price_label=f"{AssistantPricingService.format_price(subscription.amount_cents)}{per}",
            period_end_label=(
                self.business_label(subscription.current_period_end, "%d/%m/%Y")
                if subscription.current_period_end
                else None
            ),
            cancel_scheduled=bool(subscription.cancel_at_period_end),
            can_manage=bool(subscription.stripe_customer_id),
        )

    def google_profile(self, assistant: AiAssistant) -> AiAssistantClientGoogleProfile:
        """
        The receptionist's address, ready for the business's Google profile, its voicemail and its printed matter.

        Args:
            assistant: The receptionist.

        Returns:
            The address, its QR code, the voicemail greeting and whether the business said it is on its profile.
        """
        url = ai_assistant_service.page_url(assistant.slug)
        linked_at = assistant.google_profile_linked_at
        return AiAssistantClientGoogleProfile(
            page_url=url,
            short_link=ai_assistant_client_space_service.page_short_link(assistant),
            qr_svg=ai_assistant_client_space_service.qr_svg(url),
            voicemail_text=ai_assistant_client_space_service.voicemail_text(assistant),
            linked_at_label=self.business_label(linked_at, "%d/%m/%Y") if linked_at is not None else None,
            is_linked=linked_at is not None,
        )

    @staticmethod
    def limits(limits: list[AssistantLimit]) -> list[AiAssistantClientLimit]:
        """
        The imposed answers as the page edits them.

        Args:
            limits: The receptionist's effective limits.

        Returns:
            One entry per sensitive subject, in their order.
        """
        return [
            AiAssistantClientLimit(key=limit.key, topic=limit.topic, answer=limit.answer, enabled=limit.enabled)
            for limit in limits
        ]

    def installed(self, assistant: AiAssistant) -> AiAssistantClientInstalled | None:
        """
        Where the widget's loader was last seen on the business's own website.

        Args:
            assistant: The receptionist.

        Returns:
            The host and the last sighting, or None until the line is pasted on a site.
        """
        if assistant.installed_at is None or not assistant.installed_host:
            return None
        return AiAssistantClientInstalled(
            host=assistant.installed_host, seen_label=self.business_label(assistant.installed_at, "%d/%m à %H:%M")
        )

    @staticmethod
    def settings(assistant: AiAssistant) -> AiAssistantClientSettings:
        """
        The settings a client may change, defaults applied.

        Args:
            assistant: The receptionist.

        Returns:
            Its first name, the languages the space offers, the alert mobile and channels.
        """
        alerts = AlertSettings.of(assistant)
        offered = {language.value for language in AiAssistantWidgetLanguage}
        return AiAssistantClientSettings(
            assistant_name=assistant.assistant_name,
            languages=[AiAssistantWidgetLanguage(code) for code in (assistant.languages or []) if code in offered],
            alert_phone=alerts.phone_e164,
            alert_sms_enabled=alerts.sms_enabled,
            alert_email_enabled=alerts.email_enabled,
            alert_sms_types=[item for item in AiAssistantRequestType if item in alerts.sms_types],
            alert_quiet_start_hour=alerts.quiet_start_hour,
            alert_quiet_end_hour=alerts.quiet_end_hour,
        )

    @staticmethod
    def language_options() -> list[AiAssistantClientLanguageOption]:
        """
        The languages the widget can speak, with their French names.

        Returns:
            Every widget language, in the enum's order.
        """
        return [
            AiAssistantClientLanguageOption(code=language, label=LANGUAGE_NAMES.get(language.value, language.value))
            for language in AiAssistantWidgetLanguage
        ]


ai_assistant_client_space_payload = AiAssistantClientSpacePayload()
