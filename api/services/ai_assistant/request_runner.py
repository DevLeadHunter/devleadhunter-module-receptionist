"""Background runner of the assistant requests: the work that must survive a restart."""

from __future__ import annotations

import asyncio
import logging

from services.ai_assistant.request_service import ai_assistant_request_service

logger = logging.getLogger(__name__)


class AiAssistantRequestRunner:
    """Periodically picks up the request announcements an in-memory follow-up lost (deploy, crash)."""

    @staticmethod
    async def run_loop(interval_seconds: int = 300) -> None:
        """
        Announce, every few minutes, the requests whose background follow-up never finished.

        Args:
            interval_seconds: Delay between passes.
        """
        while True:
            try:
                recovered: int = await ai_assistant_request_service.announce_pending()
                if recovered:
                    logger.info("Announced assistant requests picked up again: %s", recovered)
            except Exception:
                logger.exception("Assistant request runner pass failed")
            await asyncio.sleep(interval_seconds)


async def run_ai_assistant_request_loop(interval_seconds: int = 300) -> None:
    """Entrypoint registered by the API lifespan."""
    await AiAssistantRequestRunner.run_loop(interval_seconds)
