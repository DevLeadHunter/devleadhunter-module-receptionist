"""The widget's loader reports the website it runs on: the business's own site, once the line is pasted."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from core.config import settings
from models.ai_assistant import AiAssistant

# A hostname as a browser reads it: dotted labels of letters, digits and hyphens, a top-level domain of letters.
_HOSTNAME = re.compile(r"^(?=.{4,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
# A sighting on the same host within this delay is not written again.
_REFRESH_AFTER = timedelta(hours=1)


class AiAssistantInstallationService:
    """Keeps where and when a sold assistant's widget was last seen on a real website."""

    @staticmethod
    def clean_host(raw: str) -> str | None:
        """
        The hostname worth recording.

        Args:
            raw: The hostname the loader sent.

        Returns:
            The hostname in lowercase, or None when it is malformed, local, or the demo host itself.
        """
        host = (raw or "").strip().lower().rstrip(".")
        if not _HOSTNAME.fullmatch(host):
            return None
        ours = (urlparse(settings.demo_host_base_url).hostname or "").lower()
        if host == ours or host.endswith((".localhost", ".local", ".test")):
            return None
        return host

    @classmethod
    def record(cls, db: Session, assistant: AiAssistant, raw_host: str, *, now: datetime | None = None) -> bool:
        """
        Note the sighting; a repeat on the same host within the hour changes nothing.

        Args:
            db: Active database session.
            assistant: The assistant the loader serves.
            raw_host: The hostname the loader sent.
            now: Current time (tests); defaults to now.

        Returns:
            True when the assistant was updated.
        """
        host = cls.clean_host(raw_host)
        if host is None:
            return False
        current = (now or datetime.now(UTC)).replace(tzinfo=None)
        if (
            assistant.installed_host == host
            and assistant.installed_at is not None
            and current - assistant.installed_at < _REFRESH_AFTER
        ):
            return False
        assistant.installed_host = host
        assistant.installed_at = current
        db.commit()
        return True


ai_assistant_installation_service = AiAssistantInstallationService()
