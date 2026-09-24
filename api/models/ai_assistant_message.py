"""One turn of a visitor's conversation with an AI assistant."""

from datetime import datetime

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import UTF8MB4_TABLE_OPTIONS, Base
from models.ai_assistant_conversation import AiAssistantConversation


class AiAssistantMessage(Base):
    """The visitor's message or the assistant's reply, in the order it was exchanged."""

    __tablename__ = "ai_assistant_messages"
    __table_args__ = (UTF8MB4_TABLE_OPTIONS,)

    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("ai_assistant_conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)

    conversation: Mapped[AiAssistantConversation] = relationship("AiAssistantConversation", back_populates="messages")
