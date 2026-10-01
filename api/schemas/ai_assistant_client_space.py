"""Contracts of a sold assistant's client space (the magic-link page) and of its link, issued from the dashboard."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from enums.ai_assistant_calendar_status import AiAssistantCalendarConnection
from enums.ai_assistant_mailbox import AiAssistantMailboxConnection
from enums.ai_assistant_request import (
    AiAssistantRequestChannel,
    AiAssistantRequestOutcome,
    AiAssistantRequestStatus,
    AiAssistantRequestType,
)
from enums.ai_assistant_subscription_status import AiAssistantSubscriptionStatus
from enums.ai_assistant_widget_language import AiAssistantWidgetLanguage
from schemas.ai_assistant_faq import AiAssistantFaqEntry, AiAssistantUnansweredEntry
from services.ai_assistant.field_limits import LABEL_MAX_CHARS, SHORT_TEXT_MAX_CHARS


class AiAssistantClientEvent(BaseModel):
    """What an event request said of the event; each field None until the visitor gave it."""

    date: str | None = None
    place: str | None = None
    guests: int | None = None
    budget: str | None = None


class AiAssistantClientRequestItem(BaseModel):
    """One request as its client sees it."""

    id: int
    type: AiAssistantRequestType
    status: AiAssistantRequestStatus
    # « email »: a customer's email, whose reply waits as a draft in the business's Gmail.
    channel: AiAssistantRequestChannel = AiAssistantRequestChannel.SITE
    name: str
    contact: str
    summary: str | None = None
    # « 14/09 à 10:05 », business time (Paris).
    received_label: str
    # The same moment split for grouping and display: « 2026-09-14 » and « 10:05 », business time.
    received_day: str = ""
    received_time: str = ""
    received_outside_hours: bool | None = None
    photo_urls: list[str] = Field(default_factory=list)
    # Wished half-days of an appointment request (« lun. 28/09, matin »).
    appointment_slots: list[str] = Field(default_factory=list)
    # The appointment booked in the agenda (« mar. 29/09 à 14:30 (Révision) »).
    appointment_booked: str | None = None
    # What became of the request once called back: a client won, lost, or nothing said yet.
    outcome: AiAssistantRequestOutcome | None = None
    # The event described, for a wedding, a reception, a catering request.
    event: AiAssistantClientEvent | None = None


class AiAssistantClientRequestOutcomeUpdate(BaseModel):
    """The business says what became of a request it called back; None clears it."""

    outcome: AiAssistantRequestOutcome | None = None


class AiAssistantClientLimit(BaseModel):
    """A sensitive subject and the sentence the receptionist says on it, as the business set it."""

    key: str
    topic: str
    answer: str
    enabled: bool = True


class AiAssistantClientLimitUpdate(BaseModel):
    """The business's edit of one subject."""

    key: str = Field(min_length=1, max_length=32)
    answer: str = Field(default="", max_length=300)
    enabled: bool = True


class AiAssistantClientLimitsUpdate(BaseModel):
    """The business's edits of its receptionist's imposed answers."""

    limits: list[AiAssistantClientLimitUpdate] = Field(default_factory=list, max_length=20)


class AiAssistantClientTestSms(BaseModel):
    """Whether the test SMS left for the client's alert mobile."""

    sent: bool
    to_label: str | None = None
    reason: str | None = None


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
    # Requests the business marked « client gagné », and the sentence that says it.
    won: int = 0
    won_line: str | None = None
    # Requests that came by email, each answered by a draft in Gmail.
    email_requests: int = 0


class AiAssistantClientRecentFigures(BaseModel):
    """The last days' figures, counted live like the monthly report (which covers the calendar month before)."""

    days: int
    conversations: int
    requests: int
    quotes: int
    won: int
    outside_hours_pct: int | None = None


class AiAssistantClientActivityDay(BaseModel):
    """One day of the home's activity chart."""

    # « 2026-10-01 », in the business's time zone.
    day: str
    conversations: int
    requests: int


class AiAssistantClientSubscription(BaseModel):
    """The client's subscription, read from its local copy."""

    status: AiAssistantSubscriptionStatus
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
    languages: list[AiAssistantWidgetLanguage]
    alert_phone: str | None = None
    alert_sms_enabled: bool
    alert_email_enabled: bool
    # The request types texted at once (the others go by email only), and the window during which the SMS are
    # held (Paris hours; equal hours = never held).
    alert_sms_types: list[AiAssistantRequestType]
    alert_quiet_start_hour: int
    alert_quiet_end_hour: int


class AiAssistantClientLanguageOption(BaseModel):
    """A language the widget can speak, with its French name."""

    code: AiAssistantWidgetLanguage
    label: str


class AiAssistantClientCalendar(BaseModel):
    """The agenda section: its connection and the booking settings (defaults applied)."""

    status: AiAssistantCalendarConnection
    account_email: str | None = None
    calendar_id: str
    duration_minutes: int
    min_notice_hours: int
    appointment_types: list[str] = Field(default_factory=list)
    # The last problem met with the agenda (« 24/09 à 10:05 : agenda introuvable… »), cleared by a booking.
    last_error: str | None = None
    duration_choices: list[int] = Field(default_factory=list)
    min_notice_choices: list[int] = Field(default_factory=list)


