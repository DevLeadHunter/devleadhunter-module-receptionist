"""
A deleted receptionist leaves nothing of its visitors behind: its files on R2 and the rows holding their data are
erased, its own row stays for the sales history, and a receptionist still paid for cannot be deleted. The bucket is a
fake in memory; the database is an in-memory SQLite with the real models.
"""

import asyncio
from collections.abc import Iterator
from datetime import datetime
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

import api.v1.routes.ai_assistant_requests as request_routes
import api.v1.routes.ai_assistants as owner_routes
import services.ai_assistant.assistant_purge as purge_module
from models.ai_assistant import AiAssistant
from models.ai_assistant_appointment import AiAssistantAppointment
from models.ai_assistant_calendar import AiAssistantCalendar
from models.ai_assistant_conversation import AiAssistantConversation
from models.ai_assistant_document import AiAssistantDocument
from models.ai_assistant_lead import AiAssistantLead
from models.ai_assistant_message import AiAssistantMessage
from models.ai_assistant_photo import AiAssistantPhoto
from models.ai_assistant_report import AiAssistantReport
from models.ai_assistant_request import AiAssistantRequest
from models.ai_assistant_subscription import AiAssistantSubscription
from models.prospect_db import ProspectDB
from models.user import User
from services.ai_assistant.assistant_purge import ai_assistant_purge_service
from services.ai_assistant.assistant_service import ai_assistant_service
from services.r2_storage_service import R2StorageService

_OPERATOR = SimpleNamespace(id=7, email="operateur@dibodev.fr")
# Every table a purge empties, per assistant.
_ERASED_MODELS: tuple[type, ...] = (
    AiAssistantConversation,
    AiAssistantRequest,
    AiAssistantAppointment,
    AiAssistantCalendar,
    AiAssistantLead,
    AiAssistantReport,
    AiAssistantDocument,
    AiAssistantPhoto,
)


class FakeBucket:
    """An R2 bucket in memory: the keys it holds, and whether it answers."""

    DOCUMENTS_ASSISTANT_PREFIX = R2StorageService.DOCUMENTS_ASSISTANT_PREFIX

    def __init__(self) -> None:
        self.keys: set[str] = set()
        self.is_down = False

    def is_configured(self) -> bool:
        return True

    def list_objects(self, prefix: str = "") -> list[dict[str, Any]]:
        if self.is_down:
            raise ConnectionError("R2 unreachable")
        return [{"key": key} for key in sorted(self.keys) if key.startswith(prefix)]

    def delete_many(self, keys: list[str]) -> None:
        if self.is_down:
            raise ConnectionError("R2 unreachable")
        self.keys -= set(keys)

    @staticmethod
    def assistant_video_key(slug: str) -> str:
        return R2StorageService.assistant_video_key(slug)

    @staticmethod
    def assistant_background_key(slug: str) -> str:
        return R2StorageService.assistant_background_key(slug)

    @staticmethod
    def assistant_thumbnail_key(slug: str) -> str:
        return R2StorageService.assistant_thumbnail_key(slug)


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    session = sessionmaker(bind=engine)()
    session.add(User(id=7, name="Dibodev", email="operateur@dibodev.fr", hashed_password="x"))
    session.commit()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def bucket(monkeypatch: pytest.MonkeyPatch) -> FakeBucket:
    fake = FakeBucket()
    monkeypatch.setattr(purge_module, "r2_storage", fake)
    return fake


