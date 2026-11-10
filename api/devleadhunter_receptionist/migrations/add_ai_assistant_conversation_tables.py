"""Create the ai_assistant_conversations + ai_assistant_messages tables (server-side chat journal)."""

from __future__ import annotations

from core.database import engine
from devleadhunter_receptionist.models.ai_assistant_conversation import AiAssistantConversation
from devleadhunter_receptionist.models.ai_assistant_message import AiAssistantMessage


def run_migration() -> None:
    """Create both journal tables if they do not exist (the conversation first, the messages reference it)."""
    AiAssistantConversation.__table__.create(engine, checkfirst=True)
    AiAssistantMessage.__table__.create(engine, checkfirst=True)


if __name__ == "__main__":
    run_migration()
    print("ai_assistant_conversations + ai_assistant_messages tables ensured.")
