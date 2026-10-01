"""
A plausible number of customer requests a month by trade, the base of the demo page's estimate.

These are assumptions for a small business (calls, messages and forms together), not measurements: the page shows
them as the base of an estimate. The measured share of requests received outside opening hours is in the dashboard
and the monthly report.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import ClassVar

from enums.ai_assistant_trade import AiAssistantTrade
from services.ai_assistant.opening_hours import ClosedHoursEstimate, OpeningHoursCalendar
from services.ai_assistant.trade_resolver import AiAssistantTradeResolver


@dataclass(frozen=True)
class TradeVolume:
    """A trade as the page names it (« un plombier ») and the requests such a business receives a month."""

    label: str
    monthly_requests: int


@dataclass(frozen=True)
class ClosedHoursOffer:
    """The demo page's estimate: the business's closed time this month and the requests its trade would miss."""

    closed_hours: ClosedHoursEstimate
    month: int
    trade: TradeVolume
    estimated_requests: int


class AiAssistantRequestVolume:
    """Finds the request volume of a business from its Google Maps category."""

    DEFAULT: ClassVar[TradeVolume] = TradeVolume(label="un commerce comme le vôtre", monthly_requests=20)
    _BUILDING: ClassVar[TradeVolume] = TradeVolume(label="une entreprise du bâtiment", monthly_requests=15)
    # The trades without a volume of their own (a food truck, a landscaper…) are estimated on ``DEFAULT``.
    _VOLUMES: ClassVar[dict[AiAssistantTrade, TradeVolume]] = {
        AiAssistantTrade.CATERER: TradeVolume(label="un traiteur", monthly_requests=25),
        AiAssistantTrade.EVENT_VENUE: TradeVolume(label="un lieu de réception", monthly_requests=25),
        AiAssistantTrade.PLUMBER: TradeVolume(label="un plombier", monthly_requests=30),
        AiAssistantTrade.LOCKSMITH: TradeVolume(label="un serrurier", monthly_requests=30),
        AiAssistantTrade.ELECTRICIAN: TradeVolume(label="un électricien", monthly_requests=20),
        AiAssistantTrade.DOORS_AND_WINDOWS: _BUILDING,
        AiAssistantTrade.BODYWORK: TradeVolume(label="une carrosserie", monthly_requests=30),
        AiAssistantTrade.GARAGE: TradeVolume(label="un garage", monthly_requests=30),
        AiAssistantTrade.CARPENTER: TradeVolume(label="un charpentier", monthly_requests=15),
        AiAssistantTrade.ROOFER: TradeVolume(label="un couvreur", monthly_requests=15),
        AiAssistantTrade.JOINER: TradeVolume(label="un menuisier", monthly_requests=15),
        AiAssistantTrade.PAINTER: TradeVolume(label="un peintre", monthly_requests=15),
        AiAssistantTrade.MASON: _BUILDING,
        AiAssistantTrade.HAIRDRESSER: TradeVolume(label="un salon de coiffure", monthly_requests=40),
        AiAssistantTrade.BEAUTY: TradeVolume(label="un institut de beauté", monthly_requests=35),
        AiAssistantTrade.RESTAURANT: TradeVolume(label="un restaurant", monthly_requests=40),
        AiAssistantTrade.REAL_ESTATE: TradeVolume(label="une agence immobilière", monthly_requests=25),
        AiAssistantTrade.HEALTH: TradeVolume(label="un cabinet de santé", monthly_requests=40),
    }

    @classmethod
    def for_category(cls, category: str | None) -> TradeVolume:
        """
        The request volume of a business.

        Args:
            category: Its Google Maps category (« Plombier », « Garage automobile »), or None.

        Returns:
            The volume of its trade, else ``DEFAULT``.
        """
        return cls._VOLUMES.get(AiAssistantTradeResolver.of_category(category), cls.DEFAULT)

    @classmethod
    def closed_hours_offer(
        cls, opening_hours: list[dict[str, str]] | None, category: str | None, *, year: int, month: int
    ) -> ClosedHoursOffer | None:
        """
        The estimate a demo page shows: the business's closed time from 7:00 to 22:00, and the requests that would
        come in meanwhile for its trade.

        Args:
            opening_hours: The business's cleaned opening-hour rows (its Google hours).
            category: Its Google Maps category.
            year: The month's year.
            month: The month, 1 to 12.

        Returns:
            The offer; None when the hours are unknown or never open (a listing closed every day says nothing about
            when customers find the door shut).
        """
        closed_hours = OpeningHoursCalendar.closed_hours_estimate(opening_hours, year=year, month=month)
        if closed_hours is None or closed_hours.open_hours_per_week == 0:
            return None
        trade = cls.for_category(category)
        return ClosedHoursOffer(
            closed_hours=closed_hours,
            month=month,
            trade=trade,
            estimated_requests=cls.estimate(trade.monthly_requests, closed_hours.closed_share_pct),
        )

    @staticmethod
    def estimate(monthly_requests: int, closed_share_pct: int) -> int:
        """
        The requests a month that come in while the business is closed.

        Args:
            monthly_requests: The trade's monthly volume.
            closed_share_pct: The share of 7:00–22:00 when the business is closed, in %.

        Returns:
            ``monthly_requests`` × ``closed_share_pct``, rounded half up (12.5 → 13, as a reader counts).
        """
        return math.floor(monthly_requests * closed_share_pct / 100 + 0.5)
