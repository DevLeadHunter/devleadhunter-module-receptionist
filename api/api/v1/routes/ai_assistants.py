"""AI assistant routes: owner generation/management, and public widget config + grounded chat."""

import logging
import shutil
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from core.config import settings
from core.database import get_db
from enums.ai_assistant_status import AiAssistantStatus
from enums.demo_video_status import DemoVideoStatus
from models.ai_assistant import AiAssistant
from models.ai_assistant_lead import AiAssistantLead
from models.prospect_db import ProspectDB
from models.user import User
from schemas.ai_assistant import (
    AiAssistantChatRequest,
    AiAssistantChatResponse,
    AiAssistantCreateRequest,
    AiAssistantInterestRequest,
    AiAssistantLeadItem,
    AiAssistantLeadRequest,
    AiAssistantLeadResponse,
    AiAssistantLeadsResponse,
    AiAssistantListResponse,
    AiAssistantPublicResponse,
    AiAssistantResponse,
    AiAssistantUpdateRequest,
)
from services.ai_assistant.assistant_service import ai_assistant_service
from services.ai_assistant.chat_service import ai_assistant_chat_service
from services.assistant_video_service import (
    ASSISTANT_PRESENTER_MODULE,
    assistant_video_service,
    has_ready_video,
    public_thumbnail_url,
    public_video_file_url,
    thumbnail_object_key,
    video_object_key,
    video_page_url,
)
from services.auth_service import get_current_active_user
from services.email_variables import EmailVariables
from services.notification_service import notification_service
from services.presenter_video_service import presenter_video_service
from services.r2_storage_service import r2_storage
from services.rate_limiter import assistant_chat_limiter, assistant_lead_limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai-assistants", tags=["ai-assistants"])

# Cap the history a public caller may submit, before the chat service bounds it further.
_MAX_INCOMING_MESSAGES = 40


def _demo_url(slug: str) -> str:
    base = settings.demo_host_base_url.rstrip("/")
    return f"{base}/a/{slug}"


def _embed_snippet(slug: str) -> str:
    base = settings.demo_host_base_url.rstrip("/")
    return f'<script src="{base}/ai-assistant.js" data-slug="{slug}" defer></script>'


def _client_ip(request: Request) -> str:
    """Best-effort visitor IP for rate limiting (honours the nginx ``X-Forwarded-For``)."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _accent_color(knowledge: dict[str, Any] | None) -> str | None:
    palette = (knowledge or {}).get("palette")
    return palette.get("accent") if isinstance(palette, dict) else None


def _owner_public_fields(assistant: AiAssistant) -> dict[str, str | None]:
    """Owner contact shown in the « me contacter » banner (photo guarded on the R2 base)."""
    user = assistant.user
    if user is None:
        return {}
    fields: dict[str, str | None] = {
        "owner_name": user.name,
        "owner_contact_phone": user.contact_phone,
        "owner_contact_email": user.contact_email,
    }
    if user.profile_photo_path and (settings.r2_public_base_url or "").strip():
        fields["owner_profile_photo_url"] = r2_storage.public_url(user.profile_photo_path)
    return fields


def _to_owner_response(assistant: AiAssistant) -> AiAssistantResponse:
    return AiAssistantResponse(
        id=assistant.id,
        slug=assistant.slug,
        prospect_id=assistant.prospect_id,
        business_name=assistant.business_name,
        assistant_name=assistant.assistant_name,
        languages=assistant.languages or [],
        tone=assistant.tone,
        accent_color=_accent_color(assistant.knowledge_json),
        use_brand_color=assistant.use_brand_color,
        status=assistant.status,
        demo_url=_demo_url(assistant.slug),
        embed_snippet=_embed_snippet(assistant.slug),
        video_status=assistant.video_status,
        video_page_url=video_page_url(assistant.slug) if has_ready_video(assistant) else None,
        video_error=assistant.video_error,
        created_at=assistant.created_at,
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
    return AiAssistantListResponse(assistants=[_to_owner_response(assistant) for assistant in assistants])


@router.get("/leads", response_model=AiAssistantLeadsResponse)
async def list_assistant_leads(
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> AiAssistantLeadsResponse:
    """List the leads captured across the caller's assistants, newest first."""
    rows = (
        db.query(AiAssistantLead, AiAssistant.business_name)
        .join(AiAssistant, AiAssistant.id == AiAssistantLead.assistant_id)
        .filter(AiAssistantLead.user_id == user.id)
        .order_by(AiAssistantLead.created_at.desc())
        .limit(500)
        .all()
    )
    return AiAssistantLeadsResponse(
        leads=[
            AiAssistantLeadItem(
                id=lead.id,
                assistant_id=lead.assistant_id,
                prospect_id=lead.prospect_id,
                business_name=business_name,
                name=lead.name,
                contact=lead.contact,
                need=lead.need,
                language=lead.language,
                created_at=lead.created_at,
            )
            for lead, business_name in rows
        ]
    )


