"""
The client space home's live figures: the last 30 days, in all and day by day.

The monthly report covers the calendar month before and is written once; the home shows the days being lived,
over a sliding window so it never reads zero on the first of a month. Same counting as the report
(``AiAssistantReportStats``): a conversation counts on each day a visitor wrote in it, the operator's own tests are
left out, and the days are the business's (Paris time).
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from core.clock import naive_utc_now
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
    def by_day(
        cls, db: Session, assistant: AiAssistant, *, now: datetime | None = None
    ) -> list[AiAssistantClientActivityDay]:
        """
        The conversations and requests of each of the last days, oldest first.

        Args:
            db: Active database session.
            assistant: The assistant.
            now: Current naive UTC time (tests); defaults to now.

        Returns:
            One entry per day of the window, the empty days included.
        """
        first_day, start, end = cls.window(now=now)
        conversations_by_day: defaultdict[date, set[int]] = defaultdict(set)
        turns = (
            db.query(AiAssistantMessage.conversation_id, AiAssistantMessage.created_at)
            .join(AiAssistantConversation, AiAssistantConversation.id == AiAssistantMessage.conversation_id)
            .filter(*AiAssistantReportStats.visitor_turns(assistant, start=start, end=end))
            .all()
        )
        for conversation_id, created_at in turns:
            conversations_by_day[OpeningHoursCalendar.to_business_time(created_at).date()].add(conversation_id)
        requests_by_day: Counter[date] = Counter(
            OpeningHoursCalendar.to_business_time(created_at).date()
            for (created_at,) in db.query(AiAssistantRequest.created_at)
            .filter(
                AiAssistantRequest.assistant_id == assistant.id,
                AiAssistantRequest.is_test.is_(False),
                AiAssistantRequest.created_at >= start,
                AiAssistantRequest.created_at < end,
            )
            .all()
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
