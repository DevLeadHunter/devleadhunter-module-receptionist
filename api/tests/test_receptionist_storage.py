"""The receptionist's files on the storage page: their own kinds, and an expiry anchored on their demo like a site's."""

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from api.v1.routes.admin_storage import _classify, _expired_deliverable_keys, _slug_from_key
from devleadhunter_receptionist.enums.ai_assistant_status import AiAssistantStatus
from devleadhunter_receptionist.module import ReceptionistModule
from devleadhunter_receptionist.services.assistant_service import ai_assistant_service

_NOW = datetime(2026, 9, 9, 12, 0, 0, tzinfo=UTC)


def test_every_receptionist_key_prefix_maps_to_one_of_its_storage_kinds() -> None:
    kind_by_sample_key = {
        "videos/assistant/foo.mp4": "assistant_video",
        "images/assistant/foo.jpg": "assistant_thumbnail",
        "images/assistant-photos/2026/09/abc.jpg": "assistant_photo",
        "documents/assistant/12/abc.pdf": "assistant_document",
        "images/assistant-avatars/12/abc.webp": "assistant_avatar",
    }

    assert {key: _classify(key) for key in kind_by_sample_key} == kind_by_sample_key
    assert set(kind_by_sample_key.values()) == {kind.kind for kind in ReceptionistModule().storage_kinds()}


def test_the_receptionist_files_have_their_own_kinds_and_slug() -> None:
    assert _classify("videos/assistant/toitures-morel.mp4") == "assistant_video"
    assert _classify("images/assistant/toitures-morel.jpg") == "assistant_thumbnail"
    # A visitor's quote photo shares the start of the thumbnail prefix, not its kind.
    assert _classify("images/assistant-photos/2026/09/abc.jpg") == "assistant_photo"
    assert _slug_from_key("videos/assistant/toitures-morel.mp4") == "toitures-morel"
    assert _slug_from_key("images/assistant/toitures-morel.jpg") == "toitures-morel"
    assert _slug_from_key("images/assistant-photos/2026/09/abc.jpg") is None


def test_a_receptionist_video_expires_with_its_demo_and_a_deleted_one_is_a_leftover(db: Session) -> None:
    """Same rule as the site's: live or unsent demo kept, expired or deleted demo flagged for the purge."""
    live, expired, deleted = (
        ai_assistant_service.create(
            db, user_id=1, business_name=name, prospect_id=prospect_id, country="FR", use_brand_color=False
        )
        for prospect_id, name in ((1, "Toitures Morel"), (2, "Garage Martin"), (3, "Cabinet Meyer"))
    )
    expired.status = AiAssistantStatus.EXPIRED.value
    expired.demo_link_sent_at = _NOW - timedelta(days=30)
    expired.expires_at = _NOW - timedelta(days=9)
    deleted.deleted_at = _NOW
    db.commit()
    objects = [{"key": f"videos/assistant/{assistant.slug}.mp4"} for assistant in (live, expired, deleted)] + [
        {"key": f"images/assistant/{expired.slug}.jpg"},
        {"key": "images/assistant-photos/2026/09/abc.jpg"},
    ]

    stale = _expired_deliverable_keys(db, objects, _NOW)

    assert sorted(stale) == sorted(
        [
            f"videos/assistant/{expired.slug}.mp4",
            f"images/assistant/{expired.slug}.jpg",
            f"videos/assistant/{deleted.slug}.mp4",
        ]
    )
