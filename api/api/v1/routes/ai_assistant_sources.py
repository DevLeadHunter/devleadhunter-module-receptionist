"""Owner routes of an assistant's knowledge sources: its website, its Google listing, its documents."""

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile as StarletteUploadFile

from core.database import get_db
from models.ai_assistant import AiAssistant
from models.ai_assistant_document import AiAssistantDocument
from models.prospect_db import ProspectDB
from models.user import User
from schemas.ai_assistant_sources import (
    AiAssistantDocumentItem,
    AiAssistantDocumentUpdate,
    AiAssistantSourcePage,
    AiAssistantSourcesResponse,
    AiAssistantSourcesUpdate,
    AiAssistantWebsiteSync,
)
from services.ai_assistant.assistant_service import ai_assistant_service
from services.ai_assistant.document_service import AiAssistantDocumentService, ai_assistant_document_service
from services.ai_assistant.document_text import AiAssistantDocumentText
from services.ai_assistant.source_service import ai_assistant_source_service
from services.auth_service import get_current_active_user
from services.r2_storage_service import r2_storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai-assistants", tags=["ai-assistant-sources"])

# Room for the multipart envelope around the file itself.
_DOCUMENT_REQUEST_MAX_BYTES = AiAssistantDocumentText.MAX_BYTES + 64 * 1024


def _owned(db: Session, assistant_id: int, user: User) -> AiAssistant:
    """The caller's assistant, or 404."""
    assistant = ai_assistant_service.get_for_owner(db, assistant_id, user.id)
    if assistant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assistant not found")
    return assistant


def _listing_facts(knowledge: dict[str, Any]) -> list[str]:
    """What the Google listing (and the site prepared from it) brings the assistant, in a few French words."""
    facts: list[str] = []
    rating = knowledge.get("rating") if isinstance(knowledge.get("rating"), dict) else {}
    if rating.get("value"):  # Stored as shown: « 4,6/5 », « 128 ».
        count = f" ({rating['count']} avis)" if rating.get("count") else ""
        facts.append(f"Note {rating['value']}{count}")
    hours = knowledge.get("opening_hours") or []
    if hours:
        facts.append("Horaires")
    services = knowledge.get("services") or []
    if services:
        facts.append(_count(len(services), "service"))
    reviews = knowledge.get("reviews") or []
    if reviews:
        facts.append(f"{len(reviews)} avis client{'s' if len(reviews) > 1 else ''}")
    identity = knowledge.get("identity") if isinstance(knowledge.get("identity"), dict) else {}
    contact = [label for key, label in (("phone", "téléphone"), ("address", "adresse")) if identity.get(key)]
    if contact:
        facts.append(" et ".join(contact).capitalize())
    generated = knowledge.get("generated_site") if isinstance(knowledge.get("generated_site"), dict) else {}
    prepared = [
        part
        for part in (
            "présentation" if generated.get("about") else "",
            _count(len(generated.get("services") or []), "prestation") if generated.get("services") else "",
            _count(len(generated.get("faq") or []), "question fréquente") if generated.get("faq") else "",
        )
        if part
    ]
    if prepared:
        facts.append("Site préparé : " + ", ".join(prepared))
    return facts


def _count(count: int, words: str) -> str:
    """« 1 prestation », « 3 questions fréquentes »: every word of ``words`` takes the plural above one."""
    if count <= 1:
        return f"{count} {words}"
    return f"{count} " + " ".join(f"{word}s" for word in words.split())


def _website_url(db: Session, assistant: AiAssistant, knowledge: dict[str, Any]) -> str | None:
    """The site the assistant reads, else the prospect's site that was never read (« Mettre à jour » reads it)."""
    website = knowledge.get("website") if isinstance(knowledge.get("website"), dict) else {}
    if isinstance(website.get("url"), str) and website["url"]:
        return website["url"]
    prospect = db.get(ProspectDB, assistant.prospect_id) if assistant.prospect_id else None
    if prospect is None or not ai_assistant_service.has_readable_website(prospect):
        return None
    address = (prospect.website or "").strip()
    return address if address.startswith(("http://", "https://")) else f"https://{address}"


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


def _to_sync(knowledge: dict[str, Any]) -> AiAssistantWebsiteSync | None:
    sync = knowledge.get("website_sync")
    if not isinstance(sync, dict):
        return None
    try:
        at = datetime.fromisoformat(sync["at"]) if isinstance(sync.get("at"), str) else None
    except ValueError:
        at = None
    return AiAssistantWebsiteSync(
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
        website_url=_website_url(db, assistant, knowledge),
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
        listing_facts=_listing_facts(knowledge),
        documents=[_to_document(document) for document in ai_assistant_document_service.documents_of(db, assistant)],
        max_documents=AiAssistantDocumentService.MAX_DOCUMENTS,
    )


@router.get("/{assistant_id}/sources", response_model=AiAssistantSourcesResponse)
async def get_assistant_sources(
    assistant_id: int, user: User = Depends(get_current_active_user), db: Session = Depends(get_db)
) -> AiAssistantSourcesResponse:
    """What the assistant reads: website pages, Google listing, documents, and the last website read."""
    return _to_sources(db, _owned(db, assistant_id, user))


@router.patch("/{assistant_id}/sources", response_model=AiAssistantSourcesResponse)
async def update_assistant_sources(
    assistant_id: int,
    payload: AiAssistantSourcesUpdate,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> AiAssistantSourcesResponse:
    """Switch the website or the Google listing on or off."""
    assistant = _owned(db, assistant_id, user)
    ai_assistant_source_service.set_toggles(db, assistant, site=payload.site_enabled, listing=payload.listing_enabled)
    return _to_sources(db, assistant)


@router.post("/{assistant_id}/sources/refresh", response_model=AiAssistantSourcesResponse)
async def refresh_assistant_website(
    assistant_id: int, user: User = Depends(get_current_active_user), db: Session = Depends(get_db)
) -> AiAssistantSourcesResponse:
    """Read the business's website again now (« Mettre à jour ») and tell what changed."""
    assistant = _owned(db, assistant_id, user)
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
    declared_length = request.headers.get("content-length", "")
    if not declared_length.isdigit():
        raise HTTPException(status_code=status.HTTP_411_LENGTH_REQUIRED, detail="Taille du fichier inconnue")
    if int(declared_length) > _DOCUMENT_REQUEST_MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Fichier trop lourd (10 Mo au plus)"
        )
    assistant = _owned(db, assistant_id, user)
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
    assistant = _owned(db, assistant_id, user)
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
    assistant = _owned(db, assistant_id, user)
    if not await ai_assistant_document_service.delete(db, assistant, document_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document introuvable")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
