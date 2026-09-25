"""Public routes of an assistant's widget, by slug: its config, the chat (whole or streamed), the appointment offer,
the visitor's request, the photo for a quote, and the owner's « me contacter » on the demo page.
"""

import json
import logging
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile as StarletteUploadFile

from api.v1.routes.ai_assistant_common import (
    client_ip,
    public_assistant_or_404,
    require_declared_length,
)
from core.config import settings
from core.database import SessionLocal, get_db
from enums.ai_assistant_photo import AiAssistantPhotoRejection
from enums.ai_assistant_status import AiAssistantStatus
from enums.assistant_visitor_channel import AssistantVisitorChannel
from models.ai_assistant import AiAssistant
from models.prospect_db import ProspectDB
from schemas.ai_assistant import (
    BOOKABLE_YEAR_MAX,
    BOOKABLE_YEAR_MIN,
    AiAssistantAppointmentDay,
    AiAssistantAppointmentSlotsResponse,
    AiAssistantAppointmentTime,
    AiAssistantChatRequest,
    AiAssistantChatResponse,
    AiAssistantClosedHours,
    AiAssistantInterestRequest,
    AiAssistantLeadRequest,
    AiAssistantLeadResponse,
    AiAssistantPhotoResponse,
    AiAssistantPublicResponse,
)
from services.ai_assistant.appointment_notices import ai_assistant_appointment_notices
from services.ai_assistant.appointment_slots import (
    AiAssistantAppointmentSlots,
    AppointmentRefused,
    AppointmentSlot,
    SlotNoLongerOffered,
)
from services.ai_assistant.assistant_service import ai_assistant_service
from services.ai_assistant.calendar_booking import SlotTakenError, ai_assistant_calendar_booking
from services.ai_assistant.calendar_service import ai_assistant_calendar_service
from services.ai_assistant.chat_service import ChatAnswer, ai_assistant_chat_service
from services.ai_assistant.config_builder import ai_assistant_config_builder
from services.ai_assistant.conversation_service import ai_assistant_conversation_service
from services.ai_assistant.faq_service import ai_assistant_faq_service
from services.ai_assistant.opening_hours import OpeningHoursCalendar
from services.ai_assistant.photo_service import (
    MAX_PHOTO_BYTES,
    MAX_PHOTOS_PER_SESSION,
    PhotoRejectedError,
    ai_assistant_photo_service,
)
from services.ai_assistant.request_service import ai_assistant_request_service
from services.ai_assistant.request_volume import AiAssistantRequestVolume
from services.assistant_pricing_service import AssistantPricingService
from services.assistant_video_service import (
    has_ready_video,
    public_thumbnail_url,
    public_video_file_url,
)
from services.notification_service import notification_service
from services.r2_storage_service import r2_storage
from services.rate_limiter import (
    assistant_chat_limiter,
    assistant_lead_limiter,
    assistant_photo_limiter,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai-assistants", tags=["ai-assistant-widget"])


# Cap the history a public caller may submit, before the chat service bounds it further.
_MAX_INCOMING_MESSAGES = 40


# Shown to a visitor for a refusal whose reason is not written for them.
_INVALID_REQUEST = "Demande invalide : vérifiez vos informations et réessayez."
# Shown to the operator when a « ?internal=1 » visit tries to book in a client's agenda.
_TEST_BOOKING_REFUSED = (
    "Visite de test : aucun rendez-vous n'est réservé dans l'agenda. "
    "Pour tester une réservation, ouvrez votre assistant de test sans ?internal=1."
)


def _listing_public_fields(db: Session, assistant: AiAssistant) -> dict[str, str | float | int | None]:
    """The business as its Google listing shows it (city, trade, rating), for the demo page's scene."""
    city = assistant.city
    trade_label: str | None = None
    rating: float | None = None
    reviews_count: int | None = None
    if assistant.prospect_id is not None:
        prospect = db.get(ProspectDB, assistant.prospect_id)
        if prospect is not None:
            city = city or prospect.city
            trade_label = prospect.category or None
            rating = prospect.google_rating
            reviews_count = prospect.google_reviews_count
    return {
        "city": city or None,
        "trade_label": trade_label,
        "google_rating": rating,
        "google_reviews_count": reviews_count,
    }


def _owner_public_fields(assistant: AiAssistant) -> dict[str, str | None]:
    """Owner contact shown in the « me contacter » banner of a demo only: a sold widget never carries it."""
    user = assistant.user
    if user is None or assistant.status != AiAssistantStatus.ACTIVE.value:
        return {}
    fields: dict[str, str | None] = {
        "owner_name": user.name,
        "owner_contact_phone": user.contact_phone,
        "owner_contact_email": user.contact_email,
    }
    if user.profile_photo_path and (settings.r2_public_base_url or "").strip():
        fields["owner_profile_photo_url"] = r2_storage.public_url(user.profile_photo_path)
    return fields


@router.get("/public/{slug}", response_model=AiAssistantPublicResponse)
async def get_public_assistant(slug: str, db: Session = Depends(get_db)) -> AiAssistantPublicResponse:
    """Public config consumed by the embedded chat widget."""
    assistant = public_assistant_or_404(db, slug)
    video_ready = has_ready_video(assistant)
    return AiAssistantPublicResponse(
        slug=assistant.slug,
        business_name=assistant.business_name,
        assistant_name=assistant.assistant_name,
        assistant_gender=ai_assistant_config_builder.resolve_persona_gender(assistant.assistant_name).value,
        languages=assistant.languages or [],
        accent_color=ai_assistant_service.accent_color(assistant),
        status=assistant.status,
        **_listing_public_fields(db, assistant),
        **_owner_public_fields(assistant),
        video_available=video_ready,
        video_url=public_video_file_url(assistant.slug) if video_ready else None,
        video_thumbnail_url=public_thumbnail_url(assistant.slug, assistant.video_generated_at) if video_ready else None,
        monthly_price_label=(
            AssistantPricingService.format_price(AssistantPricingService.monthly_price_cents(db, assistant.user_id))
            if assistant.status == AiAssistantStatus.ACTIVE.value
            else None
        ),
        closed_hours=_closed_hours(db, assistant) if assistant.status == AiAssistantStatus.ACTIVE.value else None,
    )


def _closed_hours(db: Session, assistant: AiAssistant) -> AiAssistantClosedHours | None:
    """The demo page's estimate of the requests that come in while the business is closed (see the service)."""
    now = OpeningHoursCalendar.business_now()
    offer = AiAssistantRequestVolume.closed_hours_offer(
        AiAssistantAppointmentSlots.opening_hours_of(assistant),
        ai_assistant_service.business_category(db, assistant),
        year=now.year,
        month=now.month,
    )
    if offer is None:
        return None
    return AiAssistantClosedHours(
        open_hours_per_week=offer.closed_hours.open_hours_per_week,
        closed_share_pct=offer.closed_hours.closed_share_pct,
        closed_hours_in_month=offer.closed_hours.closed_hours_in_month,
        month=offer.month,
        trade_label=offer.trade.label,
        monthly_requests=offer.trade.monthly_requests,
        estimated_requests=offer.estimated_requests,
    )


def _open_chat(
    slug: str, payload: AiAssistantChatRequest, request: Request, db: Session
) -> tuple[AiAssistant, list[dict[str, str]]]:
    """The assistant a chat request reaches and the conversation to answer, once the request is admissible."""
    if not assistant_chat_limiter.allow(f"{slug}:{client_ip(request)}"):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Trop de messages, réessayez plus tard"
        )
    assistant = public_assistant_or_404(db, slug)
    # Only a visitor's message is a question: the journal must never file an assistant turn as theirs.
    if not payload.messages or payload.messages[-1].role != "user":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No message to answer")
    history = [
        {"role": message.role, "content": message.content} for message in payload.messages[-_MAX_INCOMING_MESSAGES:]
    ]
    return assistant, history


