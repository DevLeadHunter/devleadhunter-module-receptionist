"""
Client space routes: the magic-link page of a sold assistant (its link is issued from the owner routes), and the
read-only demo space a prospect opens from its demo page.
"""

import logging

import stripe
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from api.v1.routes.ai_assistant_common import client_ip, confirmation_response
from core.database import get_db
from models.ai_assistant import AiAssistant
from schemas.ai_assistant_client_space import (
    AiAssistantClientCalendar,
    AiAssistantClientCalendarConnect,
    AiAssistantClientCalendarUpdate,
    AiAssistantClientGoogleProfile,
    AiAssistantClientGoogleProfileUpdate,
    AiAssistantClientLimit,
    AiAssistantClientLimitsUpdate,
    AiAssistantClientMailbox,
    AiAssistantClientMailboxConnect,
    AiAssistantClientPortalResponse,
    AiAssistantClientRenewResponse,
    AiAssistantClientRequestItem,
    AiAssistantClientRequestOutcomeUpdate,
    AiAssistantClientSettings,
    AiAssistantClientSettingsUpdate,
    AiAssistantClientSpaceResponse,
    AiAssistantClientTestSms,
)
from schemas.ai_assistant_demo_space import AiAssistantDemoSpaceRequest, AiAssistantDemoSpaceResponse
from schemas.ai_assistant_faq import AiAssistantFaqEntryRequest, AiAssistantFaqResponse
from services.ai_assistant.assistant_service import ai_assistant_service
from services.ai_assistant.calendar_access import ai_assistant_calendar_access
from services.ai_assistant.calendar_booking import ai_assistant_calendar_booking
from services.ai_assistant.calendar_service import ai_assistant_calendar_service
from services.ai_assistant.client_links import AiAssistantClientLinks, ClientLinkToken
from services.ai_assistant.client_space_example import EXAMPLE_TOKEN, ai_assistant_client_space_example
from services.ai_assistant.client_space_payload import ai_assistant_client_space_payload
from services.ai_assistant.client_space_service import ClientSpaceAccessError, ai_assistant_client_space_service
from services.ai_assistant.demo_space_service import ai_assistant_demo_space_service
from services.ai_assistant.embed_snippet import AiAssistantEmbedSnippet
from services.ai_assistant.faq_service import ai_assistant_faq_service
from services.ai_assistant.gmail_client import GmailError
from services.ai_assistant.google_calendar_client import GoogleCalendarError
from services.ai_assistant.limits import AiAssistantLimits
from services.ai_assistant.mailbox_service import ai_assistant_mailbox_service
from services.ai_assistant.request_alerts import ai_assistant_request_alerts
from services.rate_limiter import (
    assistant_client_limiter,
    assistant_client_renew_daily_limiter,
    assistant_client_renew_limiter,
    assistant_client_test_sms_limiter,
    assistant_demo_space_limiter,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai-assistants", tags=["ai-assistant-client-space"])

_TOO_MANY = "Trop de requêtes, réessayez dans quelques minutes"


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


@router.get("/client/{token}", response_model=AiAssistantClientSpaceResponse)
async def get_client_space(
    token: str, request: Request, db: Session = Depends(get_db)
) -> AiAssistantClientSpaceResponse:
    """Everything the client-space page shows, for a valid link; the example space under its reserved token."""
    if token == EXAMPLE_TOKEN:
        return ai_assistant_client_space_example.build()
    assistant, link = _open_client_space(db, token, request)
    # Each visit carries a fresh 30-day link the page moves to: a link opened monthly never expires.
    fresh_token = AiAssistantClientLinks.token(assistant)
    fresh_link = AiAssistantClientLinks.read(fresh_token, assistant) or link
    report = ai_assistant_client_space_service.latest_report(db, assistant)
    subscription = ai_assistant_client_space_service.current_subscription(db, assistant)
    records = ai_assistant_client_space_service.recent_requests(db, assistant)
    booked = ai_assistant_calendar_booking.booked_labels(db, [record.id for record in records])
    faq = ai_assistant_faq_service.faq_and_unanswered(assistant)
    return AiAssistantClientSpaceResponse(
        business_name=assistant.business_name,
        assistant_name=assistant.assistant_name,
        accent_color=ai_assistant_service.accent_color(assistant),
        link_expires_label=ai_assistant_client_space_payload.business_label(fresh_link.expires_at, "%d/%m/%Y"),
        pending_count=ai_assistant_client_space_service.pending_count(db, assistant),
        requests=[ai_assistant_client_space_payload.request_item(record, booked.get(record.id)) for record in records],
        report=(
            ai_assistant_client_space_payload.report(report, assistant.assistant_name) if report is not None else None
        ),
        settings=ai_assistant_client_space_payload.settings(assistant),
        language_options=ai_assistant_client_space_payload.language_options(),
        subscription=ai_assistant_client_space_payload.subscription(subscription) if subscription is not None else None,
        calendar=ai_assistant_client_space_payload.calendar(db, assistant),
        appointments=[
            ai_assistant_client_space_payload.appointment(appointment, record)
            for appointment, record in ai_assistant_calendar_booking.upcoming(db, assistant)
        ],
        mailbox=ai_assistant_client_space_payload.mailbox(db, assistant),
        faq=faq.faq,
        unanswered=faq.unanswered,
        fresh_token=fresh_token,
        website_url=ai_assistant_client_space_service.website_url(db, assistant),
        embed_snippet=AiAssistantEmbedSnippet.render(assistant.slug),
        google_profile=ai_assistant_client_space_payload.google_profile(assistant),
        installed=ai_assistant_client_space_payload.installed(assistant),
        limits=ai_assistant_client_space_payload.limits(AiAssistantLimits.effective(assistant)),
    )


@router.post("/public/{slug}/space", response_model=AiAssistantDemoSpaceResponse)
async def read_demo_space(
    slug: str, payload: AiAssistantDemoSpaceRequest, request: Request, db: Session = Depends(get_db)
) -> AiAssistantDemoSpaceResponse:
    """
    The space a prospect opens from its demo page: its own receptionist as the client space shows it once sold, with
    the requests left from the visitor's widget sessions only (examples of the trade below two of them).

    A POST so the session ids stay out of addresses and server logs; it saves, counts and announces nothing. A sold,
    expired or deleted receptionist has none (404).
    """
    if not assistant_demo_space_limiter.allow(f"demo-space:{client_ip(request)}"):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=_TOO_MANY)
    assistant = ai_assistant_demo_space_service.open_demo(db, slug)
    if assistant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aucun espace de démonstration ici.")
    return ai_assistant_demo_space_service.build(db, assistant, payload.session_ids)


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
    return ai_assistant_faq_service.faq_and_unanswered(assistant)


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
    return ai_assistant_client_space_payload.request_item(
        record, ai_assistant_calendar_booking.booked_labels(db, [record.id]).get(record.id)
    )


