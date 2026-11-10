"""A document a business gave its assistant (price list, terms, brochure, FAQ), read from a PDF."""

from datetime import datetime

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.dialects.mysql import MEDIUMTEXT
from sqlalchemy.orm import Mapped, mapped_column

from core.database import UTF8MB4_TABLE_OPTIONS, Base


class AiAssistantDocument(Base):
    """The file (kept in R2), its extracted text, and whether the assistant reads it.

    The assistant reads the enabled documents' text from ``knowledge_json['documents']``, rebuilt whenever a
    document is added, toggled or deleted; the text here lets a document come back without extracting it again.
    """

    __tablename__ = "ai_assistant_documents"
    __table_args__ = (UTF8MB4_TABLE_OPTIONS,)

    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    assistant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    # The name shown to the operator and cited to visitors (« Tarifs 2026.pdf »).
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pages: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    text: Mapped[str] = mapped_column(Text().with_variant(MEDIUMTEXT, "mysql"), nullable=False)
    # The text was cut to its bound (a long document).
    truncated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
