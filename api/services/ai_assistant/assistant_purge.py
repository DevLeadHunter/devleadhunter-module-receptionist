"""
What a deleted receptionist leaves behind is erased: its files on R2 (documents, visitors' photos, prospecting video)
and the rows that hold its visitors' data (conversations and their messages, requests, photos, appointments, reports,
the agenda's and the mailbox's Google tokens, the ids of the emails read, documents). The mailbox's Google grant is
revoked first. The assistant row itself stays, soft-deleted, for its orders and subscriptions; a receptionist still
paid for is never deleted.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from sqlalchemy import exists, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from enums.ai_assistant_subscription_status import LIVE_SUBSCRIPTION_STATUSES
from models.ai_assistant import AiAssistant
from models.ai_assistant_appointment import AiAssistantAppointment
from models.ai_assistant_calendar import AiAssistantCalendar
from models.ai_assistant_conversation import AiAssistantConversation
from models.ai_assistant_document import AiAssistantDocument
from models.ai_assistant_lead import AiAssistantLead
from models.ai_assistant_mailbox import AiAssistantMailbox
from models.ai_assistant_mailbox_message import AiAssistantMailboxMessage
from models.ai_assistant_message import AiAssistantMessage
from models.ai_assistant_photo import AiAssistantPhoto
from models.ai_assistant_report import AiAssistantReport
from models.ai_assistant_request import AiAssistantRequest
from models.ai_assistant_subscription import AiAssistantSubscription
from services.ai_assistant.mailbox_service import ai_assistant_mailbox_service
from services.assistant_video_service import assistant_video_service
from services.r2_storage_service import r2_storage

logger = logging.getLogger(__name__)

# Tables whose rows carry a file key: kept until storage confirms the files are gone, so a later pass can retry.
_FILE_ROW_MODELS: tuple[type, ...] = (AiAssistantDocument, AiAssistantPhoto)
# Tables holding what visitors said, left or booked, the business's agenda and mailbox tokens, the emails read.
_VISITOR_ROW_MODELS: tuple[type, ...] = (
    AiAssistantConversation,
    AiAssistantRequest,
    AiAssistantAppointment,
    AiAssistantCalendar,
    AiAssistantMailbox,
    AiAssistantMailboxMessage,
    AiAssistantLead,
    AiAssistantReport,
)
# Knowledge entries copied from visitors or from the deleted documents.
_FORGOTTEN_KNOWLEDGE_KEYS: tuple[str, ...] = ("unanswered", "documents")


@dataclass(frozen=True)
class AssistantPurgeReport:
    """What one purge erased, and whether the file rows could go too (storage answered)."""

    file_count: int
    row_count: int
    has_erased_files: bool


class AiAssistantPurgeService:
    """Erases the files and the visitors' data of deleted assistants, at the deletion and in a catch-up pass."""

    @staticmethod
    def has_live_subscription(db: Session, assistant: AiAssistant) -> bool:
        """
        Whether the assistant is still paid for (running, or a renewal being retried): it cannot be deleted then.

        Args:
            db: Active database session.
            assistant: The assistant to delete.

        Returns:
            True while a subscription of the assistant is active or past due.
        """
        return bool(
            db.query(
                exists().where(
                    AiAssistantSubscription.ai_assistant_id == assistant.id,
                    AiAssistantSubscription.status.in_(LIVE_SUBSCRIPTION_STATUSES),
                )
            ).scalar()
        )

    async def purge(self, db: Session, assistant: AiAssistant) -> AssistantPurgeReport:
        """
        Erase a deleted assistant's files and its visitors' data; a failure is left to the next pass.

        Args:
            db: Active database session.
            assistant: The soft-deleted assistant.

        Returns:
            What was erased; ``has_erased_files`` is False when storage or the database failed.

        Raises:
            ValueError: When the assistant is not deleted (it would keep serving without its data).
        """
        if assistant.deleted_at is None:
            raise ValueError(f"Assistant {assistant.id} is not deleted: nothing of it is erased")
        documents = db.query(AiAssistantDocument).filter(AiAssistantDocument.assistant_id == assistant.id).all()
        photos = db.query(AiAssistantPhoto).filter(AiAssistantPhoto.assistant_id == assistant.id).all()
        deleted_files = await self._delete_files(assistant, self._file_keys(assistant, documents, photos))
        await ai_assistant_mailbox_service.revoke_for_erased_assistant(db, assistant)
        try:
            row_count = self._delete_visitor_rows(db, assistant)
            if deleted_files is not None:
                row_count += self._delete_file_rows(db, assistant)
                assistant.avatar_key = None
                assistant.avatar_enabled = False
                assistant.avatar_is_transparent = None
            self._forget_visitor_knowledge(assistant)
            assistant_video_service.purge_video(assistant)
            db.commit()
        except SQLAlchemyError:
            logger.warning("Assistant %s: the visitors' data could not be erased", assistant.id, exc_info=True)
            db.rollback()
            return AssistantPurgeReport(file_count=deleted_files or 0, row_count=0, has_erased_files=False)
        return AssistantPurgeReport(
            file_count=deleted_files or 0, row_count=row_count, has_erased_files=deleted_files is not None
        )

    async def purge_leftovers(self, db: Session) -> int:
        """
        Finish erasing the deleted assistants that still hold visitors' data or file rows.

        Args:
            db: Active database session.

        Returns:
            How many assistants were fully purged in this pass.
        """
        holds_data = or_(
            *(
                exists().where(model.assistant_id == AiAssistant.id)
                for model in (*_VISITOR_ROW_MODELS, *_FILE_ROW_MODELS)
            )
        )
        leftovers = db.query(AiAssistant).filter(AiAssistant.deleted_at.is_not(None), holds_data).all()
        purged = 0
        for assistant in leftovers:
            report = await self.purge(db, assistant)
            purged += int(report.has_erased_files)
        return purged

    @staticmethod
    def _file_keys(
        assistant: AiAssistant, documents: list[AiAssistantDocument], photos: list[AiAssistantPhoto]
    ) -> list[str]:
        """The storage keys the assistant owns: its documents, its visitors' photos, its video and its portrait."""
        keys = [document.storage_key for document in documents]
        keys += [photo.storage_key for photo in photos if photo.storage_key]
        keys += [
            r2_storage.assistant_video_key(assistant.slug),
            r2_storage.assistant_background_key(assistant.slug),
            r2_storage.assistant_thumbnail_key(assistant.slug),
            assistant.avatar_key or "",
        ]
        return list(dict.fromkeys(key for key in keys if key))

    @staticmethod
    async def _delete_files(assistant: AiAssistant, keys: list[str]) -> int | None:
        """
        Delete the assistant's files, and any file an interrupted upload left under its documents or portraits folder.

        Returns:
            How many keys were deleted, or None when storage failed (the rows keeping the keys must stay).
        """
        if not r2_storage.is_configured():
            # Nothing can have been stored from an environment without storage.
            return 0
        documents_folder = f"{r2_storage.DOCUMENTS_ASSISTANT_PREFIX}/{assistant.id}/"
        portraits_folder = f"{r2_storage.IMAGES_ASSISTANT_AVATARS_PREFIX}/{assistant.id}/"
        try:
            orphans = await asyncio.to_thread(r2_storage.list_objects, documents_folder)
            orphans += await asyncio.to_thread(r2_storage.list_objects, portraits_folder)
            every_key = list(dict.fromkeys([*keys, *(str(orphan["key"]) for orphan in orphans)]))
            await asyncio.to_thread(r2_storage.delete_many, every_key)
        except Exception:
            logger.warning("Assistant %s: its files could not be deleted from storage", assistant.id, exc_info=True)
            return None
        return len(every_key)

    @staticmethod
    def _delete_visitor_rows(db: Session, assistant: AiAssistant) -> int:
        """Delete the rows holding the visitors' words, contacts and bookings (messages before their conversations)."""
        conversation_ids = select(AiAssistantConversation.id).where(
            AiAssistantConversation.assistant_id == assistant.id
        )
        count = (
            db.query(AiAssistantMessage)
            .filter(AiAssistantMessage.conversation_id.in_(conversation_ids))
            .delete(synchronize_session=False)
        )
        for model in _VISITOR_ROW_MODELS:
            count += db.query(model).filter(model.assistant_id == assistant.id).delete(synchronize_session=False)
        return count

    @staticmethod
    def _delete_file_rows(db: Session, assistant: AiAssistant) -> int:
        """Delete the document and photo rows, once storage confirmed their files are gone."""
        return sum(
            db.query(model).filter(model.assistant_id == assistant.id).delete(synchronize_session=False)
            for model in _FILE_ROW_MODELS
        )

    @staticmethod
    def _forget_visitor_knowledge(assistant: AiAssistant) -> None:
        """Drop the questions visitors asked and the documents' text from the assistant's knowledge."""
        knowledge = dict(assistant.knowledge_json or {})
        if any(key in knowledge for key in _FORGOTTEN_KNOWLEDGE_KEYS):
            assistant.knowledge_json = {
                key: value for key, value in knowledge.items() if key not in _FORGOTTEN_KNOWLEDGE_KEYS
            }


ai_assistant_purge_service = AiAssistantPurgeService()
