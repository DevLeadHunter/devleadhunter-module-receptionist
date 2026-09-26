"""Schemas for the AI assistant endpoints (owner management, public widget config and chat)."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from enums.ai_assistant_persona_gender import AiAssistantPersonaGender
from enums.ai_assistant_request import (
    AiAssistantDayPeriod,
    AiAssistantRequestChannel,
    AiAssistantRequestStatus,
    AiAssistantRequestType,
)
from enums.assistant_booking_mode import AssistantBookingMode
from enums.assistant_visitor_channel import AssistantVisitorChannel

# The years an appointment or an offer page may name: anything else overflows the timezone arithmetic.
BOOKABLE_YEAR_MIN = 2020
BOOKABLE_YEAR_MAX = 2100


class AiAssistantCreateRequest(BaseModel):
    """Request to generate an assistant for one of the caller's prospects."""

    prospect_id: int


class AiAssistantUpdateRequest(BaseModel):
    """Owner edits to an assistant's branding, persona and alerts (all optional, partial update)."""

    assistant_name: str | None = Field(default=None, max_length=64)
    business_name: str | None = Field(default=None, max_length=255)
    languages: list[str] | None = Field(default=None, max_length=10)
    tone: str | None = Field(default=None, max_length=255)
    use_brand_color: bool | None = None
    accent_color: str | None = Field(default=None, max_length=32)
    # Where the business's alerts, reports and client-space links go (empty clears it).
    email: str | None = Field(default=None, max_length=255)
    # The business owner's mobile for the alerts, as typed (empty clears it).
    alert_phone: str | None = Field(default=None, max_length=32)
    alert_sms_enabled: bool | None = None
    alert_email_enabled: bool | None = None
    alert_sms_types: list[AiAssistantRequestType] | None = None
    alert_quiet_start_hour: int | None = Field(default=None, ge=0, le=23)
    alert_quiet_end_hour: int | None = Field(default=None, ge=0, le=23)
    # The client requires its visitors' data to stay with Mistral: no Groq fallback.
    eu_only: bool | None = None


class AiAssistantAlertSettings(BaseModel):
    """How the business owner is alerted of the requests once the assistant is sold (defaults applied)."""

    phone: str | None
    sms_enabled: bool
    email_enabled: bool
    # Request types texted at once; every other type goes by email only.
    sms_types: list[AiAssistantRequestType]
    # SMS held from this hour to the end hour (Paris time); equal hours = never held.
    quiet_start_hour: int
    quiet_end_hour: int


class AiAssistantResponse(BaseModel):
    """An assistant as seen by its owner in the dashboard."""

    id: int
    slug: str
    prospect_id: int | None = None
    business_name: str
    assistant_name: str
    # Resolved from the first name; the dashboard picks the casting portrait from it.
    assistant_gender: str = AiAssistantPersonaGender.FEMININE.value
    # Where the business's alerts, reports and client-space links go.
    email: str | None = None
    languages: list[str] = Field(default_factory=list)
    tone: str | None = None
    accent_color: str | None = None
    use_brand_color: bool = True
    status: str
    demo_url: str
    embed_snippet: str
    # Demo countdown: NULL until the link is first emailed or texted, then the expiry it set.
    demo_link_sent_at: datetime | None = None
    expires_at: datetime | None = None
    # Prospection video state: NULL when never requested, else pending/generating/ready/failed.
    video_status: str | None = None
    video_page_url: str | None = None
    video_error: str | None = None
    # Subscription state: NULL when no active subscription, else the locked plan the client pays.
    subscription_status: str | None = None
    subscription_amount_cents: int | None = None
    subscription_interval: str | None = None
    # Visitor conversations journaled over the last 7 / 30 days (the owner's window once sold).
    conversations_7d: int = 0
    conversations_30d: int = 0
    # Visitor requests over the last 7 / 30 days, and the share received outside the business hours.
    requests_7d: int = 0
    requests_30d: int = 0
    requests_outside_hours_pct: int | None = None
    # A subscriber for 30 days whose assistant had no conversation and no request over the last 30.
    churn_risk: bool = False
    alerts: AiAssistantAlertSettings
    eu_only: bool = False
    created_at: datetime


class AiAssistantListResponse(BaseModel):
    """The caller's assistants."""

    assistants: list[AiAssistantResponse] = Field(default_factory=list)


class AssistantSubscriptionItem(BaseModel):
    """One assistant subscription, as the Ventes/Abonnements page shows it."""

    id: int
    ai_assistant_id: int | None = None
    prospect_id: int | None = None
    business_name: str | None = None
    assistant_name: str | None = None
    client_name: str | None = None
    client_email: str | None = None
    interval: str
    amount_cents: int
    currency: str
    status: str
    current_period_end: datetime | None = None
    canceled_at: datetime | None = None
    stripe_subscription_id: str | None = None
    created_at: datetime