@router.post("/client/{token}/requests/{request_id}/dropped", response_model=AiAssistantClientRequestItem)
async def mark_client_request_dropped(
    token: str, request_id: int, request: Request, db: Session = Depends(get_db)
) -> AiAssistantClientRequestItem:
    """Set one of the assistant's requests aside (a test, spam, a duplicate) from the client space."""
    assistant, _link = _open_client_space(db, token, request)
    record = ai_assistant_client_space_service.mark_dropped(db, assistant, request_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Demande introuvable")
    return ai_assistant_client_space_payload.request_item(
        record, ai_assistant_calendar_booking.booked_labels(db, [record.id]).get(record.id)
    )


@router.post("/client/{token}/requests/{request_id}/outcome", response_model=AiAssistantClientRequestItem)
async def set_client_request_outcome(
    token: str,
    request_id: int,
    payload: AiAssistantClientRequestOutcomeUpdate,
    request: Request,
    db: Session = Depends(get_db),
) -> AiAssistantClientRequestItem:
    """What became of a request the business called back: a client won, lost, or cleared (nothing set aside)."""
    assistant, _link = _open_client_space(db, token, request)
    record = ai_assistant_client_space_service.set_outcome(db, assistant, request_id, payload.outcome)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Demande introuvable")
    return ai_assistant_client_space_payload.request_item(
        record, ai_assistant_calendar_booking.booked_labels(db, [record.id]).get(record.id)
    )


@router.post("/client/{token}/alerts/test-sms", response_model=AiAssistantClientTestSms)
async def send_client_test_sms(token: str, request: Request, db: Session = Depends(get_db)) -> AiAssistantClientTestSms:
    """Text the client's alert mobile once, so they see their alerts arrive (two tests an hour at most)."""
    assistant, _link = _open_client_space(db, token, request)
    if not assistant.alert_phone_e164:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Ajoutez d'abord votre mobile, puis enregistrez."
        )
    if not assistant_client_test_sms_limiter.allow(f"test-sms:{assistant.id}"):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Deux SMS de test par heure au plus : réessayez plus tard.",
        )
    sent = await ai_assistant_request_alerts.send_test_sms(db, assistant)
    return AiAssistantClientTestSms(
        sent=sent,
        to_label=assistant.alert_phone_e164,
        reason=None if sent else "Envoi impossible pour le moment : l'expéditeur SMS n'a pas pris le message.",
    )


