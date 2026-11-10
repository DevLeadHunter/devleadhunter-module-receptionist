"""Where a piece of an assistant's knowledge comes from."""

from enum import Enum


class AiAssistantKnowledgeSource(str, Enum):
    """A page of the business's website, or a document it gave (PDF)."""

    PAGE = "page"
    DOCUMENT = "document"
