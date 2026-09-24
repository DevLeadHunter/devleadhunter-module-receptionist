"""Background expiry for AI assistant demos past their countdown."""

from __future__ import annotations

import asyncio
import logging

from core.database import SessionLocal
from services.ai_assistant.assistant_service import ai_assistant_service
from services.ai_assistant.conversation_service import ai_assistant_conversation_service
from services.assistant_subscription_service import assistant_subscription_service

logger = logging.getLogger(__name__)


class AiAssistantCleanupRunner:
    """Runs periodic expiry passes for assistant demos past their TTL (sold assistants never expire)."""

    @staticmethod
    async def run_loop(interval_seconds: int = 3600) -> None:
        """
        Periodically expire the demo assistants whose countdown ended, and drop stale unpaid checkouts.

        Args:
            interval_seconds: Delay between expiry passes.
        """
        while True:
            db = SessionLocal()
            try:
                expired: int = ai_assistant_service.expire_due_assistants(db)
                if expired:
                    logger.info("Expired assistant demos: %s", expired)
                purged: int = assistant_subscription_service.purge_stale_incomplete_rows(db)
                if purged:
                    logger.info("Purged stale unpaid assistant checkouts: %s", purged)
                forgotten: int = ai_assistant_conversation_service.purge_old(db)
                if forgotten:
                    logger.info("Purged assistant conversations past retention: %s", forgotten)
            except Exception as exc:
                logger.exception("Assistant demo expiry failed: %s", exc)
            finally:
                db.close()

            await asyncio.sleep(interval_seconds)


async def run_ai_assistant_cleanup_loop(interval_seconds: int = 3600) -> None:
    """Entrypoint registered by the API lifespan."""
    await AiAssistantCleanupRunner.run_loop(interval_seconds)
