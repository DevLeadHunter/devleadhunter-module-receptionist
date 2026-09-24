"""Contracts of a sold assistant's client space (the magic-link page) and of its link, issued from the dashboard."""

from datetime import datetime

from pydantic import BaseModel, Field

from enums.ai_assistant_request import AiAssistantRequestStatus, AiAssistantRequestType
from enums.assistant_subscription_status import AssistantSubscriptionStatus
from enums.assistant_widget_language import AssistantWidgetLanguage


class AiAssistantClientRequestItem(BaseModel):
    """One request as its client sees it."""

    id: int
    type: AiAssistantRequestType
    status: AiAssistantRequestStatus
    name: str
    contact: str
    summary: str | None = None
    # « 14/09 à 10:05 », business time (Paris).
    received_label: str
    received_outside_hours: bool | None = None
    photo_urls: list[str] = Field(default_factory=list)
    # Wished half-days of an appointment request (« lun. 28/09, matin »).
    appointment_slots: list[str] = Field(default_factory=list)


class AiAssistantClientReport(BaseModel):
    """The latest monthly report of the assistant."""

    month_label: str
    conversations: int
    requests: int
    quotes: int
    appointments: int
    urgent: int
    photo_requests: int
    outside_hours_pct: int | None = None
    # The report email's own sentences (« français 72 %, anglais 20 % », « 31 demandes marquées traitées… »).
    languages_line: str | None = None
    handling_line: str | None = None
    top_questions: list[str] = Field(default_factory=list)


class AiAssistantClientSubscription(BaseModel):
    """The client's subscription, read from its local copy."""

    status: AssistantSubscriptionStatus
    # « 79 €/mois » or « 790 €/an », the price locked at subscription.
    price_label: str
    # « 12/10/2026 »: end of the paid period, when Stripe sent it.
    period_end_label: str | None = None
    # The client scheduled the end in the portal: paid until ``period_end_label``, not renewed.
    cancel_scheduled: bool = False
    # The Stripe billing portal can open (a Stripe customer is known).
    can_manage: bool


class AiAssistantClientSettings(BaseModel):
    """The settings a client may change, defaults applied."""

    assistant_name: str
    languages: list[AssistantWidgetLanguage]
    alert_phone: str | None = None
    alert_sms_enabled: bool
    alert_email_enabled: bool


class AiAssistantClientLanguageOption(BaseModel):
    """A language the widget can speak, with its French name."""

    code: AssistantWidgetLanguage
    label: str


class AiAssistantClientSpaceResponse(BaseModel):
    """Everything the client-space page shows."""

    business_name: str
    assistant_name: str
    accent_color: str | None = None
    # « 24/10/2026 »: the last day this link opens the space.
    link_expires_label: str
    pending_count: int
    requests: list[AiAssistantClientRequestItem] = Field(default_factory=list)
    report: AiAssistantClientReport | None = None
    settings: AiAssistantClientSettings
    language_options: list[AiAssistantClientLanguageOption] = Field(default_factory=list)
    subscription: AiAssistantClientSubscription | None = None


class AiAssistantClientSettingsUpdate(BaseModel):
    """A client's settings edit (partial; the alert mobile is read like in the dashboard)."""

    assistant_name: str | None = Field(default=None, min_length=1, max_length=64)
    languages: list[AssistantWidgetLanguage] | None = Field(default=None, min_length=1)
    # As typed; empty clears it (no SMS).
    alert_phone: str | None = Field(default=None, max_length=32)
    alert_sms_enabled: bool | None = None
    alert_email_enabled: bool | None = None


class AiAssistantClientPortalResponse(BaseModel):
    """The Stripe billing portal session to redirect the client to."""

    url: str


class AiAssistantClientRenewResponse(BaseModel):
    """Whether a fresh link was emailed to the business (its address is never disclosed)."""

    sent: bool


class AiAssistantClientLinkRequest(BaseModel):
    """The operator issues a client-space link, and may email it to the business."""

    send: bool = False


class AiAssistantClientLinkResponse(BaseModel):
    """A fresh client-space link, and where it was emailed."""

    url: str
    expires_at: datetime
    # The business address it went to; None when not asked, or when it could not leave.
    sent_to: str | None = None
    send_error: str | None = None
