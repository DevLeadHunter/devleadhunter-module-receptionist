"""
Helpers shared by the assistant route modules: the visitor's address, the assistant a route reads, the small HTML
pages of the signed links, and the declared size of an upload.
"""

from __future__ import annotations

from fastapi import HTTPException, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from core.config import settings
from models.ai_assistant import AiAssistant
from services.ai_assistant.assistant_service import ai_assistant_service
from services.ai_assistant.request_email import AiAssistantRequestEmail


def client_ip(request: Request) -> str:
    """
    Best-effort visitor IP for rate limiting.

    nginx appends the address it saw to ``X-Forwarded-For``, so the last entry is the one a visitor cannot
    forge; the first one is whatever the visitor sent. Without a proxy, the socket peer is used.
    """
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.rsplit(",", 1)[-1].strip()
    return request.client.host if request.client else "unknown"


def demo_url(slug: str) -> str:
    """The demo page of an assistant, on the demo host."""
    return f"{settings.demo_host_base_url.rstrip('/')}/ia/{slug}"


def public_assistant_or_404(db: Session, slug: str) -> AiAssistant:
    """
    The assistant a public route serves: a demo or a sold one.

    Args:
        db: Active database session.
        slug: The assistant's public slug.

    Returns:
        The assistant.

    Raises:
        HTTPException: 404 for an unknown slug, or a deleted, expired or failed assistant.
    """
    assistant = ai_assistant_service.get_public_by_slug(db, slug)
    if assistant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assistant not found or inactive")
    return assistant


def owned_assistant_or_404(db: Session, assistant_id: int, user_id: int) -> AiAssistant:
    """
    The caller's assistant.

    Args:
        db: Active database session.
        assistant_id: The assistant.
        user_id: The caller.

    Returns:
        The assistant, not deleted.

    Raises:
        HTTPException: 404 when it is not the caller's or was deleted.
    """
    assistant = ai_assistant_service.get_for_owner(db, assistant_id, user_id)
    if assistant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assistant not found")
    return assistant


def confirmation_response(
    title: str, message: str, *, status_code: int = status.HTTP_200_OK, action_label: str | None = None
) -> HTMLResponse:
    """
    The small HTML page of a signed link; its address, which carries the token, never leaves as a referrer.

    Args:
        title: Headline (plain text).
        message: One sentence (plain text).
        status_code: The HTTP status of the page.
        action_label: Label of the button that confirms the action; no button when None.

    Returns:
        The page.
    """
    return HTMLResponse(
        AiAssistantRequestEmail.confirmation_page(title, message, action_label=action_label),
        status_code=status_code,
        headers={"Referrer-Policy": "no-referrer"},
    )


def require_declared_length(request: Request, *, max_bytes: int, unknown_detail: str, too_large_detail: str) -> None:
    """
    Refuse an upload before reading it: its declared size must be known and bounded.

    Args:
        request: The incoming request.
        max_bytes: The largest body accepted, multipart envelope included.
        unknown_detail: The refusal without a ``Content-Length``.
        too_large_detail: The refusal beyond ``max_bytes``.

    Raises:
        HTTPException: 411 without a declared size, 413 beyond ``max_bytes``.
    """
    declared_length = request.headers.get("content-length", "")
    if not declared_length.isdigit():
        raise HTTPException(status_code=status.HTTP_411_LENGTH_REQUIRED, detail=unknown_detail)
    if int(declared_length) > max_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=too_large_detail)
