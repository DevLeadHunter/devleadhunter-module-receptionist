"""The « Pour démarrer » steps a sold receptionist needs its business to take."""

from enum import Enum


class AiAssistantStartStep(str, Enum):
    """A step the business has not taken yet, so visitors cannot find the receptionist or its alerts go nowhere."""

    ALERT_PHONE = "alert_phone"
    GOOGLE_PROFILE_OR_WEBSITE = "google_profile_or_website"
    GOOGLE_CALENDAR = "google_calendar"
