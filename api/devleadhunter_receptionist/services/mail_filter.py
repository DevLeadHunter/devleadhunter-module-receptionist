"""
What the receptionist never reads with the model: the emails that cannot be a customer's request.

Every rule reads what Gmail and the email's own headers say (labels, list and bulk headers, autoresponders, no-reply
senders, invitations), so newsletters, notifications and the business's own messages never cost a model call. A
form notification (sent by the website, the customer in ``Reply-To``) is answered to the customer.
"""

from __future__ import annotations

import re
from datetime import datetime
from email.utils import getaddresses
from typing import ClassVar

from enums.ai_assistant_mailbox import AiAssistantMailSkipReason
from services.ai_assistant.gmail_client import GmailMessage
from services.reply_capture_service import is_auto_reply


class AiAssistantMailFilter:
    """Sorts out, before any model call, the emails that cannot be a customer's request."""

    SPAM_LABELS: ClassVar[frozenset[str]] = frozenset({"SPAM", "TRASH"})
    OWN_LABELS: ClassVar[frozenset[str]] = frozenset({"SENT", "DRAFT", "CHAT"})
    SKIPPED_CATEGORIES: ClassVar[frozenset[str]] = frozenset(
        {"CATEGORY_PROMOTIONS", "CATEGORY_SOCIAL", "CATEGORY_UPDATES", "CATEGORY_FORUMS"}
    )
    BULK_PRECEDENCES: ClassVar[frozenset[str]] = frozenset({"bulk", "list", "junk"})
    _NO_REPLY_SENDER: ClassVar[re.Pattern[str]] = re.compile(
        r"no[-_.]?reply|do[-_.]?not[-_.]?reply|ne[-_.]?pas[-_.]?repondre|mailer[-_.]?daemon|^postmaster$|"
        r"^bounces?([-_.+].*)?$|^notifications?([-_.+].*)?$|^newsletters?([-_.+].*)?$",
        re.IGNORECASE,
    )

    @classmethod
    def skip_reason(
        cls, message: GmailMessage, *, mailbox_address: str, connected_at: datetime
    ) -> AiAssistantMailSkipReason | None:
        """
        Why an email is not worth a model call, if it is not.

        Args:
            message: The email (its headers at least; its parts too once read in full).
            mailbox_address: The connected address: its own messages are never answered.
            connected_at: When the mailbox was connected, naive UTC: older emails are the business's past.

        Returns:
            The reason, or None when the email may be a customer's request.
        """
        labels = message.label_ids
        if labels & cls.SPAM_LABELS:
            return AiAssistantMailSkipReason.SPAM
        if labels & cls.OWN_LABELS:
            return AiAssistantMailSkipReason.OWN_MESSAGE
        if "INBOX" not in labels:
            return AiAssistantMailSkipReason.NOT_IN_INBOX
        if labels & cls.SKIPPED_CATEGORIES:
            return AiAssistantMailSkipReason.CATEGORY
        if message.received_at is not None and message.received_at < connected_at:
            return AiAssistantMailSkipReason.BEFORE_CONNECTION
        headers = message.headers
        if "list-unsubscribe" in headers or "list-id" in headers:
            return AiAssistantMailSkipReason.MAILING_LIST
        if headers.get("precedence", "").strip().lower() in cls.BULK_PRECEDENCES:
            return AiAssistantMailSkipReason.MAILING_LIST
        if is_auto_reply(headers.get("subject"), headers):
            return AiAssistantMailSkipReason.AUTOMATED
        customer = cls.customer_address(message)
        if customer is None:
            return AiAssistantMailSkipReason.NO_REPLY_SENDER
        if customer == mailbox_address.strip().lower():
            return AiAssistantMailSkipReason.OWN_MESSAGE
        if cls._NO_REPLY_SENDER.search(customer.split("@", 1)[0]):
            return AiAssistantMailSkipReason.NO_REPLY_SENDER
        if "text/calendar" in headers.get("content-type", "").lower():
            return AiAssistantMailSkipReason.CALENDAR_INVITE
        return None

    @staticmethod
    def body_skip_reason(message: GmailMessage) -> AiAssistantMailSkipReason | None:
        """
        Why an email read in full is not worth a model call: an invitation in its parts, or nothing to read.

        Args:
            message: The email, read with its parts.

        Returns:
            The reason, or None when the email may be a customer's request.
        """
        if message.has_calendar_invite:
            return AiAssistantMailSkipReason.CALENDAR_INVITE
        if not message.text.strip() and not message.headers.get("subject", "").strip():
            return AiAssistantMailSkipReason.EMPTY
        return None

    @staticmethod
    def customer_address(message: GmailMessage) -> str | None:
        """
        Who the reply goes to: the ``Reply-To`` address when there is one (a website's form), else the sender.

        Args:
            message: The email.

        Returns:
            The address in lower case, or None when neither header holds one.
        """
        for header in ("reply-to", "from"):
            for _name, address in getaddresses([message.headers.get(header, "")]):
                cleaned = address.strip().lower()
                if "@" in cleaned and " " not in cleaned:
                    return cleaned
        return None

    @staticmethod
    def customer_display_name(message: GmailMessage) -> str | None:
        """
        The name the customer's address carries (« Hélène Dupré » of ``Hélène Dupré <…>``), when it has one.

        Args:
            message: The email.

        Returns:
            The display name on one line, or None.
        """
        for header in ("reply-to", "from"):
            for name, address in getaddresses([message.headers.get(header, "")]):
                if "@" in address:
                    cleaned = " ".join(name.split()).strip("\"' ")
                    return cleaned or None
        return None
