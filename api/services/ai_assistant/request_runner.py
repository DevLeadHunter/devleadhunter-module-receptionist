"""Background runner of the assistant requests: the work that must survive a restart or wait for a time."""

from __future__ import annotations

import asyncio
import logging

from services.ai_assistant.request_alerts import ai_assistant_request_alerts
from services.ai_assistant.request_service import ai_assistant_request_service

logger = logging.getLogger(__name__)


class AiAssistantRequestRunner:
    """Every few minutes: lost announcements, held SMS, J+1 reminders and the operator's 48 h warnings."""

    @staticmethod
    async def run_loop(interval_seconds: int = 300) -> None:
        """
        Pick up the announcements an in-memory follow-up lost (deploy, crash), then run the timed alerts.

        Args:
            interval_seconds: Delay between passes (an SMS held for the night leaves within one pass).
        """
        while True:
            try:
                recovered: int = await ai_assistant_request_service.announce_pending()
                if recovered:
                    logger.info("Announced assistant requests picked up again: %s", recovered)
            except Exception:
                logger.exception("Assistant request runner pass failed")
            await ai_assistant_request_alerts.run_pass()
            await asyncio.sleep(interval_seconds)


async def run_ai_assistant_request_loop(interval_seconds: int = 300) -> None:
    """Entrypoint registered by the API lifespan."""
    await AiAssistantRequestRunner.run_loop(interval_seconds)
