"""
Contact details a visitor types straight into the chat (« rappelez-moi au 06 12 34 56 78 ») become the
conversation's request, exactly as the contact form would have made it.

What counts as a phone number or an email is the form's rule (``VisitorContact``). A message holds other figures
too, so a phone must also be written to be dialled: an international prefix, a leading zero (France, Belgium,
Switzerland) or a Luxembourg mobile; dates, hours and the business's own contact details are never taken. The
request is the session's one: the form sent later updates it instead of adding a second.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import ClassVar

from sqlalchemy.orm import Session

from models.ai_assistant import AiAssistant
from models.ai_assistant_request import AiAssistantRequest
from services.ai_assistant.request_service import ai_assistant_request_service
from services.ai_assistant.visitor_contact import VisitorContact

# 8 to 15 digits with the separators people type, « + » or « 00 » before them or not (the widget reads the same).
_PHONES_IN_TEXT = re.compile(r"(?:\+|00)?\d(?:[\s.()/-]*\d){7,14}")
_EMAILS_IN_TEXT = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]{2,}")
# « 01/10/2026 », « 1.10.26 », « 14h », « 9 h 30 », « 14:30 »: their figures would otherwise read as a phone number.
# A date has three groups only (« 06.12.34.56.78 » is a phone), an hour's « h » ends its word (« 78 hier » is not one).
_DATES_AND_HOURS = re.compile(
    r"(?<![\d/.-])\d{1,2}([/.-])\d{1,2}\1\d{2,4}(?![/.-]?\d)|\b\d{1,2}\s?h(?![^\W\d_])(?:\s?\d{2}\b)?|\b\d{1,2}:\d{2}\b",
    re.IGNORECASE,
)
_TRAILING_PUNCTUATION = ".,;:!?)»\"'"
# The significant digits of a number, whatever prefix it was written with (« +33 6… » and « 06… » are one number).
_SIGNIFICANT_DIGITS = 9


@dataclass(frozen=True)
class CapturedChatContact:
    """The request a chat message filled, with the name and contact it now carries."""

    request: AiAssistantRequest
    name: str
    contact: str


class AiAssistantChatContactCapture:
    """Reads a visitor's phone number or email in their chat message and files it as the session's request."""

    # The request's name when the visitor gave none: the business reads « Visiteur » and the contact beside it.
    FALLBACK_NAME: ClassVar[str] = "Visiteur"
    NAME_MAX_CHARS: ClassVar[int] = 64

    @classmethod
    def contact_in(cls, text: str, *, business_contacts: tuple[str, ...] = ()) -> str | None:
        """
        The last phone number or email address a visitor's message holds, when it can be theirs.

        Args:
            text: The visitor's message.
            business_contacts: The business's own phone numbers and emails, never taken for the visitor's.

        Returns:
            The contact as typed (trimmed), or None.
        """
        found: str | None = None
        found_at = -1
        for match in _EMAILS_IN_TEXT.finditer(text):
            email = match.group(0).rstrip(_TRAILING_PUNCTUATION)
            is_visitor_email = VisitorContact.is_email(email) and not cls._is_business(email, business_contacts)
            if match.start() > found_at and is_visitor_email:
                found, found_at = email, match.start()
        # Dates and hours are blanked in place: the positions of what is left stay the message's own.
        figures = _DATES_AND_HOURS.sub(lambda date_or_hour: " " * len(date_or_hour.group(0)), text)
        for match in _PHONES_IN_TEXT.finditer(figures):
            phone = match.group(0).strip()
            is_visitor_phone = cls._is_written_to_be_dialled(phone) and not cls._is_business(phone, business_contacts)
            if match.start() > found_at and is_visitor_phone:
                found, found_at = phone, match.start()
        return found

    def capture(
        self,
        db: Session,
        *,
        assistant: AiAssistant,
        session_id: str | None,
        language: str | None,
        visitor_message: str,
        visitor_name: str | None,
        is_test: bool,
    ) -> CapturedChatContact | None:
        """
        File the contact a visitor typed in the chat as the session's request (created, or updated like the form).

        Args:
            db: Active database session (committed).
            assistant: The assistant the visitor talks to.
            session_id: The widget session; without one nothing is filed (each turn would open a new request).
            language: The widget language.
            visitor_message: The visitor's latest message.
            visitor_name: The name the widget read in the conversation, when it read one.
            is_test: The operator testing (``?internal=1``): recorded, never announced.

        Returns:
            The filed request, or None when the message holds no contact of the visitor.
        """
        session = (session_id or "").strip()
        if not session:
            return None
        contact = self.contact_in(visitor_message, business_contacts=self._business_contacts(assistant))
        if contact is None:
            return None
        request, _created = ai_assistant_request_service.capture(
            db,
            assistant=assistant,
            name=self._name(db, assistant_id=assistant.id, session_id=session, visitor_name=visitor_name),
            contact=contact,
            need=None,
            language=language,
            session_id=session,
            is_test=is_test,
        )
        ai_assistant_request_service.schedule_follow_up(request.id)
        return CapturedChatContact(request=request, name=request.name, contact=request.contact)

    @classmethod
    def _name(cls, db: Session, *, assistant_id: int, session_id: str, visitor_name: str | None) -> str:
        """The name the visitor gave in the chat, else the one their session's last request carries."""
        given = " ".join((visitor_name or "").split())[: cls.NAME_MAX_CHARS]
        if given:
            return given
        previous: str | None = (
            db.query(AiAssistantRequest.name)
            .filter(AiAssistantRequest.assistant_id == assistant_id, AiAssistantRequest.session_id == session_id)
            .order_by(AiAssistantRequest.id.desc())
            .limit(1)
            .scalar()
        )
        return previous or cls.FALLBACK_NAME

    @staticmethod
    def _business_contacts(assistant: AiAssistant) -> tuple[str, ...]:
        """The business's own phone numbers and emails: its listing's, and the ones set on the assistant."""
        identity = (assistant.knowledge_json or {}).get("identity") or {}
        candidates = (assistant.phone, assistant.email, identity.get("phone"), identity.get("email"))
        return tuple(value for value in candidates if isinstance(value, str) and value.strip())

    @staticmethod
    def _is_written_to_be_dialled(phone: str) -> bool:
        """A phone of the form's rule that starts like one: « + », « 00 », a trunk « 0 », or a Luxembourg mobile."""
        if not VisitorContact.is_phone(phone):
            return False
        digits = re.sub(r"\D", "", phone)
        is_luxembourg_mobile = len(digits) == _SIGNIFICANT_DIGITS and digits.startswith("6")
        return phone.startswith("+") or digits.startswith("0") or is_luxembourg_mobile

    @staticmethod
    def _is_business(contact: str, business_contacts: tuple[str, ...]) -> bool:
        """Whether a contact is one of the business's own (a phone compared on its significant digits)."""
        if VisitorContact.is_email(contact):
            return any(contact.strip().lower() == known.strip().lower() for known in business_contacts)
        digits = re.sub(r"\D", "", contact)[-_SIGNIFICANT_DIGITS:]
        return any(
            not VisitorContact.is_email(known) and re.sub(r"\D", "", known)[-_SIGNIFICANT_DIGITS:] == digits
            for known in business_contacts
        )


ai_assistant_chat_contact_capture = AiAssistantChatContactCapture()
