"""The migrations of the receptionist videos built by the PC: a server render left unfinished fails, the new column
comes once."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import devleadhunter_receptionist.migrations.add_ai_assistant_video_desktop_requested_at as assistant_request_migration
import migrations.fail_unfinished_server_videos as unfinished_videos_migration
from devleadhunter_receptionist.models.ai_assistant import AiAssistant


def _bare_engine() -> Engine:
    return create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)


def test_a_receptionist_video_a_server_render_left_unfinished_ends_failed_once(
    db: Session, engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    assistant = AiAssistant(user_id=1, slug="toitures-morel", business_name="Toitures Morel", video_status="generating")
    db.add(assistant)
    db.commit()
    monkeypatch.setattr(unfinished_videos_migration, "engine", engine)

    unfinished_videos_migration.run_migration()
    unfinished_videos_migration.run_migration()

    db.expire_all()
    assert assistant.video_status == "failed"
    assert assistant.video_error.startswith("La génération sur le serveur n'existe plus")


def test_the_receptionist_request_column_is_added_once(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = _bare_engine()
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE ai_assistants (id INTEGER PRIMARY KEY, slug VARCHAR(120))"))
        conn.execute(text("INSERT INTO ai_assistants (id, slug) VALUES (1, 'toitures-morel')"))
        conn.commit()
    monkeypatch.setattr(assistant_request_migration, "engine", engine)

    assistant_request_migration.run_migration()
    assistant_request_migration.run_migration()

    columns = {column["name"] for column in inspect(engine).get_columns("ai_assistants")}
    with engine.connect() as conn:
        requested_at = conn.execute(text("SELECT video_desktop_requested_at FROM ai_assistants")).scalar_one()
    assert "video_desktop_requested_at" in columns
    assert requested_at is None