@router.patch("/client/{token}/limits", response_model=list[AiAssistantClientLimit])
async def update_client_limits(
    token: str, payload: AiAssistantClientLimitsUpdate, request: Request, db: Session = Depends(get_db)
) -> list[AiAssistantClientLimit]:
    """The business edits what its receptionist says on prices, delays, warranties… or switches a subject off."""
    assistant, _link = _open_client_space(db, token, request)
    limits = ai_assistant_client_space_service.set_limits(db, assistant, [item.model_dump() for item in payload.limits])
    return ai_assistant_client_space_payload.limits(limits)


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
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    return ai_assistant_client_space_payload.settings(updated)


@router.post("/client/{token}/google-profile", response_model=AiAssistantClientGoogleProfile)
async def update_client_google_profile(
    token: str, payload: AiAssistantClientGoogleProfileUpdate, request: Request, db: Session = Depends(get_db)
) -> AiAssistantClientGoogleProfile:
    """The business says whether the receptionist's address is on its Google profile (a « Pour démarrer » step)."""
    assistant, _link = _open_client_space(db, token, request)
    ai_assistant_client_space_service.set_google_profile_linked(db, assistant, payload.linked)
    return ai_assistant_client_space_payload.google_profile(assistant)


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
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    return ai_assistant_client_space_payload.calendar(db, assistant)


@router.delete("/client/{token}/calendar", response_model=AiAssistantClientCalendar)
async def disconnect_client_calendar(
    token: str, request: Request, db: Session = Depends(get_db)
) -> AiAssistantClientCalendar:
    """Disconnect the agenda (its tokens are deleted); appointments go back to wished half-days."""
    assistant, _link = _open_client_space(db, token, request)
    ai_assistant_calendar_service.disconnect(db, assistant)
    return ai_assistant_client_space_payload.calendar(db, assistant)


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


def _enabled_mailbox_assistant(db: Session, token: str, request: Request) -> AiAssistant:
    """The assistant a client-space link opens, when its mailbox is switched on (404 otherwise)."""
    assistant, _link = _open_client_space(db, token, request)
    if not assistant.mailbox_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Boîte mail non activée")
    return assistant


@router.post("/client/{token}/mailbox/connect", response_model=AiAssistantClientMailboxConnect)
async def connect_client_mailbox(
    token: str, request: Request, db: Session = Depends(get_db)
) -> AiAssistantClientMailboxConnect:
    """The Google consent page that connects the client's Gmail (the page opens it in a new tab)."""
    assistant = _enabled_mailbox_assistant(db, token, request)
    try:
        url = ai_assistant_mailbox_service.authorization_url(assistant)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return AiAssistantClientMailboxConnect(url=url)


@router.delete("/client/{token}/mailbox", response_model=AiAssistantClientMailbox)
async def disconnect_client_mailbox(
    token: str, request: Request, db: Session = Depends(get_db)
) -> AiAssistantClientMailbox:
    """Disconnect the client's Gmail: its tokens are deleted and its access revoked at Google."""
    assistant = _enabled_mailbox_assistant(db, token, request)
    await ai_assistant_mailbox_service.disconnect(db, assistant)
    mailbox = ai_assistant_client_space_payload.mailbox(db, assistant)
    if mailbox is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Gmail n'est plus configuré")
    return mailbox


@router.get("/mailbox/google/callback", response_class=HTMLResponse)
async def google_mailbox_callback(
    request: Request,
    code: str = Query(default=""),
    state: str = Query(default=""),
    error: str = Query(default=""),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Where Google sends the client back: the mailbox is stored, then a page to close (it carries no link)."""
    if not assistant_client_limiter.allow(f"client:{client_ip(request)}"):
        return confirmation_response(
            "Trop de tentatives", "Réessayez dans quelques minutes.", status_code=status.HTTP_429_TOO_MANY_REQUESTS
        )
    if error or not code:
        return confirmation_response(
            "Connexion annulée", "Gmail n'est pas connecté. Fermez cet onglet et recommencez depuis votre espace."
        )
    try:
        assistant, mailbox = await ai_assistant_mailbox_service.connect(db, code=code, state=state)
    except ValueError as exc:
        return confirmation_response(
            "Connexion impossible", f"{exc}. Fermez cet onglet et recommencez depuis votre espace."
        )
    except GmailError:
        logger.warning("Google refused a mailbox consent code", exc_info=True)
        return confirmation_response(
            "Connexion impossible",
            "Google n'a pas confirmé la connexion. Fermez cet onglet et recommencez depuis votre espace.",
        )
    await ai_assistant_client_space_service.announce_mailbox_connected(db, assistant, mailbox.account_email)
    return confirmation_response(
        "Gmail est connecté",
        f"{assistant.assistant_name} prépare désormais une réponse à chaque email d'un client de "
        f"{assistant.business_name} ({mailbox.account_email}) : elle vous attend dans vos brouillons Gmail, vous la "
        "relisez et l'envoyez. Vous pouvez fermer cet onglet et revenir à votre espace.",
    )
