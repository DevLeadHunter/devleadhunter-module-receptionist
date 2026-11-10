"""
Contracts of the demo space: the client space a prospect opens from its demo page, filled from its own receptionist.

The response is the client space's own contract (the page reuses its screens) with what a demo adds: ``is_demo``, the
receptionist's portrait gender, the business card it presents, the subscription link and its price; each request carries
its conversation, and the examples of the business's trade are flagged ``is_example``.
"""

from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from enums.ai_assistant_persona_gender import AiAssistantPersonaGender
from schemas.ai_assistant import AiAssistantPublicBusiness, AiAssistantTranscriptLine
from schemas.ai_assistant_client_space import (
    AiAssistantClientReport,
    AiAssistantClientRequestItem,
    AiAssistantClientSpaceResponse,
)
from services.ai_assistant.field_limits import SESSION_ID_MAX_CHARS

# A widget session id as the widget writes it: a UUID, or « <time>-<random> » in a browser without one.
DemoSpaceSessionId = Annotated[
    str, StringConstraints(min_length=8, max_length=SESSION_ID_MAX_CHARS, pattern=r"^[A-Za-z0-9_-]+$")
]

# The widget sessions a visitor's browser may name at once: its current conversation and a few earlier ones.
DEMO_SPACE_MAX_SESSIONS = 5


class AiAssistantDemoSpaceRequest(BaseModel):
    """The widget sessions the visitor's browser kept for this demo: the space lists their requests, and only those."""

    session_ids: list[DemoSpaceSessionId] = Field(default_factory=list, max_length=DEMO_SPACE_MAX_SESSIONS)


class AiAssistantDemoSpaceRequestItem(AiAssistantClientRequestItem):
    """One request of a demo space: one the visitor left while testing the demo, or an example of the trade."""

    # A fictional request of the business's trade (negative id, fictional name and contact), never a visitor's.
    is_example: bool = False
    # The conversation the request came out of, oldest turn first.
    conversation: list[AiAssistantTranscriptLine] = Field(default_factory=list)


class AiAssistantDemoSpaceReport(AiAssistantClientReport):
    """The monthly report of a demo space: example figures of the business's trade, a demo having no report."""

    is_example: bool = True


class AiAssistantDemoSpaceResponse(AiAssistantClientSpaceResponse):
    """
    Everything the demo space shows, read-only: the client space as the business gets it on the day of the sale.

    ``link_expires_label`` holds the demo's last day (« 31/10/2026 »), after which the space closes with the demo; it
    is empty while the demo's countdown has not started (its link was never sent).
    """

    # Nothing can be saved: every write of the client space takes a client link, which a demo never has.
    is_demo: bool = True
    requests: list[AiAssistantDemoSpaceRequestItem] = Field(default_factory=list)
    report: AiAssistantDemoSpaceReport | None = None
    # The grammatical gender of the receptionist's first name, which picks her portrait.
    assistant_gender: AiAssistantPersonaGender = AiAssistantPersonaGender.FEMININE
    # The business as its receptionist presents it: phone, address, opening hours.
    business: AiAssistantPublicBusiness
    # The monthly subscription link (a fresh Stripe Checkout at each click) and its price (« 79 € »).
    subscribe_url: str
    monthly_price_label: str
