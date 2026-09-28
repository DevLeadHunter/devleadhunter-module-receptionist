"""The receptionist's field limits: the API accepts what the services keep, and what the columns hold."""

import pytest
from pydantic import BaseModel, ValidationError
from sqlalchemy import String
from sqlalchemy.orm import InstrumentedAttribute

from models.ai_assistant import AiAssistant
from models.ai_assistant_appointment import AiAssistantAppointment
from models.ai_assistant_calendar import AiAssistantCalendar
from models.ai_assistant_conversation import AiAssistantConversation
from models.ai_assistant_request import AiAssistantRequest
from schemas.ai_assistant import AiAssistantChatRequest, AiAssistantLeadRequest, AiAssistantUpdateRequest
from schemas.ai_assistant_client_space import AiAssistantClientCalendarUpdate
from services.ai_assistant.conversation_service import MAX_STORED_MESSAGE_CHARS
from services.ai_assistant.field_limits import (
    LABEL_MAX_CHARS,
    LONG_TEXT_MAX_CHARS,
    SESSION_ID_MAX_CHARS,
    SHORT_TEXT_MAX_CHARS,
)


@pytest.mark.parametrize(
    ("column", "limit"),
    [
        (AiAssistant.business_name, SHORT_TEXT_MAX_CHARS),
        (AiAssistant.email, SHORT_TEXT_MAX_CHARS),
        (AiAssistant.tone, SHORT_TEXT_MAX_CHARS),
        (AiAssistant.assistant_name, LABEL_MAX_CHARS),
        (AiAssistantRequest.name, SHORT_TEXT_MAX_CHARS),
        (AiAssistantRequest.contact, SHORT_TEXT_MAX_CHARS),
        (AiAssistantRequest.session_id, SESSION_ID_MAX_CHARS),
        (AiAssistantConversation.session_id, SESSION_ID_MAX_CHARS),
        (AiAssistantAppointment.type_label, LABEL_MAX_CHARS),
        (AiAssistantCalendar.calendar_id, SHORT_TEXT_MAX_CHARS),
    ],
)
def test_every_bounded_field_fits_its_column(column: InstrumentedAttribute[str], limit: int) -> None:
    column_type = column.property.columns[0].type

    assert isinstance(column_type, String) and column_type.length == limit


@pytest.mark.parametrize(
    ("schema", "field", "limit", "other_fields"),
    [
        (AiAssistantLeadRequest, "name", SHORT_TEXT_MAX_CHARS, {"contact": "06 11 22 33 44"}),
        (AiAssistantLeadRequest, "need", LONG_TEXT_MAX_CHARS, {"name": "Julie", "contact": "06 11 22 33 44"}),
        (AiAssistantChatRequest, "session_id", SESSION_ID_MAX_CHARS, {}),
        (AiAssistantUpdateRequest, "assistant_name", LABEL_MAX_CHARS, {}),
        (AiAssistantClientCalendarUpdate, "calendar_id", SHORT_TEXT_MAX_CHARS, {}),
    ],
)
def test_the_api_accepts_a_field_up_to_its_limit_and_no_further(
    schema: type[BaseModel], field: str, limit: int, other_fields: dict[str, str]
) -> None:
    schema(**other_fields, **{field: "a" * limit})
    with pytest.raises(ValidationError):
        schema(**other_fields, **{field: "a" * (limit + 1)})


def test_a_stored_chat_turn_keeps_what_a_visitor_may_write() -> None:
    assert MAX_STORED_MESSAGE_CHARS == LONG_TEXT_MAX_CHARS