def _journal_turn(
    db: Session, assistant: AiAssistant, *, slug: str, payload: AiAssistantChatRequest, answer: ChatAnswer
) -> None:
    """Journal the turn and file the question it could not answer; neither may cost the visitor their answer."""
    try:
        ai_assistant_conversation_service.record_turn(
            db,
            assistant=assistant,
            session_id=payload.session_id,
            language=payload.language,
            visitor_message=payload.messages[-1].content,
            reply=answer.reply,
            is_test=payload.internal,
        )
    except Exception as exc:
        # No traceback: a database error would quote the visitor's message in the log.
        logger.warning("Assistant conversation journal failed for slug %s (%s)", slug, type(exc).__name__)
        db.rollback()
    # The operator's own tests never fill the business's list of unanswered questions.
    if answer.unanswered_question and not payload.internal:
        try:
            ai_assistant_faq_service.record_unanswered(db, assistant, answer.unanswered_question)
        except Exception as exc:
            logger.warning("Assistant unanswered question not filed for slug %s (%s)", slug, type(exc).__name__)
            db.rollback()


def _journal_streamed_turn(
    assistant_id: int, *, slug: str, payload: AiAssistantChatRequest, answer: ChatAnswer
) -> None:
    """Journal a streamed turn on a session of its own: the request's one is closed once the body streams."""
    try:
        with SessionLocal() as journal_db:
            assistant = journal_db.get(AiAssistant, assistant_id)
            if assistant is not None:
                _journal_turn(journal_db, assistant, slug=slug, payload=payload, answer=answer)
    except Exception as exc:
        logger.warning("Assistant conversation journal failed for slug %s (%s)", slug, type(exc).__name__)


