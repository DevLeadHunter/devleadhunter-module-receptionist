"""
Quote by photo: re-encoding, storage, the vision contract (never a price), quotas, the request link, the purge.

R2, the vision model, the pushes and the email are mocked; the database is an in-memory SQLite.
"""

import asyncio
import importlib
import io
import pkgutil
from datetime import datetime, timedelta
from typing import Any

import pytest
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import models
import services.ai_assistant.photo_service as photo_module
import services.ai_assistant.request_service as request_module
import services.email_sending_service as email_sending_module
from core.database import Base
from enums.ai_assistant_photo import AiAssistantPhotoRejection, AiAssistantPhotoUrgency
from enums.ai_assistant_request import AiAssistantRequestChannel, AiAssistantRequestType
from enums.assistant_llm import AssistantLlmUsage
from models.ai_assistant import AiAssistant
from models.ai_assistant_conversation import AiAssistantConversation
from models.ai_assistant_photo import AiAssistantPhoto
from models.prospect_db import ProspectDB
from services.ai_assistant.assistant_service import ai_assistant_service
from services.ai_assistant.photo_service import (
    AiAssistantPhotoService,
    AiAssistantPhotoVision,
    PhotoRejectedError,
)
from services.ai_assistant.request_service import AiAssistantRequestService

for _module in pkgutil.iter_modules(models.__path__):
    importlib.import_module("models." + _module.name)

_SCRATCH = {
    "relevant": True,
    "object": "aile avant gauche d'une voiture",
    "damage": "rayure profonde, peinture à refaire",
    "urgency": "low",
    "missing_questions": ["Quelle est la marque du véhicule ?"],
    "reply": "Je vois une rayure profonde sur l'aile avant gauche, la peinture est à refaire. "
    "Quelle est la marque du véhicule ? Laissez-moi votre prénom et un téléphone pour le devis.",
}


@pytest.fixture
def engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def db(engine) -> Session:
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


