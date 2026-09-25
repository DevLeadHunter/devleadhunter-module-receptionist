"""Client space routes: the magic-link page of a sold assistant (its link is issued from the owner routes)."""

import logging
from datetime import UTC, datetime

import stripe
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from api.v1.routes.ai_assistant_common import client_ip, confirmation_response, faq_response
from core.database import get_db
from enums.ai_assistant_request import AiAssistantRequestStatus, AiAssistantRequestType
from enums.assistant_subscription_status import AssistantSubscriptionStatus
from enums.assistant_widget_language import AssistantWidgetLanguage
from models.ai_assistant import AiAssistant
from models.ai_assistant_appointment import AiAssistantAppointment
from models.ai_assistant_report import AiAssistantReport
from models.ai_assistant_request import AiAssistantRequest
from models.ai_assistant_subscription import AiAssistantSubscription
from schemas.ai_assistant_client_space import (
    AiAssistantClientAppointmentItem,
    AiAssistantClientCalendar,
    AiAssistantClientCalendarConnect,
    AiAssistantClientCalendarUpdate,
    AiAssistantClientLanguageOption,
    AiAssistantClientPortalResponse,
    AiAssistantClientRenewResponse,
    AiAssistantClientReport,
    AiAssistantClientRequestItem,
    AiAssistantClientSettings,
    AiAssistantClientSettingsUpdate,
    AiAssistantClientSpaceResponse,
    AiAssistantClientSubscription,
)
from schemas.ai_assistant_faq import AiAssistantFaqEntryRequest, AiAssistantFaqResponse
from services.ai_assistant.appointment_slots import AiAssistantAppointmentSlots
from services.ai_assistant.assistant_service import ai_assistant_service
from services.ai_assistant.calendar_access import ai_assistant_calendar_access
from services.ai_assistant.calendar_booking import ai_assistant_calendar_booking
from services.ai_assistant.calendar_service import ai_assistant_calendar_service
from services.ai_assistant.calendar_settings import DURATION_CHOICES, MIN_NOTICE_CHOICES, CalendarSettings
from services.ai_assistant.client_links import AiAssistantClientLinks, ClientLinkToken
from services.ai_assistant.client_space_service import ClientSpaceAccessError, ai_assistant_client_space_service
from services.ai_assistant.faq_service import ai_assistant_faq_service
from services.ai_assistant.google_calendar_client import GoogleCalendarError
from services.ai_assistant.knowledge_builder import LANGUAGE_NAMES
from services.ai_assistant.opening_hours import OpeningHoursCalendar
from services.ai_assistant.report_email import AiAssistantReportEmail, MonthlyStats
from services.ai_assistant.report_service import ReportPeriod
from services.ai_assistant.request_alerts import AlertSettings
from services.ai_assistant.request_service import ai_assistant_request_service
from services.assistant_pricing_service import AssistantPricingService
from services.french_date_formatter import FrenchDateFormatter
from services.rate_limiter import (
    assistant_client_limiter,
    assistant_client_renew_daily_limiter,
    assistant_client_renew_limiter,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai-assistants", tags=["ai-assistant-client-space"])

_TOO_MANY = "Trop de requêtes, réessayez dans quelques minutes"


def _business_label(moment: datetime, pattern: str) -> str:
    """A stored UTC moment (naive or aware) as business-time text."""
    naive_utc = moment.astimezone(UTC).replace(tzinfo=None) if moment.tzinfo else moment
    return OpeningHoursCalendar.to_business_time(naive_utc).strftime(pattern)


def _open_client_space(
    db: Session, token: str, request: Request, *, allow_expired: bool = False
) -> tuple[AiAssistant, ClientLinkToken]:
    """The assistant a client-space link opens, or the HTTP error the page shows (rate-limited per visitor)."""
    if not assistant_client_limiter.allow(f"client:{client_ip(request)}"):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=_TOO_MANY)
    try:
        return ai_assistant_client_space_service.resolve(db, token, allow_expired=allow_expired)
    except ClientSpaceAccessError as exc:
        if exc.is_expired:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Ce lien a expiré : demandez un nouveau lien."
            ) from exc
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ce lien n'ouvre aucun espace.") from exc