def _sse_event(payload: dict[str, Any]) -> str:
    """One server-sent event of the chat stream: a JSON object on its ``data:`` line."""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/public/{slug}/chat", response_model=AiAssistantChatResponse)
async def chat_with_assistant(
    slug: str,
    payload: AiAssistantChatRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> AiAssistantChatResponse:
    """Answer a visitor's message as the prospect's grounded assistant."""
    assistant, history = _open_chat(slug, payload, request, db)
    knowledge = assistant.knowledge_json or {}
    assistant_name = assistant.assistant_name
    languages = assistant.languages
    tone = assistant.tone
    eu_only = bool(assistant.eu_only)
    # The model may take tens of seconds: the pool connection goes back meanwhile (the journal opens its own).
    db.commit()
    answer = await ai_assistant_chat_service.answer(
        knowledge=knowledge,
        assistant_name=assistant_name,
        languages=languages,
        tone=tone,
        history=history,
        eu_only=eu_only,
    )
    _journal_turn(db, assistant, slug=slug, payload=payload, answer=answer)
    return AiAssistantChatResponse(
        reply=answer.reply, offer_booking=ai_assistant_chat_service.asks_for_appointment(history[-1]["content"])
    )


@router.post("/public/{slug}/chat/stream")
async def stream_chat_with_assistant(
    slug: str,
    payload: AiAssistantChatRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Answer a visitor's message as it is written: ``data: {"delta"}`` events, then ``data: {"done", "reply",
    "offer_booking"}`` with the whole reply. The turn is journaled once the reply is complete.
    """
    assistant, history = _open_chat(slug, payload, request, db)
    assistant_id = assistant.id
    knowledge = assistant.knowledge_json or {}
    assistant_name = assistant.assistant_name
    languages = assistant.languages
    tone = assistant.tone
    eu_only = bool(assistant.eu_only)
    offer_booking = ai_assistant_chat_service.asks_for_appointment(history[-1]["content"])
    # The model may take tens of seconds: the pool connection goes back meanwhile (the journal opens its own).
    db.commit()

    async def events() -> AsyncIterator[str]:
        answer = ChatAnswer(reply="")
        async for delta in ai_assistant_chat_service.answer_stream(
            knowledge=knowledge,
            assistant_name=assistant_name,
            languages=languages,
            tone=tone,
            history=history,
            eu_only=eu_only,
        ):
            if delta.final is not None:
                answer = delta.final
            elif delta.text:
                yield _sse_event({"delta": delta.text})
        _journal_streamed_turn(assistant_id, slug=slug, payload=payload, answer=answer)
        yield _sse_event({"done": True, "reply": answer.reply, "offer_booking": offer_booking})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/public/{slug}/appointment-slots", response_model=AiAssistantAppointmentSlotsResponse)
async def get_assistant_appointment_slots(
    slug: str,
    request: Request,
    after: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
) -> AiAssistantAppointmentSlotsResponse:
    """What the appointment panel offers: the agenda's next free slots (3 at a time), else open half-days."""
    if not assistant_chat_limiter.allow(f"slots:{slug}:{client_ip(request)}"):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Trop de demandes, réessayez plus tard"
        )
    if after is not None and not BOOKABLE_YEAR_MIN <= after.year <= BOOKABLE_YEAR_MAX:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=_INVALID_REQUEST)
    assistant = public_assistant_or_404(db, slug)
    offer = await ai_assistant_calendar_service.offer(db, assistant, after=after)
    if offer.slots is not None and offer.settings is not None:
        return AiAssistantAppointmentSlotsResponse(
            mode=offer.mode,
            max_chosen=1,
            times=[AiAssistantAppointmentTime(start=slot.start, end=slot.end) for slot in offer.slots.slots],
            has_more=offer.slots.has_more,
            types=list(offer.settings.appointment_types),
            duration_minutes=offer.settings.duration_minutes,
        )
    return AiAssistantAppointmentSlotsResponse(
        mode=offer.mode,
        days=[AiAssistantAppointmentDay(date=item.day, periods=list(item.periods)) for item in offer.days],
        max_chosen=AiAssistantAppointmentSlots.MAX_CHOSEN,
    )