class _Recorder:
    """Collects the calls of a mocked async function."""

    def __init__(self, result: Any = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.result = result

    async def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append({"args": args, **kwargs})
        return self.result


class _Model:
    """The assistant model router: answers the vision calls, not the request analysis."""

    def __init__(self, vision_result: dict[str, Any] | None) -> None:
        self.result = vision_result
        self.vision_calls: list[list[dict[str, Any]]] = []

    async def __call__(
        self, usage: AssistantLlmUsage, messages: list[dict[str, Any]], **_: Any
    ) -> dict[str, Any] | None:
        if usage is AssistantLlmUsage.VISION:
            self.vision_calls.append(messages)
            return self.result
        return None


class _Storage:
    """An in-memory R2: public URLs, deletions recorded."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.deleted: list[str] = []

    async def upload(self, key: str, data: bytes, content_type: str | None = None) -> str:
        self.objects[key] = data
        return f"https://cdn.test/{key}"

    async def delete(self, key: str) -> None:
        self.deleted.append(key)
        self.objects.pop(key, None)


@pytest.fixture
def cloud(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Mock R2, the vision model (a scratch on a car wing) and the announcement side effects."""
    storage = _Storage()
    vision = _Model(dict(_SCRATCH))
    monkeypatch.setattr(photo_module.r2_storage, "upload_bytes_async", storage.upload)
    monkeypatch.setattr(photo_module.r2_storage, "delete_async", storage.delete)
    monkeypatch.setattr(photo_module.assistant_llm_router, "complete_json", vision)
    monkeypatch.setattr(
        email_sending_module.EmailSendingService, "send_via_user_identity", _Recorder({"success": True})
    )
    monkeypatch.setattr(request_module.notification_service, "notify_assistant_lead", _Recorder())
    return {"storage": storage, "vision": vision}


def _assistant(db: Session) -> AiAssistant:
    prospect = ProspectDB(name="Carrosserie Dubois", category="Carrossier", source="google", confidence=2, user_id=7)
    db.add(prospect)
    db.commit()
    return ai_assistant_service.create(
        db, user_id=7, business_name="Carrosserie Dubois", prospect_id=prospect.id, country="FR", use_brand_color=False
    )


def _photo_bytes(*, size: tuple[int, int] = (2400, 1200), fmt: str = "PNG") -> bytes:
    image = Image.new("RGB", size, (180, 40, 40))
    buffer = io.BytesIO()
    exif = Image.Exif()
    exif[0x0112] = 1  # orientation tag, to prove metadata does not survive the re-encoding
    image.save(buffer, format=fmt, exif=exif) if fmt == "JPEG" else image.save(buffer, format=fmt)
    return buffer.getvalue()


def _receive(db: Session, assistant: AiAssistant, **overrides: Any) -> AiAssistantPhoto:
    values: dict[str, Any] = {"data": _photo_bytes(), "session_id": "session-1", "language": "fr"}
    values.update(overrides)
    return asyncio.run(AiAssistantPhotoService().receive(db, assistant=assistant, **values))


def test_a_photo_is_stored_as_a_bounded_jpeg_without_metadata() -> None:
    jpeg = AiAssistantPhotoService.normalize(_photo_bytes(size=(3000, 2000), fmt="JPEG"))

    with Image.open(io.BytesIO(jpeg)) as image:
        assert image.format == "JPEG"
        assert max(image.size) == 1600
        assert not image.getexif()


def test_a_relevant_photo_is_described_journaled_and_kept(db: Session, cloud: dict[str, Any]) -> None:
    assistant = _assistant(db)

    photo = _receive(db, assistant)

    assert photo.relevant is True
    assert photo.url and photo.url.startswith("https://cdn.test/images/assistant-photos/")
    assert (photo.object_label, photo.damage) == (
        "aile avant gauche d'une voiture",
        "rayure profonde, peinture à refaire",
    )
    assert photo.urgency == AiAssistantPhotoUrgency.LOW.value
    assert photo.reply.startswith("Je vois une rayure profonde")
    prompt = cloud["vision"].vision_calls[0]
    assert "Carrossier" in prompt[1]["content"][0]["text"]
    assert prompt[1]["content"][1]["image_url"]["url"] == photo.url
    conversation = db.query(AiAssistantConversation).one()
    assert [message.content for message in conversation.messages] == ["📷 Photo envoyée", photo.reply]


def test_an_off_topic_photo_is_refused_politely_and_deleted_at_once(db: Session, cloud: dict[str, Any]) -> None:
    cloud["vision"].result = {"relevant": False, "reply": ""}
    assistant = _assistant(db)

    photo = _receive(db, assistant)

    assert photo.relevant is False
    assert photo.url is None and photo.storage_key is None and photo.deleted_at is not None
    assert cloud["storage"].objects == {}
    assert photo.reply == AiAssistantPhotoVision.OFF_TOPIC_REPLIES["fr"]


def test_the_vision_reply_never_carries_a_price() -> None:
    answer = {**_SCRATCH, "reply": "Rayure profonde : comptez environ 250 € pour la reprise.", "damage": "150 euros"}

    analysis = AiAssistantPhotoVision.parse(answer, "en")

    assert "€" not in analysis.reply
    assert analysis.reply == AiAssistantPhotoVision.FALLBACK_REPLIES["en"]
    assert analysis.damage is None
    assert analysis.object_label == "aile avant gauche d'une voiture"


def test_without_the_vision_model_the_photo_is_kept_with_a_neutral_reply(db: Session, cloud: dict[str, Any]) -> None:
    cloud["vision"].result = None
    assistant = _assistant(db)

    photo = _receive(db, assistant, language="de")

    assert photo.relevant is None
    assert photo.url is not None
    assert photo.reply == AiAssistantPhotoVision.FALLBACK_REPLIES["de"]


def test_photos_are_refused_beyond_3_per_session_8_mb_or_unreadable(db: Session, cloud: dict[str, Any]) -> None:
    assistant = _assistant(db)
    for _ in range(3):
        _receive(db, assistant)

    with pytest.raises(PhotoRejectedError) as quota:
        _receive(db, assistant)
    with pytest.raises(PhotoRejectedError) as too_large:
        _receive(db, assistant, session_id="other", data=b"x" * (8 * 1024 * 1024 + 1))
    with pytest.raises(PhotoRejectedError) as unreadable:
        _receive(db, assistant, session_id="other", data=b"not an image")

    assert quota.value.reason is AiAssistantPhotoRejection.QUOTA
    assert too_large.value.reason is AiAssistantPhotoRejection.TOO_LARGE
    assert unreadable.value.reason is AiAssistantPhotoRejection.UNREADABLE


def test_the_session_photos_make_the_request_a_quote_by_photo(db: Session, cloud: dict[str, Any]) -> None:
    assistant = _assistant(db)
    photo = _receive(db, assistant)
    service = AiAssistantRequestService()

    request, _ = service.capture(
        db, assistant=assistant, name="Marc", contact="06 12 34 56 78", need=None, language="fr", session_id="session-1"
    )
    asyncio.run(service.follow_up(db, request, assistant))

    assert request.channel == AiAssistantRequestChannel.PHOTO.value
    assert request.type == AiAssistantRequestType.QUOTE.value
    assert service.photo_urls(request) == [photo.url]
    assert request.photos_json[0]["damage"] == "rayure profonde, peinture à refaire"
    db.refresh(photo)
    assert photo.request_id == request.id


def test_a_photo_showing_an_immediate_risk_makes_the_request_urgent(db: Session, cloud: dict[str, Any]) -> None:
    cloud["vision"].result = {**_SCRATCH, "object": "tuyau sous évier", "damage": "fuite active", "urgency": "high"}
    assistant = _assistant(db)
    _receive(db, assistant)
    service = AiAssistantRequestService()

    request, _ = service.capture(
        db, assistant=assistant, name="Léa", contact="06 12 34 56 78", need=None, language="fr", session_id="session-1"
    )
    asyncio.run(service.follow_up(db, request, assistant))

    assert request.type == AiAssistantRequestType.URGENT.value


def test_photos_leave_storage_after_90_days_and_their_links_leave_the_request(
    db: Session, cloud: dict[str, Any]
) -> None:
    assistant = _assistant(db)
    photo = _receive(db, assistant)
    request, _ = AiAssistantRequestService().capture(
        db, assistant=assistant, name="Marc", contact="06 12 34 56 78", need=None, language="fr", session_id="session-1"
    )
    service = AiAssistantPhotoService()
    later = datetime.utcnow() + timedelta(days=91)

    assert asyncio.run(service.purge_expired(db, now=datetime.utcnow())) == 0
    assert asyncio.run(service.purge_expired(db, now=later)) == 1

    db.refresh(photo)
    db.refresh(request)
    assert photo.url is None and photo.deleted_at is not None
    assert cloud["storage"].objects == {}
    assert AiAssistantRequestService.photo_urls(request) == []
    assert request.photos_json[0]["damage"] == "rayure profonde, peinture à refaire"


def test_an_off_topic_photo_whose_delete_failed_is_retried_by_the_purge(
    db: Session, cloud: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    cloud["vision"].result = {"relevant": False, "reply": "Hors sujet."}

    async def broken_delete(key: str) -> None:
        raise RuntimeError("R2 down")

    monkeypatch.setattr(photo_module.r2_storage, "delete_async", broken_delete)
    assistant = _assistant(db)
    photo = _receive(db, assistant)
    assert photo.url is None and photo.storage_key is not None and photo.deleted_at is None

    monkeypatch.setattr(photo_module.r2_storage, "delete_async", cloud["storage"].delete)
    assert asyncio.run(AiAssistantPhotoService().purge_expired(db)) == 1
    db.refresh(photo)
    assert photo.storage_key is None and photo.deleted_at is not None


def _multipart(file_bytes: bytes, **fields: str) -> tuple[bytes, str]:
    boundary = "dlh-test-boundary"
    parts = [
        f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
        for name, value in fields.items()
    ]
    parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="photo.jpg"\r\n'
        "Content-Type: image/jpeg\r\n\r\n".encode()
        + file_bytes
        + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def _visitor_request(body: bytes, content_type: str, *, declared_length: str | None = None) -> Any:
    from starlette.requests import Request

    length = str(len(body)) if declared_length is None else declared_length
    headers = [(b"content-type", content_type.encode())]
    if length:
        headers.append((b"content-length", length.encode()))

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": body, "more_body": False}

    scope = {"type": "http", "method": "POST", "headers": headers, "client": ("203.0.113.9", 4242)}
    return Request(scope, receive)


def test_the_public_route_answers_counts_the_quota_and_maps_refusals(
    db: Session, cloud: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    from fastapi import HTTPException

    from api.v1.routes.ai_assistants import submit_assistant_photo

    monkeypatch.setattr(photo_module.r2_storage, "is_configured", lambda: True)
    assistant = _assistant(db)

    def send(data: bytes, *, session_id: str = "session-9", declared_length: str | None = None) -> Any:
        body, content_type = _multipart(data, session_id=session_id, language="fr", internal="false")
        visitor = _visitor_request(body, content_type, declared_length=declared_length)
        return asyncio.run(submit_assistant_photo(assistant.slug, visitor, db=db))

    answer = send(_photo_bytes())
    refusals: dict[str, int] = {}
    for label, kwargs in {
        "unreadable": {"data": b"not an image"},
        "blank session": {"data": _photo_bytes(), "session_id": "   "},
        "no length": {"data": _photo_bytes(), "declared_length": ""},
        "too large": {"data": _photo_bytes(), "declared_length": str(9 * 1024 * 1024)},
    }.items():
        with pytest.raises(HTTPException) as refused:
            send(**kwargs)
        refusals[label] = refused.value.status_code

    assert answer.accepted is True
    assert answer.remaining == 2
    assert answer.need == "aile avant gauche d'une voiture — rayure profonde, peinture à refaire"
    assert refusals == {"unreadable": 415, "blank session": 400, "no length": 411, "too large": 413}


def test_a_photo_sent_after_the_contact_details_joins_the_request(db: Session, cloud: dict[str, Any]) -> None:
    assistant = _assistant(db)
    service = AiAssistantRequestService()
    request, _ = service.capture(
        db,
        assistant=assistant,
        name="Marc",
        contact="06 12 34 56 78",
        need="Question",
        language="fr",
        session_id="session-1",
    )

    photo = _receive(db, assistant)
    service.attach_late_photos(db, assistant_id=assistant.id, session_id="session-1")

    db.refresh(request)
    assert service.photo_urls(request) == [photo.url]
    assert request.type == AiAssistantRequestType.QUOTE.value
    assert request.channel == AiAssistantRequestChannel.PHOTO.value


def test_the_quota_starts_again_once_the_request_is_handled(db: Session, cloud: dict[str, Any]) -> None:
    assistant = _assistant(db)
    for _ in range(3):
        _receive(db, assistant)
    service = AiAssistantRequestService()
    request, _ = service.capture(
        db, assistant=assistant, name="Marc", contact="06 12 34 56 78", need=None, language="fr", session_id="session-1"
    )
    photos = AiAssistantPhotoService()
    assert photos.kept_count(db, assistant.id, "session-1") == 3

    service.mark_handled(db, request)

    assert photos.kept_count(db, assistant.id, "session-1") == 0
    assert photos.kept_count(db, assistant.id, "session-1", now=datetime.utcnow() + timedelta(days=2)) == 0


def test_a_huge_canvas_is_refused_before_decoding_and_no_comment_survives() -> None:
    bomb = io.BytesIO()
    Image.new("1", (8000, 8000)).save(bomb, format="PNG")
    commented = io.BytesIO()
    Image.new("RGB", (400, 300), (10, 20, 30)).save(commented, format="JPEG", comment=b"iPhone de Marc Dubois")

    with pytest.raises(PhotoRejectedError) as refused:
        AiAssistantPhotoService.normalize(bomb.getvalue())
    clean = AiAssistantPhotoService.normalize(commented.getvalue())

    assert refused.value.reason is AiAssistantPhotoRejection.TOO_LARGE
    assert b"Marc Dubois" not in clean


def test_an_off_topic_verdict_is_read_whatever_its_json_type() -> None:
    for verdict in (False, "false", "False", "0", 0):
        assert AiAssistantPhotoVision.parse({"relevant": verdict, "reply": "Hors sujet."}, "fr").relevant is False
    assert AiAssistantPhotoVision.parse({"reply": "Je vois une fuite."}, "fr").relevant is None
