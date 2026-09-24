"""Contracts of an assistant's knowledge sources: its website pages, its Google listing, its documents."""

from datetime import datetime

from pydantic import BaseModel, Field


class AiAssistantSourcePage(BaseModel):
    """A page of the business's website the assistant read."""

    url: str
    title: str | None = None
    chars: int


class AiAssistantWebsiteSyncItem(BaseModel):
    """The last read of the website: when, how many pages, what changed since the one before."""

    at: datetime | None = None
    pages: int = 0
    added: list[str] = Field(default_factory=list)
    removed: list[str] = Field(default_factory=list)
    changed: list[str] = Field(default_factory=list)
    # Why the site could not be read (its previous pages are kept).
    error: str | None = None


class AiAssistantDocumentItem(BaseModel):
    """A document the business gave its assistant."""

    id: int
    name: str
    pages: int
    size_bytes: int
    chars: int
    # The text was cut to its bound (a long document).
    truncated: bool
    enabled: bool
    url: str | None = None
    created_at: datetime


class AiAssistantSourcesResponse(BaseModel):
    """Everything the assistant reads, and what can be switched off."""

    website_url: str | None = None
    site_enabled: bool
    listing_enabled: bool
    pages: list[AiAssistantSourcePage] = Field(default_factory=list)
    sync: AiAssistantWebsiteSyncItem | None = None
    # What the Google listing brings, in French (« Note 4,6/5 (128 avis) », « Horaires », « 3 services »).
    listing_facts: list[str] = Field(default_factory=list)
    documents: list[AiAssistantDocumentItem] = Field(default_factory=list)
    max_documents: int


class AiAssistantSourcesUpdate(BaseModel):
    """Switch the website or the Google listing on or off (partial)."""

    site_enabled: bool | None = None
    listing_enabled: bool | None = None


class AiAssistantDocumentUpdate(BaseModel):
    """Switch a document on or off."""

    enabled: bool
