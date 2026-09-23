"""
Migration: add the prospection-video columns to ``ai_assistants``.

The AI assistant gets its own prospection video (a webcam speech about the assistant plus a
recording of the widget answering a question) — a pipeline distinct from the site video. These
columns track its generation lifecycle, mirroring ``demo_sites.video_status`` / ``video_error`` /
``video_generated_at``.

Run with:
    python migrations/add_ai_assistant_video.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from core.database import engine


def run_migration() -> None:
    print("Running migration: add_ai_assistant_video")
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE ai_assistants ADD COLUMN IF NOT EXISTS video_status VARCHAR(16) NULL"))
        conn.execute(text("ALTER TABLE ai_assistants ADD COLUMN IF NOT EXISTS video_error TEXT NULL"))
        conn.execute(text("ALTER TABLE ai_assistants ADD COLUMN IF NOT EXISTS video_generated_at DATETIME NULL"))
        conn.commit()
    print("  + ai_assistants.video_status / video_error / video_generated_at")
    print("Migration completed successfully.")


if __name__ == "__main__":
    print("=" * 60)
    print("Migration: Add ai_assistants prospection-video columns")
    print("=" * 60)
    run_migration()