def _to_request_item(record: AiAssistantRequest, booked: str | None = None) -> AiAssistantClientRequestItem:
    return AiAssistantClientRequestItem(
        id=record.id,
        type=AiAssistantRequestType(record.type),
        status=AiAssistantRequestStatus(record.status),
        name=record.name,
        contact=record.contact,
        summary=(record.need_summary or record.need or "").strip() or None,
        received_label=_business_label(record.created_at, "%d/%m à %H:%M"),
        received_outside_hours=record.received_outside_hours,
        photo_urls=ai_assistant_request_service.photo_urls(record),
        appointment_slots=AiAssistantAppointmentSlots.labels(record.appointment_slots_json),
        appointment_booked=booked,
    )


def _to_calendar(db: Session, assistant: AiAssistant) -> AiAssistantClientCalendar:
    state, calendar = ai_assistant_calendar_service.connection(db, assistant)
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


def _to_appointment(
    appointment: AiAssistantAppointment, record: AiAssistantRequest
) -> AiAssistantClientAppointmentItem:
    return AiAssistantClientAppointmentItem(
        id=appointment.id,
        start_label=ai_assistant_calendar_booking.start_label(appointment),
        type_label=appointment.type_label,
        name=record.name,
        contact=record.contact,
    )


def _to_report(report: AiAssistantReport) -> AiAssistantClientReport:
    stats = MonthlyStats.from_json(report.stats_json or {})
    return AiAssistantClientReport(
        month_label=FrenchDateFormatter.month_year(ReportPeriod.of_key(report.month).first_day),
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
    )


def _to_subscription(subscription: AiAssistantSubscription) -> AiAssistantClientSubscription:
    per = "/an" if subscription.interval == "year" else "/mois"
    return AiAssistantClientSubscription(
        status=AssistantSubscriptionStatus(subscription.status),
        price_label=f"{AssistantPricingService.format_price(subscription.amount_cents)}{per}",
        period_end_label=(
            _business_label(subscription.current_period_end, "%d/%m/%Y") if subscription.current_period_end else None
        ),
        cancel_scheduled=bool(subscription.cancel_at_period_end),
        can_manage=bool(subscription.stripe_customer_id),
    )


def _to_settings(assistant: AiAssistant) -> AiAssistantClientSettings:
    alerts = AlertSettings.of(assistant)
    offered = {language.value for language in AssistantWidgetLanguage}
    return AiAssistantClientSettings(
        assistant_name=assistant.assistant_name,
        languages=[AssistantWidgetLanguage(code) for code in (assistant.languages or []) if code in offered],
        alert_phone=alerts.phone_e164,
        alert_sms_enabled=alerts.sms_enabled,
        alert_email_enabled=alerts.email_enabled,
        alert_sms_types=[item for item in AiAssistantRequestType if item in alerts.sms_types],
        alert_quiet_start_hour=alerts.quiet_start_hour,
        alert_quiet_end_hour=alerts.quiet_end_hour,
    )


@router.get("/client/{token}", response_model=AiAssistantClientSpaceResponse)
async def get_client_space(
    token: str, request: Request, db: Session = Depends(get_db)
) -> AiAssistantClientSpaceResponse:
    """Everything the client-space page shows, for a valid link."""
    assistant, link = _open_client_space(db, token, request)
    report = ai_assistant_client_space_service.latest_report(db, assistant)
    subscription = ai_assistant_client_space_service.current_subscription(db, assistant)
    records = ai_assistant_client_space_service.recent_requests(db, assistant)
    booked = ai_assistant_calendar_booking.booked_labels(db, [record.id for record in records])
    faq = faq_response(assistant)
    return AiAssistantClientSpaceResponse(
        business_name=assistant.business_name,
        assistant_name=assistant.assistant_name,
        accent_color=ai_assistant_service.accent_color(assistant),
        link_expires_label=_business_label(link.expires_at, "%d/%m/%Y"),
        pending_count=ai_assistant_client_space_service.pending_count(db, assistant),
        requests=[_to_request_item(record, booked.get(record.id)) for record in records],
        report=_to_report(report) if report is not None else None,
        settings=_to_settings(assistant),
        language_options=[
            AiAssistantClientLanguageOption(code=language, label=LANGUAGE_NAMES.get(language.value, language.value))
            for language in AssistantWidgetLanguage
        ],
        subscription=_to_subscription(subscription) if subscription is not None else None,
        calendar=_to_calendar(db, assistant),
        appointments=[
            _to_appointment(appointment, record)
            for appointment, record in ai_assistant_calendar_booking.upcoming(db, assistant)
        ],
        faq=faq.faq,
        unanswered=faq.unanswered,
    )