@router.post("/public/{slug}/lead", response_model=AiAssistantLeadResponse, status_code=status.HTTP_201_CREATED)
async def submit_assistant_lead(
    slug: str,
    payload: AiAssistantLeadRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> AiAssistantLeadResponse:
    """Record the request a visitor left through the assistant; typing and announcing run in the background."""
    if not assistant_lead_limiter.allow(f"{slug}:{client_ip(request)}"):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Trop de demandes, réessayez plus tard"
        )
    assistant = public_assistant_or_404(db, slug)
    if not payload.name.strip() or not payload.contact.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Name and contact are required")
    if payload.booking is not None and payload.internal:
        # A test visit is never announced: booking silently in a client's agenda (and texting the visitor) would be
        # an abuse path. The operator tests a real booking on their own test assistant, without « ?internal=1 ».
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=_TEST_BOOKING_REFUSED)

    try:
        captured, _created = ai_assistant_request_service.capture(
            db,
            assistant=assistant,
            name=payload.name,
            contact=payload.contact,
            need=payload.need,
            language=payload.language,
            session_id=payload.session_id,
            is_test=payload.internal,
            appointment_slots=[AppointmentSlot(day=slot.date, period=slot.period) for slot in payload.slots],
        )
    except SlotNoLongerOffered as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except AppointmentRefused as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        logger.warning("Assistant request of slug %s refused: %s", slug, exc)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=_INVALID_REQUEST) from exc
    except Exception as exc:
        # Losing the durable row must not swallow the strongest signal — still notify the owner.
        db.rollback()
        # No traceback: a database error would quote the visitor's details in the log.
        logger.warning("assistant request persist failed (slug=%s, %s)", slug, type(exc).__name__)
        if not payload.internal:
            await notification_service.notify_assistant_lead(
                db,
                user_id=assistant.user_id,
                prospect_id=assistant.prospect_id,
                fallback_name=assistant.business_name,
                lead_name=payload.name.strip(),
                need=payload.need or "",
            )
        return AiAssistantLeadResponse(ok=True)

    booked_start: datetime | None = None
    channel: AssistantVisitorChannel | None = None
    if payload.booking is not None:
        try:
            outcome = await ai_assistant_calendar_booking.book_request(
                db, assistant, captured, start=payload.booking.start, type_label=payload.booking.type
            )
        except (SlotTakenError, SlotNoLongerOffered) as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        except AppointmentRefused as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
        except (ValueError, OverflowError) as exc:
            logger.warning("Booking of slug %s refused: %s", slug, exc)
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=_INVALID_REQUEST) from exc
        if outcome.appointment is not None:
            ai_assistant_appointment_notices.schedule_confirmation(outcome.appointment.id)
            booked_start = OpeningHoursCalendar.to_business_time(outcome.appointment.starts_at)
            if outcome.appointment.visitor_phone_e164:
                channel = AssistantVisitorChannel.SMS
            elif outcome.appointment.visitor_email:
                channel = AssistantVisitorChannel.EMAIL

    ai_assistant_request_service.schedule_follow_up(captured.id)
    return AiAssistantLeadResponse(ok=True, booked_start=booked_start, confirmation_channel=channel)


