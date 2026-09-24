"""
The documents a business gives its assistant: add (PDF → text, file kept in R2), switch on or off, delete.

The assistant reads the text of the enabled documents from ``knowledge_json['documents']``, rewritten after
every change (the prompt's budget then decides how much of it fits).
"""

from __future__ import annotations

import logging
import re
from typing import ClassVar

from sqlalchemy import func
from sqlalchemy.orm import Session

from models.ai_assistant import AiAssistant
from models.ai_assistant_document import AiAssistantDocument
from services.ai_assistant.document_text import AiAssistantDocumentText
from services.r2_storage_service import r2_storage

logger = logging.getLogger(__name__)


class AiAssistantDocumentService:
    """Adds, switches and deletes an assistant's documents, and keeps its knowledge in step."""

    MAX_DOCUMENTS: ClassVar[int] = 10
    _UNSAFE_NAME: ClassVar[re.Pattern[str]] = re.compile(r"[\\/\x00-\x1f\x7f]+")

    @staticmethod
    def documents_of(db: Session, assistant: AiAssistant) -> list[AiAssistantDocument]:
        """The assistant's documents, oldest first."""
        return (
            db.query(AiAssistantDocument)
            .filter(AiAssistantDocument.assistant_id == assistant.id)
            .order_by(AiAssistantDocument.id.asc())
            .all()
        )

    @staticmethod
    def count(db: Session, assistant: AiAssistant) -> int:
        """How many documents the assistant has."""
        return int(
            db.query(func.count(AiAssistantDocument.id))
            .filter(AiAssistantDocument.assistant_id == assistant.id)
            .scalar()
            or 0
        )

    async def add(self, db: Session, assistant: AiAssistant, *, filename: str, data: bytes) -> AiAssistantDocument:
        """
        Read a PDF, keep the file in R2 and give its text to the assistant.

        Args:
            db: Active database session.
            assistant: The assistant.
            filename: The uploaded file's name (shown to the operator, cited to visitors).
            data: The file's bytes.

        Returns:
            The stored, enabled document.

        Raises:
            ValueError: When the assistant has ``MAX_DOCUMENTS`` already, or the file is refused
                (``DocumentRejected``: not a readable text PDF, or too long to read).
            RuntimeError: When the storage is unavailable, or another PDF is being read (``DocumentReaderBusy``).
        """
        if self.count(db, assistant) >= self.MAX_DOCUMENTS:
            raise ValueError(self._limit_message())
        if not r2_storage.is_configured():
            raise RuntimeError("Stockage des fichiers indisponible")
        extracted = await AiAssistantDocumentText.read(data)
        key = r2_storage.assistant_document_key(assistant.id)
        try:
            await r2_storage.upload_bytes_async(key, data, "application/pdf")
        except Exception as exc:
            logger.warning("Document of assistant %s not uploaded", assistant.id, exc_info=True)
            raise RuntimeError("Stockage des fichiers indisponible") from exc
        try:
            # Reading and storing take seconds: take the assistant as it is now, so a change made meanwhile stays.
            db.commit()
            db.refresh(assistant)
            if self.count(db, assistant) >= self.MAX_DOCUMENTS:  # Another upload landed meanwhile.
                raise ValueError(self._limit_message())
            document = AiAssistantDocument(
                user_id=assistant.user_id,
                assistant_id=assistant.id,
                name=self.display_name(filename),
                storage_key=key,
                size_bytes=len(data),
                pages=extracted.pages,
                text=extracted.text,
                truncated=extracted.truncated,
                enabled=True,
            )
            db.add(document)
            db.flush()
            self.sync_knowledge(db, assistant)
            db.commit()
        except Exception:
            db.rollback()
            await self._delete_file(key)
            raise
        db.refresh(document)
        return document

    def set_enabled(
        self, db: Session, assistant: AiAssistant, document_id: int, *, enabled: bool
    ) -> AiAssistantDocument | None:
        """
        Switch a document on or off for the assistant.

        Args:
            db: Active database session.
            assistant: The assistant.
            document_id: The document.
            enabled: Whether the assistant reads it.

        Returns:
            The document, or None when it is not the assistant's.
        """
        document = self._get(db, assistant, document_id)
        if document is None:
            return None
        document.enabled = enabled
        db.flush()
        self.sync_knowledge(db, assistant)
        db.commit()
        db.refresh(document)
        return document

    async def delete(self, db: Session, assistant: AiAssistant, document_id: int) -> bool:
        """
        Delete a document and its file.

        Args:
            db: Active database session.
            assistant: The assistant.
            document_id: The document.

        Returns:
            True when it existed (the file is deleted best effort).
        """
        document = self._get(db, assistant, document_id)
        if document is None:
            return False
        key = document.storage_key
        db.delete(document)
        db.flush()
        self.sync_knowledge(db, assistant)
        db.commit()
        await self._delete_file(key)
        return True

    def sync_knowledge(self, db: Session, assistant: AiAssistant) -> None:
        """
        Rewrite ``knowledge_json['documents']`` from the enabled documents (not committed).

        Args:
            db: Active database session.
            assistant: The assistant.
        """
        knowledge = dict(assistant.knowledge_json or {})
        knowledge["documents"] = [
            {"id": document.id, "name": document.name, "text": document.text}
            for document in self.documents_of(db, assistant)
            if document.enabled
        ]
        assistant.knowledge_json = knowledge

    @classmethod
    def display_name(cls, filename: str) -> str:
        """An uploaded file's name without its path or control characters, bounded (« Tarifs 2026.pdf »)."""
        base = cls._UNSAFE_NAME.sub(" ", (filename or "").rsplit("/", 1)[-1].rsplit("\\", 1)[-1])
        name = " ".join(base.split())[:120]
        return name or "Document.pdf"

    @classmethod
    def _limit_message(cls) -> str:
        """The refusal of an eleventh document."""
        return f"{cls.MAX_DOCUMENTS} documents au plus : supprimez-en un d'abord"

    @staticmethod
    async def _delete_file(key: str) -> None:
        """Delete a document's file, best effort (an orphan file is only storage)."""
        try:
            await r2_storage.delete_async(key)
        except Exception:
            logger.warning("Document file %s could not be deleted", key, exc_info=True)

    @staticmethod
    def _get(db: Session, assistant: AiAssistant, document_id: int) -> AiAssistantDocument | None:
        """One of the assistant's documents."""
        return (
            db.query(AiAssistantDocument)
            .filter(AiAssistantDocument.id == document_id, AiAssistantDocument.assistant_id == assistant.id)
            .first()
        )


ai_assistant_document_service = AiAssistantDocumentService()
