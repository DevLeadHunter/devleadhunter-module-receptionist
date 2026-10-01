"""
A receptionist's own portrait: normalised at upload, stored on R2 under a new key, served to the widget, the launcher
and the spaces, removed with the assistant. Storage is mocked; the database is an in-memory SQLite.
"""

import asyncio
import io
import math
from typing import Any

import pytest
from fastapi import UploadFile
from PIL import Image
from sqlalchemy.orm import Session
from starlette.datastructures import Headers

import api.v1.routes.admin_storage as storage_routes
import services.ai_assistant.avatar_service as avatar_module
from enums.storage_object_kind import StorageObjectKind
from models.ai_assistant import AiAssistant
from models.prospect_db import ProspectDB
from models.user import User
from services.ai_assistant.assistant_purge import AiAssistantPurgeService
from services.ai_assistant.assistant_service import ai_assistant_service
from services.ai_assistant.avatar_service import AiAssistantAvatarService, AvatarRefusal, ai_assistant_avatar_service


class _FakeStorage:
    """Records what the avatar service stores and deletes."""

    def __init__(self) -> None:
        self.uploaded: dict[str, bytes] = {}
        self.deleted: list[str] = []

    async def upload_bytes_async(self, key: str, data: bytes, content_type: str | None = None) -> str:
        self.uploaded[key] = data
        return key

    async def delete_async(self, key: str) -> None:
        self.deleted.append(key)


@pytest.fixture
def storage(monkeypatch: pytest.MonkeyPatch) -> _FakeStorage:
    fake = _FakeStorage()
    monkeypatch.setattr(avatar_module.r2_storage, "upload_bytes_async", fake.upload_bytes_async)
    monkeypatch.setattr(avatar_module.r2_storage, "delete_async", fake.delete_async)
    monkeypatch.setattr(avatar_module.r2_storage, "public_url", lambda key: f"https://cdn.test/{key}")
    return fake


def _assistant(db: Session) -> AiAssistant:
    db.add(User(id=7, name="Dibodev", email="operateur@dibodev.fr", hashed_password="x"))
    prospect = ProspectDB(name="Toitures Morel", category="Couvreur", source="google", confidence=2, user_id=7)
    db.add(prospect)
    db.commit()
    return ai_assistant_service.create(
        db, user_id=7, business_name="Toitures Morel", prospect_id=prospect.id, country="FR", use_brand_color=False
    )


