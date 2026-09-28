"""
The monthly report of the sold assistants: what each one brought its client over the month that ended.

From 8 h (Paris time) on the first days of a month, every assistant sold to a paying client gets the
report of the month before: conversations, requests by type, requests with a photo, languages, the
share received outside opening hours, the handling delay and the questions visitors ask the most
(``report_stats``). The client receives it by email in the assistant's accent colour, the operator in blind copy. A month
without a single conversation or request sends the visibility checks instead and warns the operator:
a silent assistant is a client about to cancel. Only the service counts: a client who paid during the
month is reported from that day, a demo or a cancelled client never gets a report, the operator's own
test visits are left out. A report row is written before anything is sent and each send attempt is
claimed on it, so a report never leaves twice; a failed send is retried twice, an hour apart.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.database import SessionLocal
from enums.ai_assistant_status import AiAssistantStatus
from enums.assistant_subscription_status import LIVE_SUBSCRIPTION_STATUSES
from models.ai_assistant import AiAssistant
from models.ai_assistant_report import AiAssistantReport
from models.ai_assistant_subscription import AiAssistantSubscription
from models.prospect_db import ProspectDB
from models.user import User
from services.ai_assistant.assistant_service import ai_assistant_service
from services.ai_assistant.business_mailer import AiAssistantBusinessMailer
from services.ai_assistant.client_links import AiAssistantClientLinks
from services.ai_assistant.config_builder import ai_assistant_config_builder
from services.ai_assistant.message_delivery import AiAssistantMessageDelivery
from services.ai_assistant.opening_hours import OpeningHoursCalendar
from services.ai_assistant.report_email import AiAssistantReportEmail, MonthlyStats, ReportEmailContent
from services.ai_assistant.report_stats import AiAssistantReportStats
from services.french_date_formatter import FrenchDateFormatter
from services.notification_service import notification_service

logger = logging.getLogger(__name__)

# The reports leave on the first days of the month (a server down on the 1st catches up), from 8 h.
REPORT_DAYS = 3
SEND_FROM_HOUR = 8
# A client who paid in the last days of a month gets their first report the month after.
MIN_SERVICE_DAYS = 7
MAX_SEND_ATTEMPTS = 3
RETRY_DELAY = timedelta(hours=1)
# A subscriber silent for that long is flagged on the dashboard, once subscribed for that long.
CHURN_WINDOW = timedelta(days=30)
LOOP_INTERVAL_SECONDS = 600


def _utc_now() -> datetime:
    """Current time as naive UTC, the storage convention."""
    return datetime.now(UTC).replace(tzinfo=None)


@dataclass(frozen=True)
class ReportPeriod:
    """A calendar month in Paris time, with its bounds in naive UTC (end excluded)."""

    first_day: date
    start: datetime
    end: datetime

    @property
    def key(self) -> str:
        """The month as stored on the report row (« 2026-09 »)."""
        return f"{self.first_day.year:04d}-{self.first_day.month:02d}"

    @classmethod
    def of_month(cls, first_day: date) -> ReportPeriod:
        """
        A calendar month.

        Args:
            first_day: Any day of the month.

        Returns:
            The month and its bounds.
        """
        first_day = first_day.replace(day=1)
        next_month = (first_day + timedelta(days=32)).replace(day=1)
        return cls(
            first_day=first_day,
            start=OpeningHoursCalendar.to_utc(datetime(first_day.year, first_day.month, 1)),
            end=OpeningHoursCalendar.to_utc(datetime(next_month.year, next_month.month, 1)),
        )

    @classmethod
    def before(cls, local_day: date) -> ReportPeriod:
        """
        The calendar month before a day.

        Args:
            local_day: A day in Paris time.

        Returns:
            The previous month.
        """
        return cls.of_month(local_day.replace(day=1) - timedelta(days=1))

    @classmethod
    def of_key(cls, key: str) -> ReportPeriod:
        """
        The month of a report row.

        Args:
            key: The stored month (« 2026-09 »).

        Returns:
            The month and its bounds.
        """
        year, month = key.split("-")
        return cls.of_month(date(int(year), int(month), 1))


class AiAssistantReportService:
    """Computes and sends the monthly report of each sold assistant, and flags the silent subscribers."""

    async def run_loop(self, interval_seconds: int = LOOP_INTERVAL_SECONDS) -> None:
        """
        Send the due reports every few minutes, apart from the request alerts (a slow model never delays them).

        Args:
            interval_seconds: Delay between passes.
        """
        while True:
            await self.run_pass()
            await asyncio.sleep(interval_seconds)

    async def run_pass(self) -> None:
        """One pass over the due reports, in its own session; never raises."""
        db = SessionLocal()
        try:
            await self.send_due_reports(db)
        except Exception:
            logger.exception("Assistant monthly reports pass failed")
            db.rollback()
        finally:
            db.close()

    async def send_due_reports(self, db: Session, *, now: datetime | None = None) -> int:
        """
        Send the reports of the month that ended, when it is time: the new ones, then the retries.

        Args:
            db: Active database session (committed).
            now: Current naive UTC time (tests); defaults to now.

        Returns:
            How many reports were emailed.
        """
        current = now or _utc_now()
        local = OpeningHoursCalendar.to_business_time(current)
        if local.day > REPORT_DAYS or local.hour < SEND_FROM_HOUR:
            return 0
        period = ReportPeriod.before(local.date())
        sent = 0
        for assistant in self._unreported_subscribers(db, period):
            try:
                sent += int(await self.report(db, assistant, period, now=now))
            except Exception:
                logger.exception("Monthly report of assistant %s failed", assistant.id)
                db.rollback()
        for row in self._retries(db, period, current):
            try:
                sent += int(await self._attempt(db, row, now=now))
            except Exception:
                logger.exception("Monthly report %s retry failed", row.id)
                db.rollback()
        return sent

    async def report(
        self, db: Session, assistant: AiAssistant, period: ReportPeriod, *, now: datetime | None = None
    ) -> bool:
        """
        Claim one assistant's report of a month, then make its first send attempt.

        Args:
            db: Active database session (committed).
            assistant: A sold assistant.
            period: The reported month.
            now: Current naive UTC time (tests); defaults to now.

        Returns:
            True when the report was emailed; False when it is not due (paid during the month's last week
            or after it, already claimed) or could not be sent yet.
        """
        if self.service_start(db, assistant.id, period) is None:
            return False
        row = AiAssistantReport(
            user_id=assistant.user_id,
            prospect_id=assistant.prospect_id,
            assistant_id=assistant.id,
            month=period.key,
        )
        db.add(row)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            return False
        return await self._attempt(db, row, now=now)

    async def compute(self, db: Session, assistant: AiAssistant, *, start: datetime, end: datetime) -> MonthlyStats:
        """The figures of an assistant over a period, test visits and requests excluded (see ``report_stats``)."""
        return await AiAssistantReportStats.compute(db, assistant, start=start, end=end)

    def service_start(self, db: Session, assistant_id: int, period: ReportPeriod) -> datetime | None:
        """
        Where an assistant's report of a month starts: the month's start, or the payment when it came later.

        Args:
            db: Active database session.
            assistant_id: The assistant.
            period: The reported month.

        Returns:
            The start (naive UTC), or None when the service covers less than a week of the month.
        """
        subscribed_at = self.subscribed_at(db, assistant_id)
        start = max(period.start, subscribed_at) if subscribed_at else period.start
        return start if period.end - start >= timedelta(days=MIN_SERVICE_DAYS) else None

    @staticmethod
    def subscribed_at(db: Session, assistant_id: int) -> datetime | None:
        """
        When the running subscription was paid (``created_at``, the checkout, for rows paid before it was kept).

        Args:
            db: Active database session.
            assistant_id: The assistant.

        Returns:
            The payment (naive UTC), or None when no subscription is running.
        """
        return (
            db.query(func.min(func.coalesce(AiAssistantSubscription.activated_at, AiAssistantSubscription.created_at)))
            .filter(
                AiAssistantSubscription.ai_assistant_id == assistant_id,
                AiAssistantSubscription.status.in_(LIVE_SUBSCRIPTION_STATUSES),
            )
            .scalar()
        )

    @staticmethod
    def is_churn_risk(
        *,
        status: str,
        subscribed_at: datetime | None,
        conversations_30d: int,
        requests_30d: int,
        now: datetime | None = None,
    ) -> bool:
        """
        Whether a subscriber's assistant went silent: sold, paid for 30 days, nothing in the last 30.

        Args:
            status: The assistant's status.
            subscribed_at: When its running subscription was paid (None = no running subscription).
            conversations_30d: Conversations active over the last 30 days (tests excluded).
            requests_30d: Requests over the last 30 days (tests excluded).
            now: Current naive UTC time (tests); defaults to now.

        Returns:
            True when the dashboard should flag a churn risk.
        """
        if status != AiAssistantStatus.DELIVERED.value or subscribed_at is None:
            return False
        if subscribed_at > (now or _utc_now()) - CHURN_WINDOW:
            return False
        return conversations_30d == 0 and requests_30d == 0

    async def _attempt(self, db: Session, row: AiAssistantReport, *, now: datetime | None = None) -> bool:
        """Claim one send attempt of a report for a client still paying, compute its figures the first time, send it."""
        assistant = db.get(AiAssistant, row.assistant_id)
        if (
            assistant is None
            or assistant.deleted_at is not None
            or assistant.status != AiAssistantStatus.DELIVERED.value
            or self.subscribed_at(db, assistant.id) is None
        ):
            return False
        current = now or _utc_now()
        if not self._claim_attempt(db, row, current):
            return False
        period = ReportPeriod.of_key(row.month)
        start = self.service_start(db, assistant.id, period) or period.start
        if row.stats_json is None:
            stats = await self.compute(db, assistant, start=start, end=period.end)
            row.stats_json = asdict(stats)
            row.is_empty = stats.is_empty
            db.commit()
            if stats.is_empty:
                await self._warn_operator(db, assistant, period)
        else:
            stats = MonthlyStats.from_json(row.stats_json)
        content = ReportEmailContent(
            business_name=assistant.business_name,
            assistant_name=assistant.assistant_name,
            persona_gender=ai_assistant_config_builder.resolve_persona_gender(assistant.assistant_name),
            month_first_day=period.first_day,
            stats=stats,
            accent_color=ai_assistant_service.accent_color(assistant),
            website=assistant.custom_domain or self._prospect_website(db, assistant.prospect_id),
            service_start=OpeningHoursCalendar.to_business_time(start).date() if start > period.start else None,
            client_space_url=AiAssistantClientLinks.url(assistant.id),
        )
        failure = await self._deliver(db, assistant, content)
        if failure is not None:
            # Retries run on the report days only: a failure late on the last one is final.
            will_retry = row.attempts < MAX_SEND_ATTEMPTS and (
                OpeningHoursCalendar.to_business_time(current + RETRY_DELAY).day <= REPORT_DAYS
            )
            self._log_failure(assistant, row, failure, will_retry=will_retry)
            return False
        row.sent_at = current
        db.commit()
        return True

    @staticmethod
    def _claim_attempt(db: Session, row: AiAssistantReport, current: datetime) -> bool:
        """Atomically count one more send attempt of an unsent report, so two passes never both send it."""
        return AiAssistantMessageDelivery.claim(
            db,
            row,
            AiAssistantReport.sent_at.is_(None),
            AiAssistantReport.attempts == row.attempts,
            AiAssistantReport.attempts < MAX_SEND_ATTEMPTS,
            values={
                AiAssistantReport.attempts: AiAssistantReport.attempts + 1,
                AiAssistantReport.last_attempt_at: current,
            },
        )

    @staticmethod
    def _unreported_subscribers(db: Session, period: ReportPeriod) -> list[AiAssistant]:
        """The sold assistants of paying clients (active or retrying payment) without a report for the month."""
        live = select(AiAssistantSubscription.ai_assistant_id).where(
            AiAssistantSubscription.status.in_(LIVE_SUBSCRIPTION_STATUSES),
            AiAssistantSubscription.ai_assistant_id.is_not(None),
        )
        reported = select(AiAssistantReport.assistant_id).where(AiAssistantReport.month == period.key)
        return (
            db.query(AiAssistant)
            .filter(
                AiAssistant.status == AiAssistantStatus.DELIVERED.value,
                AiAssistant.deleted_at.is_(None),
                AiAssistant.id.in_(live),
                AiAssistant.id.not_in(reported),
            )
            .order_by(AiAssistant.id)
            .all()
        )

    @staticmethod
    def _retries(db: Session, period: ReportPeriod, current: datetime) -> list[AiAssistantReport]:
        """The month's unsent reports with an attempt left, the last one over an hour ago."""
        return (
            db.query(AiAssistantReport)
            .filter(
                AiAssistantReport.month == period.key,
                AiAssistantReport.sent_at.is_(None),
                AiAssistantReport.attempts < MAX_SEND_ATTEMPTS,
                or_(
                    AiAssistantReport.last_attempt_at.is_(None),
                    AiAssistantReport.last_attempt_at <= current - RETRY_DELAY,
                ),
            )
            .order_by(AiAssistantReport.id)
            .all()
        )

    @staticmethod
    async def _warn_operator(db: Session, assistant: AiAssistant, period: ReportPeriod) -> None:
        """Push the operator the silent month of a subscriber; never raises."""
        try:
            await notification_service.notify_assistant_inactive(
                db,
                user_id=assistant.user_id,
                prospect_id=assistant.prospect_id,
                fallback_name=assistant.business_name,
                month_label=FrenchDateFormatter.month_year(period.first_day),
            )
        except Exception:
            logger.warning("Silent-month warning for assistant %s failed", assistant.id, exc_info=True)

    @staticmethod
    def _prospect_website(db: Session, prospect_id: int | None) -> str | None:
        """The prospect's own site, where a sold widget is embedded."""
        if prospect_id is None:
            return None
        return db.query(ProspectDB.website).filter(ProspectDB.id == prospect_id).scalar()

    @staticmethod
    async def _deliver(db: Session, assistant: AiAssistant, content: ReportEmailContent) -> str | None:
        """
        Email the report from the operator's identity: to the business, the operator in blind copy, or to
        the operator alone when the business has no address.

        Args:
            db: Active database session.
            assistant: The assistant.
            content: What the email shows.

        Returns:
            None when the email left, else why it did not (it never raises).
        """
        business = AiAssistantBusinessMailer.business_email(db, assistant)
        operator = db.query(User.email).filter(User.id == assistant.user_id).scalar()
        recipient = business or operator
        if not recipient:
            return "Aucune adresse : ni celle du commerçant, ni celle de l'owner."
        bcc = [operator] if business and operator and operator.strip().lower() != business.lower() else None
        return await AiAssistantBusinessMailer.send(
            db,
            assistant,
            AiAssistantReportEmail.render(content),
            recipient=recipient,
            recipient_name=assistant.business_name if business else None,
            bcc=bcc,
        )

    @staticmethod
    def _log_failure(assistant: AiAssistant, row: AiAssistantReport, reason: str, *, will_retry: bool) -> None:
        """Record in the activity log why a monthly report did not leave, and whether it will be retried."""
        logger.warning("Monthly report %s of assistant %s not sent: %s", row.id, assistant.id, reason)
        retry = "nouvel essai prévu" if will_retry else "abandonné"
        AiAssistantMessageDelivery.record_warning(
            assistant,
            action="assistant_report_not_sent",
            title="rapport mensuel non envoyé",
            detail=f"{reason} (essai {row.attempts}/{MAX_SEND_ATTEMPTS}, {retry})",
        )


ai_assistant_report_service = AiAssistantReportService()
