"""
The reply a receptionist leaves as a draft: an RFC 822 message in the customer's thread, ready for Gmail's API.

The draft answers the customer's email in its own thread: « Re: » of its subject, ``In-Reply-To`` its Message-ID and
``References`` the chain that led to it (Gmail threads a draft only when all three match). The reply is plain UTF-8
text followed by the customer's email quoted, as a mail client writes a reply.
"""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from datetime import datetime
from email import policy
from email.errors import HeaderParseError
from email.headerregistry import Address
from email.message import EmailMessage
from typing import ClassVar

from services.conversation_service import build_reply_subject
from services.french_date_formatter import FrenchDateFormatter


@dataclass(frozen=True)
class MailReplyDraft:
    """A reply to write in a thread: who it goes from and to, the email it answers, its text."""

    from_address: str
    to_address: str
    to_name: str | None
    # The subject, Message-ID and References of the customer's email.
    subject: str
    message_id: str | None
    references: str | None
    body: str
    # The customer's words, quoted under the reply, and when they came in (business time).
    quoted_text: str = ""
    quoted_at: datetime | None = None


class AiAssistantMailDraftBuilder:
    """Builds the RFC 822 reply of a draft and encodes it for Gmail."""

    QUOTE_MAX_CHARS: ClassVar[int] = 3000
    MAX_REFERENCES: ClassVar[int] = 20
    _MESSAGE_ID: ClassVar[re.Pattern[str]] = re.compile(r"<[^<>\s]+>")

    @classmethod
    def build(cls, draft: MailReplyDraft) -> EmailMessage:
        """
        The reply as an email message.

        Args:
            draft: What the reply holds.

        Returns:
            The message, its headers on one line each (a header read from the customer's email cannot add another).
        """
        message = EmailMessage()
        message["From"] = cls._one_line(draft.from_address)
        message["To"] = cls._recipient(draft)
        message["Subject"] = build_reply_subject(cls._one_line(draft.subject))
        references = cls._message_ids(draft.references)
        own_id = cls._message_ids(draft.message_id)
        if own_id:
            message["In-Reply-To"] = own_id[-1]
            chain = [reference for reference in references if reference != own_id[-1]] + [own_id[-1]]
            message["References"] = " ".join(chain[-cls.MAX_REFERENCES :])
        message.set_content(cls._body_with_quote(draft), charset="utf-8")
        return message

    @classmethod
    def raw(cls, draft: MailReplyDraft) -> str:
        """
        The reply as Gmail's API takes it.

        Args:
            draft: What the reply holds.

        Returns:
            The RFC 822 bytes (CRLF line ends), base64url-encoded.
        """
        return base64.urlsafe_b64encode(cls.build(draft).as_bytes(policy=policy.SMTP)).decode("ascii")

    @classmethod
    def _body_with_quote(cls, draft: MailReplyDraft) -> str:
        """The reply, then « Le …, X a écrit : » and the customer's lines each behind « > »."""
        body = draft.body.strip()
        quoted = draft.quoted_text.strip()[: cls.QUOTE_MAX_CHARS]
        if not quoted:
            return f"{body}\n"
        name = cls._one_line(draft.to_name or "")
        address = cls._one_line(draft.to_address)
        sender = f"{name} <{address}>" if name else address
        when = (
            f"Le {FrenchDateFormatter.long_date(draft.quoted_at)} à {draft.quoted_at:%H:%M}, "
            if draft.quoted_at
            else ""
        )
        lines = "\n".join(f"> {line}".rstrip() for line in quoted.splitlines())
        return f"{body}\n\n{when}{sender} a écrit :\n{lines}\n"

    @classmethod
    def _recipient(cls, draft: MailReplyDraft) -> Address | str:
        """The customer as the ``To`` header names them; their address alone when the name cannot go with it."""
        address = cls._one_line(draft.to_address)
        name = cls._one_line(draft.to_name or "")
        if not name:
            return address
        try:
            return Address(display_name=name, addr_spec=address)
        except (HeaderParseError, ValueError, IndexError):
            return address

    @classmethod
    def _message_ids(cls, value: str | None) -> list[str]:
        """The Message-IDs a header holds (« <…> » tokens), in order."""
        return cls._MESSAGE_ID.findall(value or "")

    @staticmethod
    def _one_line(value: str) -> str:
        """A header value on a single line: line breaks and runs of spaces become one space."""
        return " ".join(value.split())
