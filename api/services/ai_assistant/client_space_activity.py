"""
The client space home's live figures: the last 30 days, in all and day by day.

The monthly report covers the calendar month before and is written once; the home shows the days being lived,
over a sliding window so it never reads zero on the first of a month. Same counting as the report
(``AiAssistantReportStats``): a conversation counts on each day a visitor wrote in it, the operator's own tests are
left out, and the days are the business's (Paris time).

A demo space counts the visitor's own widget sessions only, their tests included, like the requests it lists: a demo
slug is a business name anyone can guess, so it never shows what another visitor did.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy import ColumnElement, distinct, func
from sqlalchemy.orm import Session

from core.clock import naive_utc_now
from enums.ai_assistant_request import AiAssistantRequestOutcome, AiAssistantRequestType
from models.ai_assistant import AiAssistant
from models.ai_assistant_conversation import AiAssistantConversation
from models.ai_assistant_message import AiAssistantMessage
from models.ai_assistant_request import AiAssistantRequest
from schemas.ai_assistant_client_space import AiAssistantClientActivityDay, AiAssistantClientRecentFigures
from services.ai_assistant.opening_hours import OpeningHoursCalendar
from services.ai_assistant.report_stats import AiAssistantReportStats

# The window of the home's figures and chart, today included.
ACTIVITY_DAYS = 30


class AiAssistantClientActivity:
    """The last days of an assistant, as the client space home shows them."""

    @staticmethod
    def window(*, now: datetime | None = None) -> tuple[date, datetime, datetime]:
        """
        The last ``ACTIVITY_DAYS`` business days, today included.

        Args:
            now: Current naive UTC time (tests); defaults to now.

        Returns:
            The window's first business day, then its bounds in naive UTC (end excluded: the next midnight).
        """
        today = OpeningHoursCalendar.to_business_time(now or naive_utc_now()).date()
        first_day = today - timedelta(days=ACTIVITY_DAYS - 1)
        start = OpeningHoursCalendar.to_utc(datetime(first_day.year, first_day.month, first_day.day))
        end = OpeningHoursCalendar.to_utc(datetime(today.year, today.month, today.day) + timedelta(days=1))
        return first_day, start, end

    @classmethod
    def recent_figures(
        cls, db: Session, assistant: AiAssistant, *, now: datetime | None = None
    ) -> AiAssistantClientRecentFigures:
        """
        The figures of the last days, as the monthly report counts them.

        Args:
            db: Active database session.
            assistant: The assistant.
            now: Current naive UTC time (tests); defaults to now.

        Returns:
            The conversations, requests, quotes, clients won and share received outside the opening hours.
        """
        _first_day, start, end = cls.window(now=now)
        stats = AiAssistantReportStats.figures(db, assistant, start=start, end=end)
        return AiAssistantClientRecentFigures(
            days=ACTIVITY_DAYS,
            conversations=stats.conversations,
            requests=stats.requests,
            quotes=stats.quotes,
            won=stats.won,
            outside_hours_pct=stats.outside_hours_pct,
        )

    @classmethod
    def session_figures(
        cls, db: Session, assistant: AiAssistant, session_ids: list[str], *, now: datetime | None = None
    ) -> AiAssistantClientRecentFigures:
        """
        The figures of the last days for a visitor's own widget sessions (a demo space), their tests included.

        Args:
            db: Active database session.
            assistant: The demo receptionist.
            session_ids: The widget sessions the visitor's browser kept.
            now: Current naive UTC time (tests); defaults to now.

        Returns:
            The same figures as :meth:`recent_figures`, over those sessions only.
        """
        _first_day, start, end = cls.window(now=now)
        conversations = (
            db.query(func.count(distinct(AiAssistantMessage.conversation_id)))
            .join(AiAssistantConversation, AiAssistantConversation.id == AiAssistantMessage.conversation_id)
            .filter(*cls._session_turns(assistant, session_ids, start=start, end=end))
            .scalar()
        )
        requests = (
            db.query(AiAssistantRequest.type, AiAssistantRequest.outcome, AiAssistantRequest.received_outside_hours)
            .filter(*cls._session_requests(assistant, session_ids, start=start, end=end))
            .all()
        )
        known_hours = [row.received_outside_hours for row in requests if row.received_outside_hours is not None]
        return AiAssistantClientRecentFigures(
            days=ACTIVITY_DAYS,
            conversations=int(conversations or 0),
            requests=len(requests),
            quotes=sum(1 for row in requests if row.type == AiAssistantRequestType.QUOTE.value),
            won=sum(1 for row in requests if row.outcome == AiAssistantRequestOutcome.WON.value),
            outside_hours_pct=round(100 * sum(known_hours) / len(known_hours)) if known_hours else None,
        )

    @classmethod
    def by_day(
        cls,
        db: Session,
        assistant: AiAssistant,
        *,
        session_ids: list[str] | None = None,
        now: datetime | None = None,
    ) -> list[AiAssistantClientActivityDay]:
        """
        The conversations and requests of each of the last days, oldest first.

        Args:
            db: Active database session.
            assistant: The assistant.
            session_ids: A demo space's visitor sessions, to count only theirs (tests included); None counts every
                visitor but the operator's tests.
            now: Current naive UTC time (tests); defaults to now.

        Returns:
            One entry per day of the window, the empty days included.
        """
        first_day, start, end = cls.window(now=now)
        if session_ids is None:
            turn_filters = AiAssistantReportStats.visitor_turns(assistant, start=start, end=end)
            request_filters = (
                AiAssistantRequest.assistant_id == assistant.id,
                AiAssistantRequest.is_test.is_(False),
                AiAssistantRequest.created_at >= start,
                AiAssistantRequest.created_at < end,
            )
        else:
            turn_filters = cls._session_turns(assistant, session_ids, start=start, end=end)
            request_filters = cls._session_requests(assistant, session_ids, start=start, end=end)
        conversations_by_day: defaultdict[date, set[int]] = defaultdict(set)
        turns = (
            db.query(AiAssistantMessage.conversation_id, AiAssistantMessage.created_at)
            .join(AiAssistantConversation, AiAssistantConversation.id == AiAssistantMessage.conversation_id)
            .filter(*turn_filters)
            .all()
        )
        for conversation_id, created_at in turns:
            conversations_by_day[OpeningHoursCalendar.to_business_time(created_at).date()].add(conversation_id)
        requests_by_day: Counter[date] = Counter(
            OpeningHoursCalendar.to_business_time(created_at).date()
            for (created_at,) in db.query(AiAssistantRequest.created_at).filter(*request_filters).all()
        )
        days = [first_day + timedelta(days=offset) for offset in range(ACTIVITY_DAYS)]
        return [
            AiAssistantClientActivityDay(
                day=day.isoformat(),
                conversations=len(conversations_by_day[day]),
                requests=requests_by_day[day],
            )
            for day in days
        ]

    @staticmethod
    def _session_turns(
        assistant: AiAssistant, session_ids: list[str], *, start: datetime, end: datetime
    ) -> tuple[ColumnElement[bool], ...]:
        """The filters of a visitor's own messages over the window, in their widget sessions' conversations."""
        return (
            AiAssistantConversation.assistant_id == assistant.id,
            AiAssistantConversation.session_id.in_(session_ids),
            AiAssistantMessage.role == "user",
            AiAssistantMessage.created_at >= start,
            AiAssistantMessage.created_at < end,
        )

    @staticmethod
    def _session_requests(
        assistant: AiAssistant, session_ids: list[str], *, start: datetime, end: datetime
    ) -> tuple[ColumnElement[bool], ...]:
        """The filters of the requests a visitor left from their widget sessions over the window."""
        return (
            AiAssistantRequest.assistant_id == assistant.id,
            AiAssistantRequest.session_id.in_(session_ids),
            AiAssistantRequest.created_at >= start,
            AiAssistantRequest.created_at < end,
        )