def _assistant_with_visitors(db: Session, bucket: FakeBucket, business_name: str) -> AiAssistant:
    """A receptionist with a document, a photo, a conversation, a request, a booking, an agenda, a lead and a video."""
    prospect = ProspectDB(name=business_name, category="Couvreur", source="google", confidence=2, user_id=7)
    db.add(prospect)
    db.commit()
    assistant = ai_assistant_service.create(
        db, user_id=7, business_name=business_name, prospect_id=prospect.id, country="FR", use_brand_color=False
    )
    assistant.knowledge_json = {
        **(assistant.knowledge_json or {}),
        "unanswered": [{"question": "Venez-vous le dimanche ?", "count": 1}],
        "documents": [{"id": 1, "name": "Tarifs.pdf", "text": "Tarifs 2026"}],
        "faq": [{"question": "Horaires ?", "answer": "De 8 h à 18 h."}],
    }
    assistant.video_status = "ready"
    document_key = f"documents/assistant/{assistant.id}/tarifs.pdf"
    photo_key = f"images/assistant-photos/2026/09/{assistant.slug}.jpg"
    request = AiAssistantRequest(
        user_id=7, assistant_id=assistant.id, name="Marc Dubois", contact="06 98 76 54 32", photos_json=[photo_key]
    )
    db.add(request)
    db.commit()
    db.add_all(
        [
            AiAssistantDocument(
                user_id=7, assistant_id=assistant.id, name="Tarifs.pdf", storage_key=document_key, text="Tarifs"
            ),
            AiAssistantPhoto(
                user_id=7, assistant_id=assistant.id, storage_key=photo_key, url=f"https://r2.example/{photo_key}"
            ),
            AiAssistantConversation(
                user_id=7,
                assistant_id=assistant.id,
                session_id=f"session-{assistant.id}",
                messages=[AiAssistantMessage(role="user", content="Mes tuiles ont bougé")],
            ),
            AiAssistantAppointment(
                user_id=7,
                assistant_id=assistant.id,
                request_id=request.id,
                starts_at=datetime(2026, 10, 2, 9, 0),
                ends_at=datetime(2026, 10, 2, 10, 0),
                visitor_email="marc@example.fr",
            ),
            AiAssistantCalendar(user_id=7, assistant_id=assistant.id, refresh_token_encrypted="jeton-chiffre"),
            AiAssistantLead(user_id=7, assistant_id=assistant.id, name="Julie", contact="julie@example.fr"),
            AiAssistantReport(user_id=7, assistant_id=assistant.id, month="2026-08", stats_json={"requests": 3}),
        ]
    )
    db.commit()
    bucket.keys |= {
        document_key,
        f"documents/assistant/{assistant.id}/upload-interrompu.pdf",
        photo_key,
        R2StorageService.assistant_video_key(assistant.slug),
        R2StorageService.assistant_background_key(assistant.slug),
        R2StorageService.assistant_thumbnail_key(assistant.slug),
    }
    return assistant


def _rows_of(db: Session, assistant: AiAssistant) -> dict[str, int]:
    """How many rows each purged table still holds for the assistant (messages through its conversations)."""
    counts = {
        model.__tablename__: db.query(model).filter(model.assistant_id == assistant.id).count()
        for model in _ERASED_MODELS
    }
    counts["ai_assistant_messages"] = (
        db.query(AiAssistantMessage)
        .join(AiAssistantConversation, AiAssistantConversation.id == AiAssistantMessage.conversation_id)
        .filter(AiAssistantConversation.assistant_id == assistant.id)
        .count()
    )
    return counts


def _keys_of(bucket: FakeBucket, assistant: AiAssistant) -> set[str]:
    """The bucket keys that belong to the assistant (its id folder or its slug)."""
    return {key for key in bucket.keys if f"/{assistant.id}/" in key or assistant.slug in key}