@router.post("/client/{token}/faq", response_model=AiAssistantFaqResponse, status_code=status.HTTP_201_CREATED)
async def add_client_faq_entry(
    token: str, payload: AiAssistantFaqEntryRequest, request: Request, db: Session = Depends(get_db)
) -> AiAssistantFaqResponse:
    """The business answers a question itself: it joins the FAQ and leaves the unanswered list."""
    assistant, _link = _open_client_space(db, token, request)
    try:
        ai_assistant_faq_service.add_faq(db, assistant, payload.question, payload.answer)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return faq_response(assistant)


@router.delete("/client/{token}/unanswered/{index}", status_code=status.HTTP_204_NO_CONTENT)
async def dismiss_client_unanswered_question(
    token: str, index: int, request: Request, db: Session = Depends(get_db)
) -> Response:
    """Drop an unanswered question without answering it."""
    assistant, _link = _open_client_space(db, token, request)
    try:
        ai_assistant_faq_service.dismiss_unanswered(db, assistant, index)
    except IndexError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question introuvable") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/client/{token}/requests/{request_id}/handled", response_model=AiAssistantClientRequestItem)
async def mark_client_request_handled(
    token: str, request_id: int, request: Request, db: Session = Depends(get_db)
) -> AiAssistantClientRequestItem:
    """Mark one of the assistant's requests handled from the client space."""
    assistant, _link = _open_client_space(db, token, request)
    record = ai_assistant_client_space_service.mark_handled(db, assistant, request_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Demande introuvable")
    return _to_request_item(record, ai_assistant_calendar_booking.booked_labels(db, [record.id]).get(record.id))


@router.patch("/client/{token}/settings", response_model=AiAssistantClientSettings)
async def update_client_settings(
    token: str, payload: AiAssistantClientSettingsUpdate, request: Request, db: Session = Depends(get_db)
) -> AiAssistantClientSettings:
    """Change the assistant's first name, languages or alerts from the client space."""
    assistant, _link = _open_client_space(db, token, request)
    try:
        updated = await ai_assistant_client_space_service.update_settings(
            db, assistant, payload.model_dump(exclude_unset=True, mode="json")
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return _to_settings(updated)


@router.post("/client/{token}/billing-portal", response_model=AiAssistantClientPortalResponse)
async def open_client_billing_portal(
    token: str, request: Request, db: Session = Depends(get_db)
) -> AiAssistantClientPortalResponse:
    """A Stripe billing portal session for the client's subscription, returning to the client space."""
    assistant, _link = _open_client_space(db, token, request)
    try:
        url = await ai_assistant_client_space_service.billing_portal_url(
            db, assistant, return_url=AiAssistantClientLinks.page_url(token)
        )
    except (ValueError, stripe.error.StripeError) as exc:
        logger.warning("Billing portal of assistant %s unavailable", assistant.id, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="La gestion de l'abonnement est indisponible pour le moment.",
        ) from exc
    if url is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aucun abonnement à gérer")
    return AiAssistantClientPortalResponse(url=url)


@router.post(
    "/client/{token}/renew", response_model=AiAssistantClientRenewResponse, status_code=status.HTTP_202_ACCEPTED
)
async def renew_client_link(
    token: str, request: Request, db: Session = Depends(get_db)
) -> AiAssistantClientRenewResponse:
    """Email a fresh link to the business from an expired (but authentic) one; its address is never shown."""
    assistant, _link = _open_client_space(db, token, request, allow_expired=True)
    key = f"renew:{assistant.id}"
    if not assistant_client_renew_limiter.allow(key) or not assistant_client_renew_daily_limiter.allow(key):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=_TOO_MANY)
    delivery = await ai_assistant_client_space_service.issue_link(db, assistant, send=True)
    return AiAssistantClientRenewResponse(sent=delivery.sent_to is not None)


@router.post("/client/{token}/calendar/connect", response_model=AiAssistantClientCalendarConnect)
async def connect_client_calendar(
    token: str, request: Request, db: Session = Depends(get_db)
) -> AiAssistantClientCalendarConnect:
    """The Google consent page that connects the client's agenda (the page opens it in a new tab)."""
    assistant, _link = _open_client_space(db, token, request)
    try:
        url = ai_assistant_calendar_service.authorization_url(assistant)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return AiAssistantClientCalendarConnect(url=url)


@router.patch("/client/{token}/calendar", response_model=AiAssistantClientCalendar)
async def update_client_calendar(
    token: str, payload: AiAssistantClientCalendarUpdate, request: Request, db: Session = Depends(get_db)
) -> AiAssistantClientCalendar:
    """Change the booking settings: agenda, duration, minimum notice, kinds of appointment."""
    assistant, _link = _open_client_space(db, token, request)
    calendar = ai_assistant_calendar_access.calendar_of(db, assistant)
    if calendar is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aucun agenda connecté")
    try:
        await ai_assistant_calendar_service.update_settings(db, calendar, payload.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return _to_calendar(db, assistant)


@router.delete("/client/{token}/calendar", response_model=AiAssistantClientCalendar)
async def disconnect_client_calendar(
    token: str, request: Request, db: Session = Depends(get_db)
) -> AiAssistantClientCalendar:
    """Disconnect the agenda (its tokens are deleted); appointments go back to wished half-days."""
    assistant, _link = _open_client_space(db, token, request)
    ai_assistant_calendar_service.disconnect(db, assistant)
    return _to_calendar(db, assistant)


@router.get("/calendar/google/callback", response_class=HTMLResponse)
async def google_calendar_callback(
    request: Request,
    code: str = Query(default=""),
    state: str = Query(default=""),
    error: str = Query(default=""),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Where Google sends the client back: the agenda is stored, then a page to close (it carries no link)."""
    if not assistant_client_limiter.allow(f"client:{client_ip(request)}"):
        return confirmation_response(
            "Trop de tentatives", "Réessayez dans quelques minutes.", status_code=status.HTTP_429_TOO_MANY_REQUESTS
        )
    if error or not code:
        return confirmation_response(
            "Connexion annulée", "L'agenda n'est pas connecté. Fermez cet onglet et recommencez depuis votre espace."
        )
    try:
        assistant, calendar = await ai_assistant_calendar_service.connect(db, code=code, state=state)
    except ValueError as exc:
        return confirmation_response(
            "Connexion impossible", f"{exc}. Fermez cet onglet et recommencez depuis votre espace."
        )
    except GoogleCalendarError:
        logger.warning("Google refused an agenda consent code", exc_info=True)
        return confirmation_response(
            "Connexion impossible",
            "Google n'a pas confirmé la connexion. Fermez cet onglet et recommencez depuis votre espace.",
        )
    await ai_assistant_client_space_service.announce_calendar_connected(db, assistant, calendar.account_email)
    account = f" ({calendar.account_email})" if calendar.account_email else ""
    return confirmation_response(
        "Google Agenda est connecté",
        f"{assistant.assistant_name} réservera désormais les rendez-vous de {assistant.business_name} dans cet "
        f"agenda{account}. Vous pouvez fermer cet onglet et revenir à votre espace.",
    )
