"""Enums of a sold receptionist's Gmail mailbox: its connection, and what it did with each email it read."""

from enum import Enum


class AiAssistantMailboxStatus(str, Enum):
    """The mailbox is read (``connected``) or its client must connect it again (``error``)."""

    CONNECTED = "connected"
    ERROR = "error"


class AiAssistantMailboxConnection(str, Enum):
    """
    Where a receptionist's mailbox stands.

    ``disabled``: the operator has not switched it on for this receptionist; ``unavailable``: Google or the mailbox's
    redirect address is not configured on the server.
    """

    DISABLED = "disabled"
    UNAVAILABLE = "unavailable"
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    ERROR = "error"


class AiAssistantMailboxMessageOutcome(str, Enum):
    """
    What the receptionist did with an email: sorted out before any model call (``skipped``), read by the model and
    not a customer's request (``ignored``), answered with a draft (``drafted``), or failed (retried a few times).
    """

    SKIPPED = "skipped"
    IGNORED = "ignored"
    DRAFTED = "drafted"
    FAILED = "failed"


class AiAssistantMailSkipReason(str, Enum):
    """Why an email is sorted out before any model call: it cannot be a customer's request."""

    SPAM = "spam"
    OWN_MESSAGE = "own_message"
    NOT_IN_INBOX = "not_in_inbox"
    CATEGORY = "category"
    BEFORE_CONNECTION = "before_connection"
    MAILING_LIST = "mailing_list"
    AUTOMATED = "automated"
    NO_REPLY_SENDER = "no_reply_sender"
    CALENDAR_INVITE = "calendar_invite"
    EMPTY = "empty"