# Room for the multipart envelope and the three text fields around the photo itself.
_PHOTO_REQUEST_MAX_BYTES = MAX_PHOTO_BYTES + 64 * 1024


def _photo_rejection_status(reason: AiAssistantPhotoRejection) -> int:
    """HTTP status of a refused photo."""
    if reason is AiAssistantPhotoRejection.TOO_LARGE:
        return status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    if reason is AiAssistantPhotoRejection.UNREADABLE:
        return status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    if reason is AiAssistantPhotoRejection.QUOTA:
        return status.HTTP_409_CONFLICT
    return status.HTTP_503_SERVICE_UNAVAILABLE


@router.post("/public/{slug}/photo", response_model=AiAssistantPhotoResponse, status_code=status.HTTP_201_CREATED)
async def submit_assistant_photo(
    slug: str,
    request: Request,
    db: Session = Depends(get_db),
) -> AiAssistantPhotoResponse:
    """A photo for a quote (multipart ``file``, ``session_id``, ``language``, ``internal``): stored,
    described by the vision model (never a price), kept for the visitor's request.

    The form is parsed by hand, after the rate limit and the declared size are checked: a public
    upload must never write an unbounded body to disk first.
    """
    if not assistant_photo_limiter.allow(f"{slug}:{client_ip(request)}"):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Trop de photos, réessayez plus tard")
    require_declared_length(
        request,
        max_bytes=_PHOTO_REQUEST_MAX_BYTES,
        unknown_detail="Taille de la photo inconnue",
        too_large_detail="Photo trop lourde (8 Mo maximum).",
    )
    assistant = public_assistant_or_404(db, slug)
    if not r2_storage.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Envoi de photo indisponible pour le moment"
        )
    form = await request.form(max_files=1, max_fields=3)
    try:
        upload = form.get("file")
        raw_session = form.get("session_id")
        raw_language = form.get("language")
        raw_internal = form.get("internal")
        session_id = raw_session.strip()[:64] if isinstance(raw_session, str) else ""
        if not isinstance(upload, StarletteUploadFile) or not session_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Photo ou session manquante")
        data = await upload.read(MAX_PHOTO_BYTES + 1)
    finally:
        await form.close()
    try:
        photo = await ai_assistant_photo_service.receive(
            db,
            assistant=assistant,
            data=data,
            session_id=session_id,
            language=raw_language.strip()[:8] if isinstance(raw_language, str) else None,
            is_test=isinstance(raw_internal, str) and raw_internal.strip().lower() in {"true", "1"},
        )
    except PhotoRejectedError as exc:
        raise HTTPException(status_code=_photo_rejection_status(exc.reason), detail=exc.message) from exc
    # A photo sent after the contact details joins the request already left in this visit.
    if photo.relevant is not False:
        ai_assistant_request_service.attach_late_photos(db, assistant_id=assistant.id, session_id=session_id)
    kept = ai_assistant_photo_service.kept_count(db, assistant.id, session_id)
    need = " — ".join(part for part in (photo.object_label, photo.damage) if part) or None
    return AiAssistantPhotoResponse(
        accepted=photo.relevant is not False,
        reply=photo.reply or "",
        need=need,
        remaining=max(MAX_PHOTOS_PER_SESSION - kept, 0),
    )


@router.post("/public/{slug}/interest", status_code=status.HTTP_204_NO_CONTENT)
async def submit_assistant_interest(
    slug: str,
    payload: AiAssistantInterestRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> None:
    """The prospect raised their hand on the assistant sales page — notify the owner (hot lead)."""
    if not assistant_lead_limiter.allow(f"interest:{slug}:{client_ip(request)}"):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Trop de demandes, réessayez plus tard"
        )
    assistant = ai_assistant_service.get_public_by_slug(db, slug)
    if not assistant:
        return  # Unknown or inactive slug: ignore, like the public demo-events beacon.
    await notification_service.notify_assistant_interest(
        db,
        user_id=assistant.user_id,
        prospect_id=assistant.prospect_id,
        fallback_name=assistant.business_name,
        message=(payload.message or "").strip(),
    )
