"""Contracts of an assistant's FAQ (the answers the business writes) and of the questions it could not answer."""

from datetime import datetime

from pydantic import BaseModel, Field


class AiAssistantFaqEntry(BaseModel):
    """A question and the answer the business wrote for it; the assistant repeats it as is."""

    question: str
    answer: str
    created_at: datetime | None = None


class AiAssistantUnansweredEntry(BaseModel):
    """A question visitors asked that the assistant's knowledge could not answer."""

    question: str
    # How many times it was asked (the same question, case and accents aside).
    count: int
    first_seen: datetime | None = None
    last_seen: datetime | None = None


class AiAssistantFaqResponse(BaseModel):
    """The FAQ and the unanswered questions of one assistant."""

    faq: list[AiAssistantFaqEntry] = Field(default_factory=list)
    unanswered: list[AiAssistantUnansweredEntry] = Field(default_factory=list)


class AiAssistantFaqEntryRequest(BaseModel):
    """A question and its answer, written or rewritten by the business (cut to 200 and 1,000 characters)."""

    question: str = Field(..., max_length=4000)
    answer: str = Field(..., max_length=8000)
