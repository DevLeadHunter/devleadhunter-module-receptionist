"""
The texts a visitor receives about their appointment, in their language: the SMS, the email and its ``.ics`` file.

French, Dutch, English, German (Luxembourgish reads French). Each SMS fits one GSM-7 segment: the kind of
appointment, the address or the phone are dropped when they would not fit. The email tells the visitor to call the
business, never to answer (it would reach the operator); the ``.ics`` file holds the appointment in UTC.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import ClassVar

from models.ai_assistant import AiAssistant
from models.ai_assistant_appointment import AiAssistantAppointment
from services.ai_assistant.request_email import AiAssistantRequestEmail, RenderedEmail
from services.french_date_formatter import FrenchDateFormatter
from services.sms.gsm_segments import segment_count, to_strict_gsm7


def _utc_now() -> datetime:
    """Current time, naive UTC (the ``.ics`` stamp)."""
    return datetime.now(UTC).replace(tzinfo=None)


@dataclass(frozen=True)
class BusinessCard:
    """How the visitor reaches the business: its short name, phone and address (when known)."""

    name: str
    phone: str | None
    email: str | None
    address: str | None

    @classmethod
    def of(cls, assistant: AiAssistant) -> BusinessCard:
        """
        Read the business's card from its knowledge.

        Args:
            assistant: The assistant.

        Returns:
            The card; the name is cut before a « - » or « | » tagline and kept under 32 characters.
        """
        identity = (assistant.knowledge_json or {}).get("identity")
        identity = identity if isinstance(identity, dict) else {}
        name = re.split(r"\s+[-–—|]\s+", assistant.business_name.strip())[0][:32].strip()
        return cls(
            name=name or assistant.business_name[:32],
            phone=cls._text(identity.get("phone")),
            email=cls._text(identity.get("email")),
            address=cls._text(identity.get("address")),
        )

    @staticmethod
    def _text(value: object) -> str | None:
        """A trimmed string, or None."""
        return " ".join(value.split()) or None if isinstance(value, str) else None


class AppointmentTexts:
    """The visitor's confirmation and reminder, in their language."""

    LANGUAGES: ClassVar[tuple[str, ...]] = ("fr", "nl", "en", "de")
    _WEEKDAYS: ClassVar[dict[str, tuple[str, ...]]] = {
        "fr": FrenchDateFormatter.SHORT_WEEKDAYS,
        "nl": ("ma", "di", "wo", "do", "vr", "za", "zo"),
        "en": ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"),
        "de": ("Mo.", "Di.", "Mi.", "Do.", "Fr.", "Sa.", "So."),
    }
    _LONG_WEEKDAYS: ClassVar[dict[str, tuple[str, ...]]] = {
        "fr": FrenchDateFormatter.WEEKDAYS,
        "nl": ("maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"),
        "en": ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"),
        "de": ("Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"),
    }
    _MONTHS: ClassVar[dict[str, tuple[str, ...]]] = {
        "fr": FrenchDateFormatter.MONTHS,
        "nl": (
            "januari",
            "februari",
            "maart",
            "april",
            "mei",
            "juni",
            "juli",
            "augustus",
            "september",
            "oktober",
            "november",
            "december",
        ),
        "en": (
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ),
        "de": (
            "Januar",
            "Februar",
            "März",
            "April",
            "Mai",
            "Juni",
            "Juli",
            "August",
            "September",
            "Oktober",
            "November",
            "Dezember",
        ),
    }
    _AT: ClassVar[dict[str, str]] = {"fr": "à", "nl": "om", "en": "at", "de": "um"}
    _CONFIRMATION: ClassVar[dict[str, str]] = {
        "fr": "{business} : votre rendez-vous du {when}{kind} est confirmé.",
        "nl": "{business}: uw afspraak op {when}{kind} is bevestigd.",
        "en": "{business}: your appointment on {when}{kind} is confirmed.",
        "de": "{business}: Ihr Termin am {when}{kind} ist bestätigt.",
    }
    _REMINDER: ClassVar[dict[str, str]] = {
        "fr": "Rappel : rendez-vous demain, {when}, chez {business}.",
        "nl": "Herinnering: afspraak morgen, {when}, bij {business}.",
        "en": "Reminder: appointment tomorrow, {when}, at {business}.",
        "de": "Erinnerung: Termin morgen, {when}, bei {business}.",
    }
    _CALL: ClassVar[dict[str, str]] = {
        "fr": " Empêché ? Appelez le {phone}.",
        "nl": " Verhinderd? Bel {phone}.",
        "en": " Can't make it? Call {phone}.",
        "de": " Verhindert? Rufen Sie {phone} an.",
    }
    _ADDRESS: ClassVar[dict[str, str]] = {
        "fr": " Adresse : {address}.",
        "nl": " Adres: {address}.",
        "en": " Address: {address}.",
        "de": " Adresse: {address}.",
    }
    _EMAIL_SUBJECT: ClassVar[dict[str, str]] = {
        "fr": "Votre rendez-vous chez {business} : {when}",
        "nl": "Uw afspraak bij {business}: {when}",
        "en": "Your appointment at {business}: {when}",
        "de": "Ihr Termin bei {business}: {when}",
    }
    _EMAIL_INTRO: ClassVar[dict[str, str]] = {
        "fr": "Votre rendez-vous chez <strong>{business}</strong> est confirmé :",
        "nl": "Uw afspraak bij <strong>{business}</strong> is bevestigd:",
        "en": "Your appointment at <strong>{business}</strong> is confirmed:",
        "de": "Ihr Termin bei <strong>{business}</strong> ist bestätigt:",
    }
    _REMINDER_SUBJECT: ClassVar[dict[str, str]] = {
        "fr": "Rappel : ",
        "nl": "Herinnering: ",
        "en": "Reminder: ",
        "de": "Erinnerung: ",
    }
    _REMINDER_INTRO: ClassVar[dict[str, str]] = {
        "fr": "Rappel : votre rendez-vous chez <strong>{business}</strong>, c'est demain :",
        "nl": "Herinnering: uw afspraak bij <strong>{business}</strong> is morgen:",
        "en": "Reminder: your appointment at <strong>{business}</strong> is tomorrow:",
        "de": "Erinnerung: Ihr Termin bei <strong>{business}</strong> ist morgen:",
    }
    _EMAIL_LABELS: ClassVar[dict[str, tuple[str, str, str]]] = {
        "fr": ("Quand", "Pour", "Où"),
        "nl": ("Wanneer", "Voor", "Waar"),
        "en": ("When", "For", "Where"),
        "de": ("Wann", "Für", "Wo"),
    }
    _EMAIL_DURATION: ClassVar[dict[str, str]] = {
        "fr": "{minutes} min",
        "nl": "{minutes} min",
        "en": "{minutes} min",
        "de": "{minutes} Min.",
    }
    _EMAIL_CHANGE: ClassVar[dict[str, str]] = {
        "fr": "Pour le déplacer ou l'annuler, contactez directement {business}{reach}.",
        "nl": "Om te verplaatsen of te annuleren, neem rechtstreeks contact op met {business}{reach}.",
        "en": "To move or cancel it, please contact {business} directly{reach}.",
        "de": "Zum Verschieben oder Absagen wenden Sie sich bitte direkt an {business}{reach}.",
    }
    _EMAIL_REACH: ClassVar[dict[str, str]] = {"fr": " : {how}", "nl": ": {how}", "en": ": {how}", "de": ": {how}"}
    _EMAIL_FILE: ClassVar[dict[str, str]] = {
        "fr": "Le fichier joint l'ajoute à votre agenda. Cet email part automatiquement : n'y répondez pas.",
        "nl": "Met het bijgevoegde bestand zet u het in uw agenda. Deze e-mail is automatisch: niet beantwoorden.",
        "en": "The attached file adds it to your calendar. This email is automatic: please do not reply.",
        "de": "Mit der angehängten Datei tragen Sie ihn in Ihren Kalender ein. Diese E-Mail ist automatisch: bitte nicht antworten.",
    }
    _EVENT_TITLE: ClassVar[dict[str, str]] = {
        "fr": "Rendez-vous chez {business}",
        "nl": "Afspraak bij {business}",
        "en": "Appointment at {business}",
        "de": "Termin bei {business}",
    }

    @classmethod
    def language(cls, code: str | None) -> str:
        """The texts' language for a widget language (French by default, and for Luxembourgish)."""
        return code if code in cls.LANGUAGES else "fr"

    @classmethod
    def when(cls, start_local: datetime, language: str) -> str:
        """A short day and time (« mar. 29/09 à 14:30 », « Di. 29.09. um 14:30 »)."""
        weekday = cls._WEEKDAYS[language][start_local.weekday()]
        day = f"{start_local:%d.%m.}" if language == "de" else f"{start_local:%d/%m}"
        return f"{weekday} {day} {cls._AT[language]} {start_local:%H:%M}"

    @classmethod
    def when_long(cls, start_local: datetime, language: str) -> str:
        """A spelled-out day and time (« mardi 29 septembre à 14:30 »)."""
        weekday = cls._LONG_WEEKDAYS[language][start_local.weekday()]
        month = cls._MONTHS[language][start_local.month - 1]
        if language == "en":
            return f"{weekday} {start_local.day} {month} {cls._AT[language]} {start_local:%H:%M}"
        if language == "de":
            return f"{weekday}, {start_local.day}. {month} {cls._AT[language]} {start_local:%H:%M}"
        return f"{weekday} {start_local.day} {month} {cls._AT[language]} {start_local:%H:%M}"

    @classmethod
    def confirmation_sms(
        cls, *, card: BusinessCard, start_local: datetime, type_label: str | None, language: str
    ) -> str:
        """
        The confirmation SMS, one GSM-7 segment.

        Args:
            card: The business.
            start_local: The appointment's start, business time.
            type_label: The kind of appointment, when one was chosen.
            language: The texts' language.

        Returns:
            The text in GSM-7; the kind, then the phone are dropped when they would not fit.
        """
        when = cls.when(start_local, language)
        call = cls._CALL[language].format(phone=card.phone) if card.phone else ""
        for kind, tail in ((f" ({type_label})" if type_label else "", call), ("", call), ("", "")):
            text = to_strict_gsm7(cls._CONFIRMATION[language].format(business=card.name, when=when, kind=kind) + tail)
            if segment_count(text) == 1:
                return text
        return text

    @classmethod
    def reminder_sms(cls, *, card: BusinessCard, start_local: datetime, language: str) -> str:
        """
        The J-1 reminder SMS, one GSM-7 segment.

        Args:
            card: The business.
            start_local: The appointment's start, business time.
            language: The texts' language.

        Returns:
            The text in GSM-7; the address, then the phone are dropped when they would not fit.
        """
        base = cls._REMINDER[language].format(when=f"{start_local:%H:%M}", business=card.name)
        address = cls._ADDRESS[language].format(address=card.address) if card.address else ""
        call = cls._CALL[language].format(phone=card.phone) if card.phone else ""
        for text in (to_strict_gsm7(base + address + call), to_strict_gsm7(base + call)):
            if segment_count(text) == 1:
                return text
        return to_strict_gsm7(base)

    @classmethod
    def email(
        cls,
        *,
        card: BusinessCard,
        start_local: datetime,
        duration_minutes: int,
        type_label: str | None,
        language: str,
        is_reminder: bool = False,
    ) -> RenderedEmail:
        """
        The confirmation email, or the J-1 reminder of a visitor who left no mobile.

        Args:
            card: The business.
            start_local: The appointment's start, business time.
            duration_minutes: How long it lasts.
            type_label: The kind of appointment, when one was chosen.
            language: The texts' language.
            is_reminder: Word it as the reminder of the day before.

        Returns:
            Subject and HTML body; every stored text is HTML-escaped.
        """
        business = html.escape(card.name)
        when_label, for_label, where_label = cls._EMAIL_LABELS[language]
        duration = cls._EMAIL_DURATION[language].format(minutes=duration_minutes)
        rows = [(when_label, f"{cls.when_long(start_local, language)} ({duration})")]
        if type_label:
            rows.append((for_label, type_label))
        if card.address:
            rows.append((where_label, card.address))
        details = "".join(
            f'<tr><td style="padding:4px 12px 4px 0;color:#6b6358;vertical-align:top">{html.escape(label)}</td>'
            f'<td style="padding:4px 0;font-weight:600">{html.escape(value)}</td></tr>'
            for label, value in rows
        )
        reach_bits = [html.escape(bit) for bit in (card.phone, card.email) if bit]
        reach = cls._EMAIL_REACH[language].format(how=" · ".join(reach_bits)) if reach_bits else ""
        body = "".join(
            [
                AiAssistantRequestEmail.paragraph(
                    (cls._REMINDER_INTRO if is_reminder else cls._EMAIL_INTRO)[language].format(business=business)
                ),
                f'<table role="presentation" style="margin:0 0 16px;border-collapse:collapse">{details}</table>',
                AiAssistantRequestEmail.paragraph(cls._EMAIL_CHANGE[language].format(business=business, reach=reach)),
                AiAssistantRequestEmail.paragraph(html.escape(cls._EMAIL_FILE[language]), muted=True),
            ]
        )
        subject = cls._EMAIL_SUBJECT[language].format(business=card.name, when=cls.when_long(start_local, language))
        return RenderedEmail(
            subject=f"{cls._REMINDER_SUBJECT[language]}{subject}" if is_reminder else subject,
            html=AiAssistantRequestEmail.document(body),
        )

    @classmethod
    def ics(cls, *, card: BusinessCard, appointment: AiAssistantAppointment, language: str) -> bytes:
        """
        The appointment as an iCalendar file (RFC 5545), times in UTC.

        Args:
            card: The business.
            appointment: The booked appointment.
            language: The texts' language (title).

        Returns:
            The file's bytes (UTF-8, CRLF lines, long lines folded).
        """
        stamp = f"{_utc_now():%Y%m%dT%H%M%SZ}"
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Dibodev//Receptionniste//FR",
            "METHOD:PUBLISH",
            "BEGIN:VEVENT",
            f"UID:{appointment.google_event_id or appointment.id}@receptionniste.dibodev.fr",
            f"DTSTAMP:{stamp}",
            f"DTSTART:{appointment.starts_at:%Y%m%dT%H%M%SZ}",
            f"DTEND:{appointment.ends_at:%Y%m%dT%H%M%SZ}",
            f"SUMMARY:{cls._ics_text(cls._EVENT_TITLE[language].format(business=card.name))}",
        ]
        if card.address:
            lines.append(f"LOCATION:{cls._ics_text(card.address)}")
        if appointment.type_label:
            lines.append(f"DESCRIPTION:{cls._ics_text(appointment.type_label)}")
        lines.extend(["END:VEVENT", "END:VCALENDAR"])
        return ("\r\n".join(cls._fold(line) for line in lines) + "\r\n").encode("utf-8")

    @staticmethod
    def _ics_text(value: str) -> str:
        """Escape a text value for iCalendar."""
        return value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")

    @staticmethod
    def _fold(line: str) -> str:
        """Fold a content line at 75 octets (continuation lines start with a space)."""
        encoded = line.encode("utf-8")
        if len(encoded) <= 75:
            return line
        parts: list[str] = []
        current = ""
        for character in line:
            limit = 75 if not parts else 74
            if len((current + character).encode("utf-8")) > limit:
                parts.append(current)
                current = character
            else:
                current += character
        parts.append(current)
        return "\r\n ".join(parts)