class AssistantSubscriptionListResponse(BaseModel):
    """The caller's subscriptions plus the headline KPIs (active count + MRR)."""

    subscriptions: list[AssistantSubscriptionItem] = Field(default_factory=list)
    active_count: int = 0
    mrr_cents: int = 0


class AiAssistantClosedHours(BaseModel):
    """
    The demo page's estimate: how long the business is closed from 7:00 to 22:00 (its Google hours) and the
    requests that would come in meanwhile, on a base of a plausible monthly volume for its trade.
    """

    open_hours_per_week: int
    closed_share_pct: int
    closed_hours_in_month: int
    # The month of ``closed_hours_in_month`` (1 to 12), in the business's time.
    month: int
    # The base of the estimate: « un plombier », 30 requests a month.
    trade_label: str
    monthly_requests: int
    # ``monthly_requests`` × ``closed_share_pct``.
    estimated_requests: int


class AiAssistantPublicResponse(BaseModel):
    """The configuration the chat widget needs to render itself for a prospect's assistant."""

    slug: str
    business_name: str
    assistant_name: str
    assistant_gender: str = AiAssistantPersonaGender.FEMININE.value
    languages: list[str] = Field(default_factory=list)
    accent_color: str | None = None
    status: str
    # The business as its Google listing shows it, for the demo page's scene (None when unknown).
    city: str | None = None
    trade_label: str | None = None
    google_rating: float | None = None
    google_reviews_count: int | None = None
    # Owner contact, shown in the « me contacter » banner so the prospect can reach the seller.
    owner_name: str | None = None
    owner_profile_photo_url: str | None = None
    owner_contact_phone: str | None = None
    owner_contact_email: str | None = None
    # Prospection video (the /va/{slug} player + email thumbnail), present only when generated.
    video_available: bool = False
    video_url: str | None = None
    video_thumbnail_url: str | None = None
    # What the prospect would pay a month (the seller's current price, « 79 € »), for the demo page;
    # None once sold.
    monthly_price_label: str | None = None
    # How long the business is closed while its customers look for it, for the demo page; None once sold or
    # when its hours are unknown.
    closed_hours: AiAssistantClosedHours | None = None


class AiAssistantInterestRequest(BaseModel):
    """A prospect raising their hand from the assistant sales page (« me contacter » banner)."""

    message: str | None = Field(None, max_length=2000)


class AiAssistantChatMessage(BaseModel):
    """A single conversation turn from the widget (its replies included: about 2,500 characters at most)."""

    role: Literal["user", "assistant"]
    content: str = Field(..., max_length=4000)
    # The suggestions the widget showed under an assistant turn: sent back so the model does not repeat them.
    follow_ups: list[str] = Field(default_factory=list, max_length=3)


class AiAssistantChatRequest(BaseModel):
    """A visitor's chat request: the conversation so far, ending on the visitor's message."""

    # The widget sends its last 40 turns; the margin covers an older widget still in a page.
    messages: list[AiAssistantChatMessage] = Field(default_factory=list, max_length=100)
    # Random id the widget keeps with the visitor's conversation, so the journal groups its turns.
    session_id: str | None = Field(default=None, max_length=64)
    language: str | None = Field(default=None, max_length=8)
    # Set by the widget on a « ?internal=1 » visit (the operator testing): journaled, out of the counts.
    internal: bool = False


class AiAssistantChatResponse(BaseModel):
    """The assistant's reply to a chat request."""

    reply: str
    # The visitor asks for an appointment: the widget opens its appointment panel under the reply.
    offer_booking: bool = False
    # Questions the visitor may want to ask next, offered as chips under the reply.
    follow_ups: list[str] = Field(default_factory=list)


class AiAssistantSlotChoice(BaseModel):
    """A half-day a visitor picked for an appointment."""

    date: date
    period: AiAssistantDayPeriod


class AiAssistantAppointmentDay(BaseModel):
    """An open day and the half-days a visitor may pick in it."""

    date: date
    periods: list[AiAssistantDayPeriod]


class AiAssistantAppointmentTime(BaseModel):
    """A free slot of the connected agenda (aware, business time zone)."""

    start: datetime
    end: datetime


class AiAssistantAppointmentSlotsResponse(BaseModel):
    """What the appointment panel offers: free slots of the agenda, or open half-days to wish (from tomorrow)."""

    mode: AssistantBookingMode = AssistantBookingMode.REQUEST
    days: list[AiAssistantAppointmentDay] = Field(default_factory=list)
    max_chosen: int
    times: list[AiAssistantAppointmentTime] = Field(default_factory=list)
    has_more: bool = False
    # Kinds of appointment the visitor picks from, when the agenda offers some.
    types: list[str] = Field(default_factory=list)
    duration_minutes: int | None = None


class AiAssistantBookingChoice(BaseModel):
    """A free slot of the agenda the visitor picked, and its kind."""

    start: datetime
    type: str | None = Field(default=None, max_length=64)

    @field_validator("start")
    @classmethod
    def _within_bookable_years(cls, value: datetime) -> datetime:
        """A start far outside the offer overflows timezone arithmetic: refuse it here."""
        if not BOOKABLE_YEAR_MIN <= value.year <= BOOKABLE_YEAR_MAX:
            raise ValueError("start is outside the bookable years")
        return value


