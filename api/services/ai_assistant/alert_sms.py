"""
The owner's alert SMS: one GSM-7 segment, the summary cut word by word to fit, then the client-space link.

A new request opens on its type (or on the appointment booked in the agenda), a reminder on the day it came in;
the wished half-days come before the summary and are never cut. A request that came by email says so, and that its
reply waits as a draft in Gmail.
"""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar

from enums.ai_assistant_request import AiAssistantRequestType
from services.sms.gsm_segments import segment_count, to_strict_gsm7


class AlertSms:
    """Writes the owner's SMS: one GSM-7 segment, the summary cut to fit, then the client-space link."""

    LABELS: ClassVar[dict[AiAssistantRequestType, str]] = {
        AiAssistantRequestType.QUESTION: "Nouvelle question",
        AiAssistantRequestType.QUOTE: "Nouvelle demande de devis",
        AiAssistantRequestType.APPOINTMENT: "Nouvelle demande de RDV",
        AiAssistantRequestType.URGENT: "URGENT, nouvelle demande",
        AiAssistantRequestType.OTHER: "Nouvelle demande",
    }
    REMINDER_LABELS: ClassVar[dict[AiAssistantRequestType, str]] = {
        AiAssistantRequestType.QUESTION: "question",
        AiAssistantRequestType.QUOTE: "demande de devis",
        AiAssistantRequestType.APPOINTMENT: "demande de RDV",
        AiAssistantRequestType.URGENT: "demande urgente",
        AiAssistantRequestType.OTHER: "demande",
    }
    # The contact is what the owner acts on: kept whole up to 60 characters, the name is cut first.
    _NAME_MAX_CHARS = 30
    _CONTACT_MAX_CHARS = 60
    # The summary comes before the client-space link: the link goes when it would leave less than this.
    _MIN_SUMMARY_WITH_LINK = 30
    # The shorter name tried before giving up the second wished half-day.
    _SHORT_NAME_MAX_CHARS = 15
    # Where the reply to a request that came by email waits.
    GMAIL_DRAFT_NOTE = " Réponse en brouillon dans Gmail."

    @classmethod
    def new_request(
        cls,
        *,
        request_type: AiAssistantRequestType,
        name: str,
        contact: str,
        summary: str | None,
        has_photos: bool,
        link: str | None = None,
        slots: tuple[str, ...] = (),
        booked: str | None = None,
        is_email_request: bool = False,
    ) -> str:
        """
        The SMS announcing a request (« Nouvelle demande de devis (photo) de Marc, 06… : … Suivi : … »).

        Args:
            request_type: Its type.
            name: The visitor's name.
            contact: Their phone or email.
            summary: What they need.
            has_photos: Whether they sent photos.
            link: The client space, without scheme; dropped when it cannot fit.
            slots: Wished half-days (« mar. 22/09 après-midi »), kept before the summary and never cut.
            booked: The appointment booked in the agenda (« mar. 29/09 à 14:30 (Révision) »): the SMS opens on it.
            is_email_request: The request is a customer's email: said in the head, and its reply waits in Gmail.

        Returns:
            A one-segment GSM-7 text.
        """
        note = cls.GMAIL_DRAFT_NOTE if is_email_request else ""
        if booked:
            urgent = "URGENT, " if request_type is AiAssistantRequestType.URGENT else ""
            booked_heads = [
                f"{urgent}RDV réservé le {booked} par {cls._clip(name, max_chars)}, "
                f"{cls._clip(contact, cls._CONTACT_MAX_CHARS)}"
                for max_chars in (cls._NAME_MAX_CHARS, cls._SHORT_NAME_MAX_CHARS)
            ]
            fitting = [head for head in booked_heads if segment_count(to_strict_gsm7(head) + ".") <= 1]
            return cls._fit(fitting[0] if fitting else booked_heads[-1], summary, link, note)
        photos = " (photo)" if has_photos else ""
        by_email = " par email" if is_email_request else ""
        heads = [
            f"{cls.LABELS[request_type]}{photos}{by_email} de {cls._clip(name, max_chars)}, "
            f"{cls._clip(contact, cls._CONTACT_MAX_CHARS)}"
            for max_chars in (cls._NAME_MAX_CHARS, cls._SHORT_NAME_MAX_CHARS)
        ]
        return cls._fit(cls._with_slots(heads, slots), summary, link, note)

    @classmethod
    def reminder(
        cls,
        *,
        request_type: AiAssistantRequestType,
        name: str,
        contact: str,
        summary: str | None,
        received_local: datetime,
        link: str | None = None,
        slots: tuple[str, ...] = (),
        is_email_request: bool = False,
    ) -> str:
        """
        The SMS reminding a request still waiting (« Rappel, en attente depuis le 23/09 : demande de devis… »).

        Args:
            request_type: Its type.
            name: The visitor's name.
            contact: Their phone or email.
            summary: What they need.
            received_local: When it came in, local time.
            link: The client space, without scheme; dropped when it cannot fit.
            slots: Wished half-days (« mar. 22/09 après-midi »), kept before the summary and never cut.
            is_email_request: The request is a customer's email: said in the head, and its reply waits in Gmail.

        Returns:
            A one-segment GSM-7 text.
        """
        by_email = " par email" if is_email_request else ""
        heads = [
            f"Rappel, en attente depuis le {received_local:%d/%m} : {cls.REMINDER_LABELS[request_type]}{by_email} de "
            f"{cls._clip(name, max_chars)}, {cls._clip(contact, cls._CONTACT_MAX_CHARS)}"
            for max_chars in (cls._NAME_MAX_CHARS, cls._SHORT_NAME_MAX_CHARS)
        ]
        return cls._fit(cls._with_slots(heads, slots), summary, link, cls.GMAIL_DRAFT_NOTE if is_email_request else "")

    @classmethod
    def _with_slots(cls, heads: list[str], slots: tuple[str, ...]) -> str:
        """
        The first head (full name, then a shorter one) that carries the wished half-days in one segment.

        Both half-days first, then only the first one; without them when even that overflows (the email has them).
        """
        for wished in (slots[:2], slots[:1]) if slots else ():
            for head in heads:
                candidate = f"{head}, pour {' ou '.join(wished)}"
                if segment_count(to_strict_gsm7(candidate) + ".") <= 1:
                    return candidate
        return heads[0]

    @classmethod
    def _clip(cls, text: str, max_chars: int) -> str:
        """A visitor-typed field, GSM-7 and bounded."""
        cleaned = to_strict_gsm7(text)
        return cleaned if len(cleaned) <= max_chars else cleaned[: max_chars - 3].rstrip() + "..."

    @classmethod
    def _fit(cls, head: str, summary: str | None, link: str | None = None, note: str = "") -> str:
        """
        ``head : summary.note Suivi : link`` in one segment, the summary cut word by word; the link is added
        only while the summary keeps ``_MIN_SUMMARY_WITH_LINK`` characters (or all of a shorter one).
        """
        base = to_strict_gsm7(head)
        while segment_count(base + ".") > 1:  # only with extension characters (€, [ ]…) in every field
            base = base[:-1]
        words = to_strict_gsm7(summary or "").split()
        if link:
            text, kept = cls._fill(base, words, f"{note} Suivi : {link}")
            if text is not None and kept >= min(cls._MIN_SUMMARY_WITH_LINK, len(" ".join(words))):
                return text
        text, _kept = cls._fill(base, words, note)
        if text is None and note:
            text, _kept = cls._fill(base, words, "")
        return text or base + "."

    @staticmethod
    def _fill(base: str, words: list[str], tail: str) -> tuple[str | None, int]:
        """
        ``base : summary.tail``, the summary cut word by word until the text is one segment.

        Returns:
            The text and how many summary characters it kept, or (None, 0) when even ``base.tail`` overflows.
        """
        remaining = list(words)
        cut = False
        while remaining:
            ending = "..." if cut else ("" if remaining[-1].endswith((".", "!", "?")) else ".")
            kept = " ".join(remaining)
            text = f"{base} : {kept}{ending}{tail}"
            if segment_count(text) <= 1:
                return text, len(kept)
            remaining.pop()
            cut = True
        text = f"{base}.{tail}"
        return (text, 0) if segment_count(text) <= 1 else (None, 0)
