"""The receptionist's tables hold visitor and business text: they are created in utf8mb4 whatever the schema default."""

import pytest
from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateTable

from core.database import Base


@pytest.mark.parametrize(
    "table",
    [
        "ai_assistant_conversations",
        "ai_assistant_messages",
        "ai_assistant_requests",
        "ai_assistant_photos",
        "ai_assistant_reports",
        "ai_assistant_calendars",
        "ai_assistant_appointments",
        "ai_assistant_documents",
    ],
)
def test_the_table_is_created_in_utf8mb4(table: str) -> None:
    ddl = str(CreateTable(Base.metadata.tables[table]).compile(dialect=mysql.dialect()))

    assert "CHARSET=utf8mb4" in ddl and "COLLATE utf8mb4_unicode_ci" in ddl