class AiAssistantClientMailbox(BaseModel):
    """The Gmail section: its connection, the address read, the reply drafts of the month."""

    status: AiAssistantMailboxConnection
    account_email: str | None = None
    # Reply drafts prepared since the first of the month (Paris).
    drafts_this_month: int = 0
    # Why the mailbox must be connected again (« 01/10 à 10:05 : l'accès… »), when it must.
    last_error: str | None = None
    # The daily cap stopped the reading today: the next emails get no draft before tomorrow.
    has_reached_daily_cap: bool = False
    # The Gmail drafts of the connected account.
    drafts_url: str


class AiAssistantClientMailboxConnect(BaseModel):
    """The Google consent page that connects the client's Gmail, to open in a new tab."""

    url: str


class AiAssistantClientAppointmentItem(BaseModel):
    """An upcoming appointment the assistant booked."""

    id: int
    # « mar. 29/09 à 14:30 », business time.
    start_label: str
    type_label: str | None = None
    name: str
    contact: str


class AiAssistantClientGoogleProfile(BaseModel):
    """The receptionist's address, ready for the business's Google profile, its voicemail and its printed matter."""

    # The receptionist's own page: the link for « Site web » and « Prendre rendez-vous » of the profile.
    page_url: str
    # The same address without its scheme, as it is read on a voicemail or printed.
    short_link: str
    # The address as an inline SVG QR code, to print on a card, a van, a quote.
    qr_svg: str
    # A voicemail greeting the business can record as is.
    voicemail_text: str
    # « 27/09/2026 » once the business said the link is on its profile.
    linked_at_label: str | None = None
    is_linked: bool = False


class AiAssistantClientGoogleProfileUpdate(BaseModel):
    """The business ticks (or unticks) « le lien est sur ma fiche »."""

    linked: bool


class AiAssistantClientInstalled(BaseModel):
    """Where the widget's loader was last seen on the business's own website."""

    host: str
    # « 27/09 à 21:15 », business time.
    seen_label: str


class AiAssistantClientSpaceResponse(BaseModel):
    """Everything the client-space page shows."""

    business_name: str
    assistant_name: str
    accent_color: str | None = None
    # « 24/10/2026 »: the last day this link opens the space.
    link_expires_label: str
    # The example space a prospect opens from its demo page: fictional data, nothing to save.
    is_example: bool = False
    pending_count: int
    requests: list[AiAssistantClientRequestItem] = Field(default_factory=list)
    report: AiAssistantClientReport | None = None
    # The last 30 days, in all and day by day (oldest first): the home's figures and chart.
    recent: AiAssistantClientRecentFigures | None = None
    activity: list[AiAssistantClientActivityDay] = Field(default_factory=list)
    settings: AiAssistantClientSettings
    language_options: list[AiAssistantClientLanguageOption] = Field(default_factory=list)
    subscription: AiAssistantClientSubscription | None = None
    calendar: AiAssistantClientCalendar
    appointments: list[AiAssistantClientAppointmentItem] = Field(default_factory=list)
    # The Gmail mailbox; None until the operator switches it on (and while Gmail is not configured on the server).
    mailbox: AiAssistantClientMailbox | None = None
    # The answers the business wrote, and the questions its assistant could not answer.
    faq: list[AiAssistantFaqEntry] = Field(default_factory=list)
    unanswered: list[AiAssistantUnansweredEntry] = Field(default_factory=list)
    # A fresh 30-day token for a valid link (never for the example): the page moves its URL to it, so a link
    # opened at least once a month never expires, and an icon on the phone's home screen keeps working.
    fresh_token: str | None = None
    # The business's own website, when known (« Ouvrir votre site » on the first day).
    website_url: str | None = None
    # The line to paste on the website to show the receptionist (« Sur votre site » screen).
    embed_snippet: str | None = None
    # The receptionist's address for the Google profile, the voicemail and the printed QR.
    google_profile: AiAssistantClientGoogleProfile | None = None
    # The widget seen on the business's site, once the line is pasted; None until then.
    installed: AiAssistantClientInstalled | None = None
    # What the receptionist never improvises: the imposed answers, as the business set them.
    limits: list[AiAssistantClientLimit] = Field(default_factory=list)


class AiAssistantClientSettingsUpdate(BaseModel):
    """A client's settings edit (partial; the alert mobile is read like in the dashboard)."""

    assistant_name: str | None = Field(default=None, min_length=1, max_length=LABEL_MAX_CHARS)
    languages: list[AiAssistantWidgetLanguage] | None = Field(
        default=None, min_length=1, max_length=len(AiAssistantWidgetLanguage)
    )
    # As typed; empty clears it (no SMS).
    alert_phone: str | None = Field(default=None, max_length=32)
    alert_sms_enabled: bool | None = None
    alert_email_enabled: bool | None = None
    alert_sms_types: list[AiAssistantRequestType] | None = None
    alert_quiet_start_hour: int | None = Field(default=None, ge=0, le=23)
    alert_quiet_end_hour: int | None = Field(default=None, ge=0, le=23)


class AiAssistantClientCalendarUpdate(BaseModel):
    """A client's booking settings edit (partial; choices checked by the service)."""

    calendar_id: str | None = Field(default=None, max_length=SHORT_TEXT_MAX_CHARS)
    duration_minutes: int | None = None
    min_notice_hours: int | None = None
    # Longer kinds are cut to 40 characters by the service.
    appointment_types: list[Annotated[str, StringConstraints(max_length=200)]] | None = Field(
        default=None, max_length=6
    )


class AiAssistantClientCalendarConnect(BaseModel):
    """The Google consent page to open in a new tab."""

    url: str


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
