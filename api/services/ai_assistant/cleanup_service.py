"""
The hourly upkeep of the receptionist module: the demos past their countdown expire, the stale unpaid checkouts go,
the conversations, the ids of the emails read and the visitors' photos past their retention are forgotten, and the
« Pour démarrer » reminders leave.
"""

from __future__ import annotations

import asyncio
import logging

from core.database import SessionLocal
from services.ai_assistant.assistant_purge import ai_assistant_purge_service
from services.ai_assistant.assistant_service import ai_assistant_service
from services.ai_assistant.conversation_service import ai_assistant_conversation_service
from services.ai_assistant.mailbox_service import ai_assistant_mailbox_service
from services.ai_assistant.photo_service import ai_assistant_photo_service
from services.ai_assistant.start_reminders import ai_assistant_start_reminders
from services.assistant_subscription_service import assistant_subscription_service

logger = logging.getLogger(__name__)


class AiAssistantCleanupRunner:
    """Runs the receptionist module's hourly upkeep (a sold assistant never expires)."""

    @staticmethod
    async def run_loop(interval_seconds: int = 3600) -> None:
        """
        Periodically expire the demo assistants whose countdown ended, drop stale unpaid checkouts, forget the
        conversations, the emails read and the visitor photos past their retention, send the « Pour démarrer »
        reminders due, and finish erasing the deleted assistants.

        Args:
            interval_seconds: Delay between two passes.
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
                forgotten_emails: int = ai_assistant_mailbox_service.purge_old_messages(db)
                if forgotten_emails:
                    logger.info("Purged mailbox emails read past retention: %s", forgotten_emails)
            except Exception as exc:
                logger.exception("Assistant demo expiry failed: %s", exc)
                db.rollback()
            # The « Pour démarrer » reminders, on their own so a mail failure never blocks the purges.
            try:
                reminded: int = await ai_assistant_start_reminders.send_due(db)
                if reminded:
                    logger.info("Sent assistant start reminders: %s", reminded)
            except Exception:
                logger.exception("Assistant start reminders failed")
                db.rollback()
            try:
                erased: int = await ai_assistant_purge_service.purge_leftovers(db)
                if erased:
                    logger.info("Erased what deleted assistants had left: %s", erased)
            except Exception:
                logger.exception("Deleted assistants purge failed")
                db.rollback()
            # Its own step: the 90-day deletion promise must not depend on the expiry pass succeeding.
            try:
                photos: int = await ai_assistant_photo_service.purge_expired(db)
                if photos:
                    logger.info("Deleted assistant photos past retention or off-topic: %s", photos)
            except Exception:
                logger.exception("Assistant photo purge failed")
            finally:
                db.close()

            await asyncio.sleep(interval_seconds)


async def run_ai_assistant_cleanup_loop(interval_seconds: int = 3600) -> None:
    """Entrypoint registered by the API lifespan."""
    await AiAssistantCleanupRunner.run_loop(interval_seconds)