def _image(size: tuple[int, int], *, image_format: str, transparent: bool = False) -> bytes:
    mode = "RGBA" if transparent else "RGB"
    background = (0, 0, 0, 0) if transparent else (200, 160, 120)
    image = Image.new(mode, size, background)
    for x in range(size[0] // 4, 3 * size[0] // 4):
        for y in range(size[1] // 4, 3 * size[1] // 4):
            image.putpixel((x, y), (180, 40, 30, 255) if transparent else (180, 40, 30))
    buffer = io.BytesIO()
    image.save(buffer, format=image_format)
    return buffer.getvalue()


def _photo(size: tuple[int, int]) -> bytes:
    # Edges of every colour, as a real photo has.
    image = Image.new("RGB", size)
    image.putdata([(x * 255 // size[0], y * 255 // size[1], 90) for y in range(size[1]) for x in range(size[0])])
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=95)
    return buffer.getvalue()


def _fully_transparent_png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGBA", (64, 64), (0, 0, 0, 0)).save(buffer, format="PNG")
    return buffer.getvalue()


def _upload(data: bytes, content_type: str) -> UploadFile:
    return UploadFile(file=io.BytesIO(data), filename="portrait", headers=Headers({"content-type": content_type}))


def _decoded(data: bytes) -> Image.Image:
    image = Image.open(io.BytesIO(data))
    image.load()
    return image


def test_a_photo_is_cropped_to_a_square_and_a_cut_out_logo_fitted_whole_on_transparency() -> None:
    photo, photo_is_transparent = AiAssistantAvatarService.normalized(_photo((800, 600)))
    logo, logo_is_transparent = AiAssistantAvatarService.normalized(
        _image((300, 300), image_format="PNG", transparent=True)
    )

    assert photo_is_transparent is False and _decoded(photo).size == (512, 512)
    assert logo_is_transparent is True
    fitted = _decoded(logo).convert("RGBA")
    assert fitted.size == (512, 512)
    # The corner is the disc behind it, the centre the logo.
    assert fitted.getpixel((2, 2))[3] == 0 and fitted.getpixel((256, 256))[3] == 255


def test_a_cut_out_logo_is_trimmed_of_its_margins_and_kept_whole_inside_the_disc() -> None:
    # A square mark in the middle of a large transparent canvas, as logos are often exported.
    portrait, _ = AiAssistantAvatarService.normalized(_image((1000, 1000), image_format="PNG", transparent=True))

    fitted = _decoded(portrait).convert("RGBA")
    visible = [(index % 512, index // 512) for index, pixel in enumerate(fitted.getdata()) if pixel[3] > 16]
    # Scaled up to the disc rather than left at its size in the canvas...
    assert min(x for x, _ in visible) < 256 - 140 and max(x for x, _ in visible) > 256 + 140
    # ...yet no corner of the square leaves the disc.
    assert max(math.hypot(x + 0.5 - 256, y + 0.5 - 256) for x, y in visible) <= 256


def test_a_logo_on_a_plain_background_sits_whole_on_a_disc_of_that_colour_whatever_its_format() -> None:
    # A wide mark on a plain sandy background, as a logo exported in JPEG.
    portrait, is_transparent = AiAssistantAvatarService.normalized(_image((1200, 300), image_format="JPEG"))

    fitted = _decoded(portrait).convert("RGB")
    assert is_transparent is False
    assert all(abs(a - b) <= 12 for a, b in zip(fitted.getpixel((4, 4)), (200, 160, 120), strict=True))
    marked = [
        (index % 512, index // 512) for index, pixel in enumerate(fitted.getdata()) if pixel[1] < 100 and pixel[0] > 140
    ]
    assert max(x for x, _ in marked) - min(x for x, _ in marked) > 300
    assert max(math.hypot(x + 0.5 - 256, y + 0.5 - 256) for x, y in marked) <= 256


def test_a_wide_photo_is_cropped_rather_than_fitted() -> None:
    portrait, is_transparent = AiAssistantAvatarService.normalized(_photo((1200, 600)))

    fitted = _decoded(portrait).convert("RGB")
    assert is_transparent is False and fitted.size == (512, 512)
    # No plain margin around it: the photo fills the square up to its corners.
    assert fitted.getpixel((2, 2)) != fitted.getpixel((509, 2)) != fitted.getpixel((2, 509))


@pytest.mark.parametrize(
    ("data", "content_type", "is_too_large"),
    [
        (b"%PDF-1.4", "application/pdf", False),
        (b"not an image at all", "image/png", False),
        (b"", "image/png", False),
        (_fully_transparent_png(), "image/png", False),
        (b"x" * (2 * 1024 * 1024 + 1), "image/jpeg", True),
    ],
    ids=["pdf", "unreadable", "empty", "fully-transparent", "over-2-mb"],
)
def test_a_file_the_portrait_cannot_take_is_refused_with_its_reason(
    db: Session, storage: _FakeStorage, data: bytes, content_type: str, is_too_large: bool
) -> None:
    assistant = _assistant(db)

    with pytest.raises(AvatarRefusal) as refusal:
        asyncio.run(ai_assistant_avatar_service.store(db, assistant, _upload(data, content_type)))

    assert refusal.value.is_too_large is is_too_large
    assert storage.uploaded == {} and assistant.avatar_key is None


def test_a_new_portrait_replaces_the_previous_one_and_clearing_gives_the_casting_back(
    db: Session, storage: _FakeStorage
) -> None:
    assistant = _assistant(db)

    asyncio.run(
        ai_assistant_avatar_service.store(db, assistant, _upload(_image((640, 640), image_format="PNG"), "image/png"))
    )
    first_key = assistant.avatar_key
    asyncio.run(
        ai_assistant_avatar_service.store(
            db, assistant, _upload(_image((400, 400), image_format="PNG", transparent=True), "image/png")
        )
    )

    assert first_key is not None and first_key.startswith(f"images/assistant-avatars/{assistant.id}/")
    assert assistant.avatar_key != first_key and assistant.avatar_is_transparent is True
    assert storage.deleted == [first_key]
    assert ai_assistant_avatar_service.public_url(assistant) == f"https://cdn.test/{assistant.avatar_key}"

    ai_assistant_service.update(db, assistant, {"avatar_enabled": True})
    second_key = assistant.avatar_key
    asyncio.run(ai_assistant_avatar_service.clear(db, assistant))

    assert assistant.avatar_key is None and assistant.avatar_is_transparent is None
    assert assistant.avatar_enabled is False
    assert storage.deleted == [first_key, second_key]
    assert ai_assistant_avatar_service.public_url(assistant) is None


def test_the_image_stays_at_hand_and_shows_only_once_chosen(db: Session, storage: _FakeStorage) -> None:
    assistant = _assistant(db)
    with pytest.raises(ValueError):
        ai_assistant_service.update(db, assistant, {"avatar_enabled": True})

    logo = _image((400, 400), image_format="PNG", transparent=True)
    asyncio.run(ai_assistant_avatar_service.store(db, assistant, _upload(logo, "image/png")))
    ai_assistant_service.update(db, assistant, {"avatar_background": "#f4e9dc"})

    # Sent but not chosen: the owner sees it in its card, the visitors still see the casting face.
    assert ai_assistant_avatar_service.public_url(assistant) is not None
    assert ai_assistant_avatar_service.shown_url(assistant) is None
    assert ai_assistant_avatar_service.shown_background(assistant) is None

    ai_assistant_service.update(db, assistant, {"avatar_enabled": True})
    assert ai_assistant_avatar_service.shown_url(assistant) == ai_assistant_avatar_service.public_url(assistant)
    assert ai_assistant_avatar_service.shown_background(assistant) == "#f4e9dc"

    ai_assistant_service.update(db, assistant, {"avatar_enabled": False})
    assert ai_assistant_avatar_service.shown_url(assistant) is None
    assert assistant.avatar_key is not None


def test_a_photo_covers_its_disc_so_no_colour_is_served_with_it(db: Session, storage: _FakeStorage) -> None:
    assistant = _assistant(db)
    asyncio.run(ai_assistant_avatar_service.store(db, assistant, _upload(_photo((640, 480)), "image/jpeg")))
    ai_assistant_service.update(db, assistant, {"avatar_background": "#f4e9dc", "avatar_enabled": True})

    assert ai_assistant_avatar_service.shown_url(assistant) is not None
    assert ai_assistant_avatar_service.shown_background(assistant) is None


def test_the_disc_colour_is_a_hex_colour_or_the_accent_tint(db: Session) -> None:
    assistant = _assistant(db)

    ai_assistant_service.update(db, assistant, {"avatar_background": "#F4E9DC"})
    assert assistant.avatar_background == "#f4e9dc"
    ai_assistant_service.update(db, assistant, {"avatar_background": ""})
    assert assistant.avatar_background is None
    with pytest.raises(ValueError):
        ai_assistant_service.update(db, assistant, {"avatar_background": "rouge"})


def test_the_portrait_goes_with_the_deleted_assistant_and_files_under_its_own_kind() -> None:
    assistant = AiAssistant(id=3, slug="toitures-morel", avatar_key="images/assistant-avatars/3/abc.webp")

    keys: list[Any] = AiAssistantPurgeService._file_keys(assistant, [], [])

    assert "images/assistant-avatars/3/abc.webp" in keys
    assert storage_routes._classify("images/assistant-avatars/3/abc.webp") is StorageObjectKind.ASSISTANT_AVATAR
    assert storage_routes._classify("images/assistant-photos/2026/10/abc.jpg") is StorageObjectKind.ASSISTANT_PHOTO
