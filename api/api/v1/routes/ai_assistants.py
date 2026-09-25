"""Owner routes of the AI assistants: generate, list, edit, regenerate, delete, the client-space link and the
prospecting video.
"""

import logging
import shutil
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from api.v1.routes.ai_assistant_common import (
    demo_url,
    owned_assistant_or_404,
)
from core.database import get_db
from enums.ai_assistant_request import AiAssistantRequestType
from enums.ai_assistant_status import AiAssistantStatus
from enums.demo_video_status import DemoVideoStatus
from models.ai_assistant import AiAssistant
from models.prospect_db import ProspectDB
from models.user import User
from schemas.ai_assistant import (
    AiAssistantAlertSettings,
    AiAssistantCreateRequest,
    AiAssistantListResponse,
    AiAssistantResponse,
    AiAssistantUpdateRequest,
)
from schemas.ai_assistant_client_space import AiAssistantClientLinkRequest, AiAssistantClientLinkResponse
from services.ai_assistant.assistant_service import ai_assistant_service
from services.ai_assistant.client_space_service import ai_assistant_client_space_service
from services.ai_assistant.config_builder import ai_assistant_config_builder
from services.ai_assistant.conversation_service import ConversationCounts, ai_assistant_conversation_service
from services.ai_assistant.embed_snippet import AiAssistantEmbedSnippet
from services.ai_assistant.report_service import ai_assistant_report_service
from services.ai_assistant.request_alerts import AlertSettings
from services.ai_assistant.request_service import RequestCounts, ai_assistant_request_service
from services.assistant_subscription_service import assistant_subscription_service
from services.assistant_video_service import (
    ASSISTANT_PRESENTER_MODULE,
    assistant_video_service,
    has_ready_video,
    thumbnail_object_key,
    video_object_key,
    video_page_url,
)
from services.auth_service import get_current_active_user
from services.email_variables import EmailVariables
from services.presenter_video_service import presenter_video_service
from services.r2_storage_service import r2_storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai-assistants", tags=["ai-assistants"])


def _to_owner_response(
    assistant: AiAssistant,
    subscription: object | None = None,
    conversations: ConversationCounts | None = None,
    requests: RequestCounts | None = None,
) -> AiAssistantResponse:
    return AiAssistantResponse(
        id=assistant.id,
        slug=assistant.slug,
        prospect_id=assistant.prospect_id,
        business_name=assistant.business_name,
        assistant_name=assistant.assistant_name,
        assistant_gender=ai_assistant_config_builder.resolve_persona_gender(assistant.assistant_name).value,
        email=assistant.email,
        languages=assistant.languages or [],
        tone=assistant.tone,
        accent_color=ai_assistant_service.accent_color(assistant),
        use_brand_color=assistant.use_brand_color,
        status=assistant.status,
        demo_url=demo_url(assistant.slug),
        embed_snippet=AiAssistantEmbedSnippet.render(assistant.slug),
        demo_link_sent_at=assistant.demo_link_sent_at,
        expires_at=assistant.expires_at,
        video_status=assistant.video_status,
        video_page_url=video_page_url(assistant.slug) if has_ready_video(assistant) else None,
        video_error=assistant.video_error,
        subscription_status=getattr(subscription, "status", None),
        subscription_amount_cents=getattr(subscription, "amount_cents", None),
        subscription_interval=getattr(subscription, "interval", None),
        conversations_7d=conversations.last_7_days if conversations else 0,
        conversations_30d=conversations.last_30_days if conversations else 0,
        requests_7d=requests.last_7_days if requests else 0,
        requests_30d=requests.last_30_days if requests else 0,
        requests_outside_hours_pct=requests.outside_hours_pct if requests else None,
        churn_risk=ai_assistant_report_service.is_churn_risk(
            status=assistant.status,
            subscribed_at=getattr(subscription, "activated_at", None) or getattr(subscription, "created_at", None),
            conversations_30d=conversations.last_30_days if conversations else 0,
            requests_30d=requests.last_30_days if requests else 0,
        ),
        alerts=_alert_settings(assistant),
        eu_only=bool(assistant.eu_only),
        created_at=assistant.created_at,
    )


def _to_full_owner_response(db: Session, assistant: AiAssistant) -> AiAssistantResponse:
    """One assistant as the list shows it (subscription and counts included), after an edit."""
    return _to_owner_response(
        assistant,
        assistant_subscription_service.active_by_assistant_ids(db, [assistant.id]).get(assistant.id),
        ai_assistant_conversation_service.counts_for_assistants(db, [assistant.id]).get(assistant.id),
        ai_assistant_request_service.counts_for_assistants(db, [assistant.id]).get(assistant.id),
    )


