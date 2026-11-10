"""Create ai_assistants table."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.database import engine
from models.ai_assistant import AiAssistant


def run_migration() -> None:
    """Create the ai_assistants table if it does not exist."""
    AiAssistant.__table__.create(engine, checkfirst=True)


if __name__ == "__main__":
    run_migration()
    print("ai_assistants table ensured.")