def test_deleting_erases_the_files_and_the_visitors_data_and_keeps_the_sales_history(
    db: Session, bucket: FakeBucket
) -> None:
    deleted = _assistant_with_visitors(db, bucket, "Toitures Morel")
    kept = _assistant_with_visitors(db, bucket, "Couverture Petit")
    ended = AiAssistantSubscription(user_id=7, ai_assistant_id=deleted.id, amount_cents=7900, status="canceled")
    db.add(ended)
    db.commit()

    asyncio.run(owner_routes.delete_assistant(deleted.id, _OPERATOR, db))

    db.refresh(deleted)
    assert deleted.deleted_at is not None and deleted.status == "deleted"
    assert set(_rows_of(db, deleted).values()) == {0}
    assert _keys_of(bucket, deleted) == set()
    assert "unanswered" not in deleted.knowledge_json and "documents" not in deleted.knowledge_json
    assert deleted.knowledge_json["faq"] and deleted.video_status is None
    assert db.get(AiAssistantSubscription, ended.id) is not None
    assert set(_rows_of(db, kept).values()) == {1}
    assert len(_keys_of(bucket, kept)) == 6


def test_a_receptionist_still_paid_for_cannot_be_deleted(db: Session, bucket: FakeBucket) -> None:
    for status in ("active", "past_due"):
        assistant = _assistant_with_visitors(db, bucket, f"Garage {status}")
        db.add(AiAssistantSubscription(user_id=7, ai_assistant_id=assistant.id, amount_cents=7900, status=status))
        db.commit()

        with pytest.raises(HTTPException) as caught:
            asyncio.run(owner_routes.delete_assistant(assistant.id, _OPERATOR, db))

        db.refresh(assistant)
        assert (caught.value.status_code, caught.value.detail) == (
            409,
            "Résiliez d'abord l'abonnement de cette réceptionniste.",
        )
        assert assistant.deleted_at is None
        assert set(_rows_of(db, assistant).values()) == {1}
        assert len(_keys_of(bucket, assistant)) == 6


def test_when_storage_fails_the_file_rows_wait_for_the_next_pass(db: Session, bucket: FakeBucket) -> None:
    assistant = _assistant_with_visitors(db, bucket, "Toitures Morel")
    bucket.is_down = True

    asyncio.run(owner_routes.delete_assistant(assistant.id, _OPERATOR, db))

    rows = _rows_of(db, assistant)
    assert (rows["ai_assistant_documents"], rows["ai_assistant_photos"]) == (1, 1)
    assert rows["ai_assistant_requests"] == rows["ai_assistant_conversations"] == rows["ai_assistant_messages"] == 0
    assert len(_keys_of(bucket, assistant)) == 6

    bucket.is_down = False
    assert asyncio.run(ai_assistant_purge_service.purge_leftovers(db)) == 1
    assert set(_rows_of(db, assistant).values()) == {0}
    assert _keys_of(bucket, assistant) == set()
    assert asyncio.run(ai_assistant_purge_service.purge_leftovers(db)) == 0


def test_the_catch_up_pass_erases_the_receptionists_deleted_before_the_purge_only(
    db: Session, bucket: FakeBucket
) -> None:
    deleted_long_ago = _assistant_with_visitors(db, bucket, "Toitures Morel")
    deleted_long_ago.status = "deleted"
    deleted_long_ago.deleted_at = datetime(2026, 9, 1)
    live = _assistant_with_visitors(db, bucket, "Couverture Petit")
    db.commit()

    assert asyncio.run(ai_assistant_purge_service.purge_leftovers(db)) == 1
    assert set(_rows_of(db, deleted_long_ago).values()) == {0}
    assert set(_rows_of(db, live).values()) == {1}
    with pytest.raises(ValueError):
        asyncio.run(ai_assistant_purge_service.purge(db, live))


def test_the_legacy_leads_of_a_deleted_receptionist_leave_the_dashboard(db: Session, bucket: FakeBucket) -> None:
    kept = _assistant_with_visitors(db, bucket, "Couverture Petit")
    deleted_long_ago = _assistant_with_visitors(db, bucket, "Toitures Morel")
    deleted_long_ago.deleted_at = datetime(2026, 9, 1)
    db.commit()

    leads = asyncio.run(request_routes.list_assistant_leads(_OPERATOR, db)).leads

    assert [lead.assistant_id for lead in leads] == [kept.id]
