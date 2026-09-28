"""
An assistant's alert settings, its defaults applied: which requests reach the owner by SMS, and when not.

A NULL column means its default: SMS and email on, quotes, appointments and emergencies texted, and a quiet window
from 22 h to 8 h (business time) during which an SMS waits for the end of the window.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from enums.ai_assistant_request import AiAssistantRequestType
from models.ai_assistant import AiAssistant

DEFAULT_SMS_TYPES: frozenset[AiAssistantRequestType] = frozenset(
    {AiAssistantRequestType.QUOTE, AiAssistantRequestType.APPOINTMENT, AiAssistantRequestType.URGENT}
)
DEFAULT_QUIET_START_HOUR = 22
DEFAULT_QUIET_END_HOUR = 8

_REQUEST_TYPE_VALUES: frozenset[str] = frozenset(request_type.value for request_type in AiAssistantRequestType)


def _hour_or(value: int | None, default: int) -> int:
    """A stored hour when it is a valid one (0-23), else the default."""
    return value if isinstance(value, int) and 0 <= value <= 23 else default


@dataclass(frozen=True)
class AlertSettings:
    """An assistant's alert settings with the defaults applied."""

    phone_e164: str | None
    sms_enabled: bool
    email_enabled: bool
    sms_types: frozenset[AiAssistantRequestType]
    quiet_start_hour: int
    quiet_end_hour: int

    @classmethod
    def of(cls, assistant: AiAssistant) -> AlertSettings:
        """
        Read an assistant's alert settings, a NULL column meaning its default.

        Args:
            assistant: The assistant.

        Returns:
            The effective settings.
        """
        stored_types = assistant.alert_sms_types
        sms_types = (
            frozenset(AiAssistantRequestType(value) for value in stored_types if value in _REQUEST_TYPE_VALUES)
            if isinstance(stored_types, list)
            else DEFAULT_SMS_TYPES
        )
        return cls(
            phone_e164=assistant.alert_phone_e164 or None,
            sms_enabled=assistant.alert_sms_enabled is not False,
            email_enabled=assistant.alert_email_enabled is not False,
            sms_types=sms_types,
            quiet_start_hour=_hour_or(assistant.alert_quiet_start_hour, DEFAULT_QUIET_START_HOUR),
            quiet_end_hour=_hour_or(assistant.alert_quiet_end_hour, DEFAULT_QUIET_END_HOUR),
        )

    def wants_sms(self, request_type: AiAssistantRequestType) -> bool:
        """
        Whether a request of this type is texted to the owner.

        Args:
            request_type: The request type.

        Returns:
            True when SMS are on, a number is set and the type is one worth an SMS.
        """
        return self.sms_enabled and self.phone_e164 is not None and request_type in self.sms_types


class QuietHours:
    """The owner's « do not disturb » window, in the business's local time (hours 0-23)."""

    @staticmethod
    def contains(local: datetime, start_hour: int, end_hour: int) -> bool:
        """
        Whether a local moment falls in the window.

        Args:
            local: Local time of the business.
            start_hour: First quiet hour (22 for 22:00).
            end_hour: Hour the window ends (8 for 08:00); equal to ``start_hour`` = no window.

        Returns:
            True inside the window.
        """
        if start_hour == end_hour:
            return False
        if start_hour < end_hour:
            return start_hour <= local.hour < end_hour
        return local.hour >= start_hour or local.hour < end_hour

    @classmethod
    def release_at(cls, local: datetime, start_hour: int, end_hour: int) -> datetime:
        """
        The first moment at or after ``local`` outside the window.

        Args:
            local: Local time of the business.
            start_hour: First quiet hour.
            end_hour: Hour the window ends.

        Returns:
            ``local`` itself outside the window, else the window's end (local time).
        """
        if not cls.contains(local, start_hour, end_hour):
            return local
        release = local.replace(hour=end_hour, minute=0, second=0, microsecond=0)
        return release if release > local else release + timedelta(days=1)