class AiAssistantLeadRequest(BaseModel):
    """A visitor's details submitted through the assistant widget — it becomes a request."""

    name: str = Field(..., max_length=255)
    contact: str = Field(..., max_length=255)
    need: str | None = Field(default=None, max_length=2000)
    language: str | None = Field(default=None, max_length=8)
    # The widget session, so the request links the conversation and a resubmission updates it.
    session_id: str | None = Field(default=None, max_length=64)
    # Set by the widget on a « ?internal=1 » visit (the operator testing): recorded, never announced.
    internal: bool = False
    # Half-days picked for an appointment: the request becomes an appointment request.
    slots: list[AiAssistantSlotChoice] = Field(default_factory=list, max_length=2)
    # A free slot of the connected agenda: the appointment is booked in it.
    booking: AiAssistantBookingChoice | None = None


class AiAssistantPhotoResponse(BaseModel):
    """The assistant's answer to a photo a visitor sent for a quote."""

    # False when the photo was off-topic (refused politely, not kept).
    accepted: bool
    reply: str
    # One line on what the photo shows, to prefill the need of the contact form.
    need: str | None = None
    # How many more photos this widget session may send.
    remaining: int


class AiAssistantLeadResponse(BaseModel):
    """Acknowledgement that a lead was recorded."""

    ok: bool
    # The appointment's start when it was booked in the agenda (None: a request the business confirms).
    booked_start: datetime | None = None
    # How the visitor gets the confirmation of a booked appointment (None: no mobile nor email to use).
    confirmation_channel: AssistantVisitorChannel | None = None


class AiAssistantLeadItem(BaseModel):
    """One lead captured by an assistant, for the owner's leads list."""

    id: int
    assistant_id: int
    prospect_id: int | None = None
    business_name: str
    name: str
    contact: str
    need: str | None = None
    language: str | None = None
    created_at: datetime


class AiAssistantLeadsResponse(BaseModel):
    """The leads captured across the caller's assistants, newest first."""

    leads: list[AiAssistantLeadItem] = Field(default_factory=list)


class AiAssistantRequestItem(BaseModel):
    """One visitor request, for the owner's « Demandes » list."""

    id: int
    assistant_id: int
    prospect_id: int | None = None
    business_name: str
    type: AiAssistantRequestType
    status: AiAssistantRequestStatus
    channel: AiAssistantRequestChannel
    name: str
    contact: str
    need: str | None = None
    need_summary: str | None = None
    language: str | None = None
    received_outside_hours: bool | None = None
    is_test: bool = False
    owner_note: str | None = None
    photo_urls: list[str] = Field(default_factory=list)
    # Wished half-days of an appointment request, in French (« lun. 28/09, matin »).
    appointment_slots: list[str] = Field(default_factory=list)
    # The appointment booked in the agenda (« mar. 29/09 à 14:30 (Révision) »).
    appointment_booked: str | None = None
    created_at: datetime
    handled_at: datetime | None = None


class AiAssistantRequestsResponse(BaseModel):
    """The caller's requests across their assistants, newest first."""

    requests: list[AiAssistantRequestItem] = Field(default_factory=list)
    # Real requests still waiting for handling (tests excluded), whatever the filter.
    pending_count: int = 0


class AiAssistantTranscriptLine(BaseModel):
    """One turn of the conversation a request came out of; ``photo_url`` when the visitor's turn was a photo."""

    role: Literal["user", "assistant"]
    content: str
    photo_url: str | None = None


class AiAssistantRequestDetail(BaseModel):
    """One request with the conversation that led to it, for the owner's request drawer."""

    request: AiAssistantRequestItem
    transcript: list[AiAssistantTranscriptLine] = Field(default_factory=list)


class AiAssistantRequestUpdateRequest(BaseModel):
    """Owner changes to a request (partial)."""

    status: AiAssistantRequestStatus | None = None
    owner_note: str | None = Field(default=None, max_length=2000)


class AiAssistantConversationMessageItem(BaseModel):
    """One turn of a journaled conversation; ``photo_url`` when the visitor's turn was a photo (gone once purged)."""

    id: int
    role: str
    content: str
    photo_url: str | None = None
    created_at: datetime


class AiAssistantConversationItem(BaseModel):
    """One visitor conversation with its turns, for the owner's read-only journal."""

    id: int
    session_id: str
    language: str | None = None
    message_count: int
    started_at: datetime
    last_message_at: datetime
    messages: list[AiAssistantConversationMessageItem] = Field(default_factory=list)


class AiAssistantConversationsResponse(BaseModel):
    """The latest conversations of one assistant, newest first."""

    assistant_id: int
    business_name: str
    conversations: list[AiAssistantConversationItem] = Field(default_factory=list)