def _alert_settings(assistant: AiAssistant) -> AiAssistantAlertSettings:
    settings = AlertSettings.of(assistant)
    return AiAssistantAlertSettings(
        phone=settings.phone_e164,
        sms_enabled=settings.sms_enabled,
        email_enabled=settings.email_enabled,
        sms_types=[item for item in AiAssistantRequestType if item in settings.sms_types],
        quiet_start_hour=settings.quiet_start_hour,
        quiet_end_hour=settings.quiet_end_hour,
    )


@router.post("", response_model=AiAssistantResponse, status_code=status.HTTP_201_CREATED)
async def create_assistant(
    payload: AiAssistantCreateRequest,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> AiAssistantResponse:
    """Generate an assistant for one of the caller's prospects."""
    prospect = db.query(ProspectDB).filter(ProspectDB.id == payload.prospect_id, ProspectDB.user_id == user.id).first()
    if not prospect:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prospect not found")
    assistant = await ai_assistant_service.create_for_prospect(db, user_id=user.id, prospect=prospect)
    return _to_owner_response(assistant)


@router.get("", response_model=AiAssistantListResponse)
async def list_assistants(
    prospect_id: int | None = None,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> AiAssistantListResponse:
    """List the caller's assistants, newest first (optionally filtered to one prospect)."""
    query = db.query(AiAssistant).filter(AiAssistant.user_id == user.id, AiAssistant.deleted_at.is_(None))
    if prospect_id is not None:
        query = query.filter(AiAssistant.prospect_id == prospect_id)
    assistants = query.order_by(AiAssistant.created_at.desc()).all()
    subscriptions = assistant_subscription_service.active_by_assistant_ids(db, [a.id for a in assistants])
    conversation_counts = ai_assistant_conversation_service.counts_for_assistants(db, [a.id for a in assistants])
    request_counts = ai_assistant_request_service.counts_for_assistants(db, [a.id for a in assistants])
    return AiAssistantListResponse(
        assistants=[
            _to_owner_response(
                assistant,
                subscriptions.get(assistant.id),
                conversation_counts.get(assistant.id),
                request_counts.get(assistant.id),
            )
            for assistant in assistants
        ]
    )


@router.get("/{assistant_id:int}", response_model=AiAssistantResponse)
async def get_assistant(
    assistant_id: int,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> AiAssistantResponse:
    """One of the caller's assistants, with its counters and subscription (the detail page)."""
    assistant = owned_assistant_or_404(db, assistant_id, user.id)
    return _to_full_owner_response(db, assistant)


@router.patch("/{assistant_id}", response_model=AiAssistantResponse)
async def update_assistant(
    assistant_id: int,
    payload: AiAssistantUpdateRequest,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> AiAssistantResponse:
    """Edit one of the caller's assistants (name, persona, languages, accent, owner alerts, EU only)."""
    assistant = (
        db.query(AiAssistant)
        .filter(AiAssistant.id == assistant_id, AiAssistant.user_id == user.id, AiAssistant.deleted_at.is_(None))
        .first()
    )
    if not assistant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assistant not found")
    try:
        updated = ai_assistant_service.update(db, assistant, payload.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return _to_full_owner_response(db, updated)


@router.post("/{assistant_id}/regenerate", response_model=AiAssistantResponse)
async def regenerate_assistant(
    assistant_id: int,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> AiAssistantResponse:
    """Rebuild an assistant's knowledge from its prospect's latest data (branding and persona kept)."""
    assistant = (
        db.query(AiAssistant)
        .filter(AiAssistant.id == assistant_id, AiAssistant.user_id == user.id, AiAssistant.deleted_at.is_(None))
        .first()
    )
    if not assistant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assistant not found")
    if assistant.prospect_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="This assistant has no prospect to regenerate from"
        )
    prospect = (
        db.query(ProspectDB).filter(ProspectDB.id == assistant.prospect_id, ProspectDB.user_id == user.id).first()
    )
    if not prospect:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Prospect not found for this assistant")
    updated = await ai_assistant_service.regenerate_for_prospect(db, assistant=assistant, prospect=prospect)
    return _to_full_owner_response(db, updated)


@router.post("/{assistant_id}/client-link", response_model=AiAssistantClientLinkResponse)
async def issue_assistant_client_link(
    assistant_id: int,
    payload: AiAssistantClientLinkRequest,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> AiAssistantClientLinkResponse:
    """A fresh client-space link for one of the caller's sold assistants, emailed to the business on demand."""
    assistant = owned_assistant_or_404(db, assistant_id, user.id)
    if assistant.status != AiAssistantStatus.DELIVERED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="L'espace client s'ouvre une fois l'assistant vendu."
        )
    delivery = await ai_assistant_client_space_service.issue_link(db, assistant, send=payload.send)
    return AiAssistantClientLinkResponse(
        url=delivery.url, expires_at=delivery.expires_at, sent_to=delivery.sent_to, send_error=delivery.send_error
    )


@router.post("/{assistant_id}/video", response_model=AiAssistantResponse)
async def generate_assistant_video(
    assistant_id: int,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> AiAssistantResponse:
    """Start generating the assistant's prospection video (webcam speech + a recording of the widget)."""
    assistant = owned_assistant_or_404(db, assistant_id, user.id)
    try:
        assistant_video_service.request_generation(db, assistant, user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return _to_full_owner_response(db, assistant)


@router.get("/{assistant_id}/video-context")
async def get_assistant_video_context(
    assistant_id: int,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Everything the desktop sidecar needs to render this assistant's video locally.

    Unlike the site — whose editor sequence needs the owner's Storyblok session, forcing a desktop
    build — the assistant video has no such dependency; the desktop path is preferred only to spare
    the shared VPS. The sidecar records the public widget answering, montages it with its bundled
    ffmpeg, and posts the finished clip back via ``POST /{id}/video-final``.
    """
    assistant = owned_assistant_or_404(db, assistant_id, user.id)
    if assistant.status != AiAssistantStatus.ACTIVE.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La vidéo ne peut être générée que pour un assistant actif.",
        )
    presenter = presenter_video_service.get_for_user(db, user.id, ASSISTANT_PRESENTER_MODULE)
    if presenter is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucun clip de présentation « assistant » enregistré.",
        )
    total_seconds = presenter.duration_seconds - presenter.intro_seconds - presenter.outro_seconds
    first_name: str | None = None
    if assistant.prospect_id:
        resolved_first, _last, _gender = EmailVariables.resolved_contact(db, assistant.prospect_id)
        first_name = resolved_first or None
    return {
        "slug": assistant.slug,
        "demo_url": demo_url(assistant.slug),
        "first_name": first_name,
        "presenter_duration": presenter.duration_seconds,
        "presenter_intro": presenter.intro_seconds,
        "presenter_outro": presenter.outro_seconds,
        "total_seconds": round(total_seconds, 2),
        "out_width": 1280,
        "out_height": 720,
        "fps": 30,
    }


@router.post("/{assistant_id}/video-final", response_model=AiAssistantResponse)
async def upload_assistant_video_final(
    assistant_id: int,
    file: UploadFile = File(...),
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> AiAssistantResponse:
    """
    Store a desktop-produced FINAL assistant video and mark it ready.

    The sidecar montages the whole clip locally and returns a zip (``video.mp4`` + ``thumbnail.jpg``);
    here we push both to R2 and flip the status — the VPS never touches ffmpeg for a desktop build.
    """
    assistant = owned_assistant_or_404(db, assistant_id, user.id)

    work_dir = Path(tempfile.mkdtemp(prefix=f"assistant-video-final-{assistant.slug}-"))
    try:
        zip_path = work_dir / "bundle.zip"
        with zip_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        video_path = work_dir / "video.mp4"
        thumbnail_path = work_dir / "thumbnail.jpg"
        try:
            with zipfile.ZipFile(zip_path) as archive:
                video_path.write_bytes(archive.read("video.mp4"))
                thumbnail_path.write_bytes(archive.read("thumbnail.jpg"))
        except (zipfile.BadZipFile, KeyError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Archive vidéo invalide (video.mp4 + thumbnail.jpg attendus).",
            ) from exc

        await r2_storage.upload_file_async(video_path, video_object_key(assistant.slug), "video/mp4")
        await r2_storage.upload_file_async(thumbnail_path, thumbnail_object_key(assistant.slug), "image/jpeg")
        assistant.video_status = DemoVideoStatus.READY.value
        assistant.video_error = None
        assistant.video_generated_at = datetime.now(UTC)
        db.commit()
        db.refresh(assistant)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
    return _to_full_owner_response(db, assistant)


@router.delete("/{assistant_id}/video", response_model=AiAssistantResponse)
async def clear_assistant_video(
    assistant_id: int,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> AiAssistantResponse:
    """Delete the assistant's generated video and reset its state."""
    assistant = owned_assistant_or_404(db, assistant_id, user.id)
    assistant_video_service.clear_video(db, assistant)
    return _to_full_owner_response(db, assistant)


@router.delete("/{assistant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assistant(
    assistant_id: int,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> None:
    """Soft-delete one of the caller's assistants."""
    assistant = (
        db.query(AiAssistant)
        .filter(AiAssistant.id == assistant_id, AiAssistant.user_id == user.id, AiAssistant.deleted_at.is_(None))
        .first()
    )
    if not assistant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assistant not found")
    assistant.status = AiAssistantStatus.DELETED.value
    assistant.deleted_at = datetime.utcnow()
    db.commit()
