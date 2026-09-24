"""Owner routes of an assistant's knowledge sources: its website, its Google listing, its documents."""

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile as StarletteUploadFile

from api.v1.routes.ai_assistant_common import owned_assistant_or_404, require_declared_length
from core.database import get_db
from models.ai_assistant import AiAssistant
from models.ai_assistant_document import AiAssistantDocument
from models.user import User
from schemas.ai_assistant_sources import (
    AiAssistantDocumentItem,
    AiAssistantDocumentUpdate,
    AiAssistantSourcePage,
    AiAssistantSourcesResponse,
    AiAssistantSourcesUpdate,
    AiAssistantWebsiteSyncItem,
)
from services.ai_assistant.document_service import AiAssistantDocumentService, ai_assistant_document_service
from services.ai_assistant.document_text import AiAssistantDocumentText
from services.ai_assistant.source_service import AiAssistantSourceService, ai_assistant_source_service
from services.auth_service import get_current_active_user
from services.r2_storage_service import r2_storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai-assistants", tags=["ai-assistant-sources"])

# Room for the multipart envelope around the file itself.
_DOCUMENT_REQUEST_MAX_BYTES = AiAssistantDocumentText.MAX_BYTES + 64 * 1024


def _to_document(document: AiAssistantDocument) -> AiAssistantDocumentItem:
    try:
        url: str | None = r2_storage.public_url(document.storage_key)
    except RuntimeError:
        url = None
    return AiAssistantDocumentItem(
        id=document.id,
        name=document.name,
        pages=document.pages,
        size_bytes=document.size_bytes,
        chars=len(document.text),
        truncated=document.truncated,
        enabled=document.enabled,
        url=url,
        created_at=document.created_at,
    )


def _to_sync(knowledge: dict[str, Any]) -> AiAssistantWebsiteSyncItem | None:
    sync = knowledge.get("website_sync")
    if not isinstance(sync, dict):
        return None
    try:
        at = datetime.fromisoformat(sync["at"]) if isinstance(sync.get("at"), str) else None
    except ValueError:
        at = None
    return AiAssistantWebsiteSyncItem(
        at=at,
        pages=int(sync.get("pages") or 0),
        added=[str(url) for url in sync.get("added") or []],
        removed=[str(url) for url in sync.get("removed") or []],
        changed=[str(url) for url in sync.get("changed") or []],
        error=sync.get("error") if isinstance(sync.get("error"), str) else None,
    )


def _to_sources(db: Session, assistant: AiAssistant) -> AiAssistantSourcesResponse:
    knowledge = assistant.knowledge_json or {}
    website = knowledge.get("website") if isinstance(knowledge.get("website"), dict) else {}
    toggles = ai_assistant_source_service.toggles(assistant)
    return AiAssistantSourcesResponse(
        website_url=ai_assistant_source_service.website_url(db, assistant),
        site_enabled=toggles.site,
        listing_enabled=toggles.listing,
        pages=[
            AiAssistantSourcePage(
                url=str(page["url"]), title=page.get("title") or None, chars=len(page.get("text") or "")
            )
            for page in website.get("pages") or []
            if isinstance(page, dict) and page.get("url")
        ],
        sync=_to_sync(knowledge),
        listing_facts=AiAssistantSourceService.listing_facts(knowledge),
        documents=[_to_document(document) for document in ai_assistant_document_service.documents_of(db, assistant)],
        max_documents=AiAssistantDocumentService.MAX_DOCUMENTS,
    )


@router.get("/{assistant_id}/sources", response_model=AiAssistantSourcesResponse)
async def get_assistant_sources(
    assistant_id: int, user: User = Depends(get_current_active_user), db: Session = Depends(get_db)
) -> AiAssistantSourcesResponse:
    """What the assistant reads: website pages, Google listing, documents, and the last website read."""
    return _to_sources(db, owned_assistant_or_404(db, assistant_id, user.id))


@router.patch("/{assistant_id}/sources", response_model=AiAssistantSourcesResponse)
async def update_assistant_sources(
    assistant_id: int,
    payload: AiAssistantSourcesUpdate,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> AiAssistantSourcesResponse:
    """Switch the website or the Google listing on or off."""
    assistant = owned_assistant_or_404(db, assistant_id, user.id)
    ai_assistant_source_service.set_toggles(db, assistant, site=payload.site_enabled, listing=payload.listing_enabled)
    return _to_sources(db, assistant)


@router.post("/{assistant_id}/sources/refresh", response_model=AiAssistantSourcesResponse)
async def refresh_assistant_website(
    assistant_id: int, user: User = Depends(get_current_active_user), db: Session = Depends(get_db)
) -> AiAssistantSourcesResponse:
    """Read the business's website again now (« Mettre à jour ») and tell what changed."""
    assistant = owned_assistant_or_404(db, assistant_id, user.id)
    await ai_assistant_source_service.refresh_website(db, assistant, force=True)
    return _to_sources(db, assistant)


@router.post("/{assistant_id}/documents", response_model=AiAssistantDocumentItem, status_code=status.HTTP_201_CREATED)
async def upload_assistant_document(
    assistant_id: int,
    request: Request,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> AiAssistantDocumentItem:
    """A PDF for the assistant to read (multipart ``file``); the declared size is checked before reading."""
    require_declared_length(
        request,
        max_bytes=_DOCUMENT_REQUEST_MAX_BYTES,
        unknown_detail="Taille du fichier inconnue",
        too_large_detail="Fichier trop lourd (10 Mo au plus)",
    )
    assistant = owned_assistant_or_404(db, assistant_id, user.id)
    form = await request.form(max_files=1, max_fields=1)
    try:
        upload = form.get("file")
        if not isinstance(upload, StarletteUploadFile):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Fichier manquant")
        filename = upload.filename or "Document.pdf"
        data = await upload.read(AiAssistantDocumentText.MAX_BYTES + 1)
    finally:
        await form.close()
    try:
        document = await ai_assistant_document_service.add(db, assistant, filename=filename, data=data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except RuntimeError as exc:
        logger.warning("Document of assistant %s not stored", assistant.id, exc_info=True)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return _to_document(document)


@router.patch("/{assistant_id}/documents/{document_id}", response_model=AiAssistantDocumentItem)
async def update_assistant_document(
    assistant_id: int,
    document_id: int,
    payload: AiAssistantDocumentUpdate,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> AiAssistantDocumentItem:
    """Switch a document on or off for the assistant."""
    assistant = owned_assistant_or_404(db, assistant_id, user.id)
    document = ai_assistant_document_service.set_enabled(db, assistant, document_id, enabled=payload.enabled)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document introuvable")
    return _to_document(document)


@router.delete("/{assistant_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assistant_document(
    assistant_id: int,
    document_id: int,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Response:
    """Delete a document and its file."""
    assistant = owned_assistant_or_404(db, assistant_id, user.id)
    if not await ai_assistant_document_service.delete(db, assistant, document_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document introuvable")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
