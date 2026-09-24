"""
The half-days a visitor may ask an appointment for, read from the business's opening hours.

Without a connected agenda the assistant never books: it offers the next open half-days (morning,
afternoon) from tomorrow on, the visitor picks up to two, and the business confirms one. A half-day is
open when the hours say the business is open at one of its probe times; unknown hours fall back to the
weekdays.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import ClassVar

from enums.ai_assistant_request import AiAssistantDayPeriod
from models.ai_assistant import AiAssistant
from services.ai_assistant.opening_hours import OpeningHoursCalendar


@dataclass(frozen=True)
class AppointmentDay:
    """An open day and its open half-days."""

    day: date
    periods: tuple[AiAssistantDayPeriod, ...]


@dataclass(frozen=True)
class AppointmentSlot:
    """A half-day the visitor wishes."""

    day: date
    period: AiAssistantDayPeriod


class AiAssistantAppointmentSlots:
    """Offers, checks and words the half-days of an appointment request."""

    DAYS_OFFERED: ClassVar[int] = 6
    DAYS_LOOKED_AHEAD: ClassVar[int] = 21
    MAX_CHOSEN: ClassVar[int] = 2
    _PROBES: ClassVar[dict[AiAssistantDayPeriod, tuple[time, ...]]] = {
        AiAssistantDayPeriod.MORNING: (time(8, 30), time(9, 30), time(10, 30), time(11, 30)),
        AiAssistantDayPeriod.AFTERNOON: (time(13, 30), time(14, 30), time(15, 30), time(16, 30), time(17, 30)),
    }
    _WEEKDAYS: ClassVar[tuple[str, ...]] = ("lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim.")
    _PERIOD_LABELS: ClassVar[dict[AiAssistantDayPeriod, str]] = {
        AiAssistantDayPeriod.MORNING: "matin",
        AiAssistantDayPeriod.AFTERNOON: "après-midi",
    }

    @staticmethod
    def opening_hours_of(assistant: AiAssistant) -> list[dict[str, str]] | None:
        """The business's cleaned opening-hour rows, from its assistant's knowledge (None when unknown)."""
        opening_hours = (assistant.knowledge_json or {}).get("opening_hours")
        return opening_hours if isinstance(opening_hours, list) else None

    @classmethod
    def offer_for(cls, assistant: AiAssistant, *, today: date | None = None) -> list[AppointmentDay]:
        """
        The half-days an assistant's widget offers now.

        Args:
            assistant: The assistant (its knowledge holds the business hours).
            today: The business's current day (tests); defaults to today in Paris.

        Returns:
            The offered days, as :meth:`offer` reads them.
        """
        return cls.offer(cls.opening_hours_of(assistant), today=today or OpeningHoursCalendar.business_now().date())

    @classmethod
    def offer(cls, opening_hours: list[dict[str, str]] | None, *, today: date) -> list[AppointmentDay]:
        """
        The next open days (from tomorrow) and their open half-days.

        Args:
            opening_hours: The business's cleaned opening-hour rows, when known.
            today: The business's current day.

        Returns:
            At most ``DAYS_OFFERED`` days, looking ``DAYS_LOOKED_AHEAD`` days ahead.
        """
        days: list[AppointmentDay] = []
        for offset in range(1, cls.DAYS_LOOKED_AHEAD + 1):
            day = today + timedelta(days=offset)
            periods = tuple(period for period in AiAssistantDayPeriod if cls._is_open(opening_hours, day, period))
            if periods:
                days.append(AppointmentDay(day=day, periods=periods))
            if len(days) == cls.DAYS_OFFERED:
                break
        return days

    @classmethod
    def check(
        cls, opening_hours: list[dict[str, str]] | None, chosen: list[AppointmentSlot], *, today: date
    ) -> list[AppointmentSlot]:
        """
        Keep a visitor's choice only when every half-day is still offered.

        Args:
            opening_hours: The business's cleaned opening-hour rows, when known.
            chosen: The half-days the visitor picked.
            today: The business's current day.

        Returns:
            The distinct half-days, in calendar order.

        Raises:
            ValueError: When more than ``MAX_CHOSEN`` are chosen or one is not offered.
        """
        distinct = sorted(set(chosen), key=lambda slot: (slot.day, list(AiAssistantDayPeriod).index(slot.period)))
        if len(distinct) > cls.MAX_CHOSEN:
            raise ValueError("Deux créneaux au plus")
        offered = {(item.day, period) for item in cls.offer(opening_hours, today=today) for period in item.periods}
        if any((slot.day, slot.period) not in offered for slot in distinct):
            raise ValueError("Ce créneau n'est plus proposé")
        return distinct

    @classmethod
    def label(cls, slot: AppointmentSlot) -> str:
        """A half-day in French (« lun. 28/09, matin »)."""
        return f"{cls._WEEKDAYS[slot.day.weekday()]} {slot.day:%d/%m}, {cls._PERIOD_LABELS[slot.period]}"

    @classmethod
    def short_labels(cls, stored: list[dict[str, str]] | None) -> list[str]:
        """
        The half-days of a request as the alert SMS words them (« lun. 28/09 matin »).

        Args:
            stored: The request's ``appointment_slots_json``.

        Returns:
            One label per half-day, in stored order.
        """
        return [
            f"{cls._WEEKDAYS[slot.day.weekday()]} {slot.day:%d/%m} {cls._PERIOD_LABELS[slot.period]}"
            for slot in cls.read(stored)
        ]

    @classmethod
    def labels(cls, stored: list[dict[str, str]] | None) -> list[str]:
        """
        The French labels of a request's stored half-days (unreadable entries skipped).

        Args:
            stored: The request's ``appointment_slots_json``.

        Returns:
            One label per half-day, in stored order.
        """
        return [cls.label(slot) for slot in cls.read(stored)]

    @staticmethod
    def read(stored: list[dict[str, str]] | None) -> list[AppointmentSlot]:
        """The half-days of a request's ``appointment_slots_json``, unreadable entries skipped."""
        slots: list[AppointmentSlot] = []
        for entry in stored or []:
            try:
                slots.append(
                    AppointmentSlot(
                        day=date.fromisoformat(str(entry["date"])), period=AiAssistantDayPeriod(entry["period"])
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
        return slots

    @staticmethod
    def to_json(slots: list[AppointmentSlot]) -> list[dict[str, str]]:
        """Half-days as stored on a request (``[{"date": "2026-09-28", "period": "morning"}]``)."""
        return [{"date": slot.day.isoformat(), "period": slot.period.value} for slot in slots]

    @classmethod
    def _is_open(cls, opening_hours: list[dict[str, str]] | None, day: date, period: AiAssistantDayPeriod) -> bool:
        """Whether the business is open during a half-day (weekdays only when its hours are unknown)."""
        answers = [
            OpeningHoursCalendar.is_open_at(opening_hours, datetime.combine(day, probe))
            for probe in cls._PROBES[period]
        ]
        if all(answer is None for answer in answers):
            return day.weekday() < 5
        return any(answer is True for answer in answers)