@router.patch("/{assistant_id}", response_model=AiAssistantResponse)
async def update_assistant(
    assistant_id: int,
    payload: AiAssistantUpdateRequest,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> AiAssistantResponse:
    """Edit one of the caller's assistants (name, persona, languages, accent)."""
    assistant = (
        db.query(AiAssistant)
        .filter(AiAssistant.id == assistant_id, AiAssistant.user_id == user.id, AiAssistant.deleted_at.is_(None))
        .first()
    )
    if not assistant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assistant not found")
    updated = ai_assistant_service.update(db, assistant, payload.model_dump(exclude_unset=True))
    return _to_owner_response(updated)


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
    return _to_owner_response(updated)


def _owned_assistant_or_404(db: Session, assistant_id: int, user_id: int) -> AiAssistant:
    """Fetch a caller-owned, non-deleted assistant, or raise 404."""
    assistant = (
        db.query(AiAssistant)
        .filter(AiAssistant.id == assistant_id, AiAssistant.user_id == user_id, AiAssistant.deleted_at.is_(None))
        .first()
    )
    if not assistant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assistant not found")
    return assistant


@router.post("/{assistant_id}/video", response_model=AiAssistantResponse)
async def generate_assistant_video(
    assistant_id: int,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> AiAssistantResponse:
    """Start generating the assistant's prospection video (webcam speech + a recording of the widget)."""
    assistant = _owned_assistant_or_404(db, assistant_id, user.id)
    try:
        assistant_video_service.request_generation(db, assistant, user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return _to_owner_response(assistant)


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
    assistant = _owned_assistant_or_404(db, assistant_id, user.id)
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
        "demo_url": _demo_url(assistant.slug),
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
    assistant = _owned_assistant_or_404(db, assistant_id, user.id)

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
    return _to_owner_response(assistant)


@router.delete("/{assistant_id}/video", response_model=AiAssistantResponse)
async def clear_assistant_video(
    assistant_id: int,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> AiAssistantResponse:
    """Delete the assistant's generated video and reset its state."""
    assistant = _owned_assistant_or_404(db, assistant_id, user.id)
    assistant_video_service.clear_video(db, assistant)
    return _to_owner_response(assistant)


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


@router.get("/public/{slug}", response_model=AiAssistantPublicResponse)
async def get_public_assistant(slug: str, db: Session = Depends(get_db)) -> AiAssistantPublicResponse:
    """Public config consumed by the embedded chat widget."""
    assistant = ai_assistant_service.get_public_by_slug(db, slug)
    if not assistant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assistant not found or inactive")
    video_ready = has_ready_video(assistant)
    return AiAssistantPublicResponse(
        slug=assistant.slug,
        business_name=assistant.business_name,
        assistant_name=assistant.assistant_name,
        languages=assistant.languages or [],
        accent_color=_accent_color(assistant.knowledge_json),
        status=assistant.status,
        **_owner_public_fields(assistant),
        video_available=video_ready,
        video_url=public_video_file_url(assistant.slug) if video_ready else None,
        video_thumbnail_url=public_thumbnail_url(assistant.slug, assistant.video_generated_at) if video_ready else None,
    )


@router.post("/public/{slug}/chat", response_model=AiAssistantChatResponse)
async def chat_with_assistant(
    slug: str,
    payload: AiAssistantChatRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> AiAssistantChatResponse:
    """Answer a visitor's message as the prospect's grounded assistant."""
    if not assistant_chat_limiter.allow(f"{slug}:{_client_ip(request)}"):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Trop de messages, réessayez plus tard"
        )
    assistant = ai_assistant_service.get_public_by_slug(db, slug)
    if not assistant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assistant not found or inactive")
    if not payload.messages:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No message to answer")

    history = [
        {"role": message.role, "content": message.content} for message in payload.messages[-_MAX_INCOMING_MESSAGES:]
    ]
    reply = await ai_assistant_chat_service.answer(
        knowledge=assistant.knowledge_json or {},
        assistant_name=assistant.assistant_name,
        languages=assistant.languages,
        tone=assistant.tone,
        history=history,
    )
    return AiAssistantChatResponse(reply=reply)


@router.post("/public/{slug}/lead", response_model=AiAssistantLeadResponse, status_code=status.HTTP_201_CREATED)
async def submit_assistant_lead(
    slug: str,
    payload: AiAssistantLeadRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> AiAssistantLeadResponse:
    """Record a lead a visitor left through the assistant, then notify the owner."""
    if not assistant_lead_limiter.allow(f"{slug}:{_client_ip(request)}"):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Trop de demandes, réessayez plus tard"
        )
    assistant = ai_assistant_service.get_public_by_slug(db, slug)
    if not assistant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assistant not found or inactive")
    if not payload.name.strip() or not payload.contact.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Name and contact are required")

    try:
        ai_assistant_service.record_lead(
            db,
            assistant=assistant,
            name=payload.name,
            contact=payload.contact,
            need=payload.need,
            language=payload.language,
        )
    except Exception:
        # Losing the durable row must not swallow the strongest signal — still notify the owner.
        db.rollback()
        logger.warning("assistant lead persist failed (slug=%s)", slug)

    await notification_service.notify_assistant_lead(
        db,
        user_id=assistant.user_id,
        prospect_id=assistant.prospect_id,
        fallback_name=assistant.business_name,
        lead_name=payload.name.strip(),
        need=payload.need or "",
    )
    return AiAssistantLeadResponse(ok=True)


@router.post("/public/{slug}/interest", status_code=status.HTTP_204_NO_CONTENT)
async def submit_assistant_interest(
    slug: str,
    payload: AiAssistantInterestRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> None:
    """The prospect raised their hand on the assistant sales page — notify the owner (hot lead)."""
    if not assistant_lead_limiter.allow(f"interest:{slug}:{_client_ip(request)}"):
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
