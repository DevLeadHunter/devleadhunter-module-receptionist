"""Add ``ai_assistants.client_link_version``: the version its client-space links are signed with."""

from __future__ import annotations

from sqlalchemy import inspect, text

from core.database import engine


def run_migration() -> None:
    """Add the column if it is missing: every row reads 0, so the links already sent keep opening (re-runnable)."""
    columns = {column["name"] for column in inspect(engine).get_columns("ai_assistants")}
    if "client_link_version" in columns:
        return
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE ai_assistants ADD COLUMN client_link_version INT NOT NULL DEFAULT 0"))
        conn.commit()


if __name__ == "__main__":
    run_migration()
