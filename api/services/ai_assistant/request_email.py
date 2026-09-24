"""
The summary email a business receives for each request its assistant captured.

One glance must be enough: what the visitor wants, how to reach them (tap-to-call / tap-to-mail),
whether it came in outside opening hours, the conversation for context, and a one-click
« marquer traitée ». Plain black-on-white HTML with inline styles, readable in any mail client.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

from enums.ai_assistant_request import AiAssistantRequestType
from services.ai_assistant.request_analyzer import TranscriptLine


@dataclass(frozen=True)
class RequestEmailContent:
    """What the summary email shows about one request."""

    business_name: str
    assistant_name: str
    request_type: AiAssistantRequestType
    visitor_name: str
    contact: str
    need: str | None
    need_summary: str | None
    received_at: datetime
    received_outside_hours: bool | None
    transcript: list[TranscriptLine]
    handled_url: str
    photo_urls: tuple[str, ...] = ()
    # The J+1 reminder of a request still waiting, instead of its first announcement.
    is_reminder: bool = False


@dataclass(frozen=True)
class RenderedEmail:
    """A ready-to-send subject and HTML body."""

    subject: str
    html: str


class AiAssistantRequestEmail:
    """Renders the request summary email."""

    TYPE_LABELS: ClassVar[dict[AiAssistantRequestType, str]] = {
        AiAssistantRequestType.QUESTION: "Question",
        AiAssistantRequestType.QUOTE: "Demande de devis",
        AiAssistantRequestType.APPOINTMENT: "Demande de rendez-vous",
        AiAssistantRequestType.URGENT: "Urgence",
        AiAssistantRequestType.OTHER: "Nouvelle demande",
    }
    _EMAIL_PATTERN: ClassVar[re.Pattern[str]] = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    _PHONE_PATTERN: ClassVar[re.Pattern[str]] = re.compile(r"^\+?[\d\s.()-]{6,}$")

    @classmethod
    def type_label(cls, request_type: AiAssistantRequestType) -> str:
        """French label of a request type (e.g. « Demande de devis »)."""
        return cls.TYPE_LABELS[request_type]

    @classmethod
    def render(cls, content: RequestEmailContent) -> RenderedEmail:
        """
        Render the summary email of a request.

        Args:
            content: What to show.

        Returns:
            Subject and HTML body; every visitor-provided text is HTML-escaped.
        """
        label = cls.type_label(content.request_type)
        subject = f"{label} — {content.visitor_name}"
        if content.received_outside_hours:
            subject += " (hors horaires)"
        if content.is_reminder:
            subject = f"Rappel : {subject}"

        received = content.received_at.strftime("%d/%m/%Y à %H:%M")
        timing = f"Reçue le {received}" + (", en dehors de vos horaires" if content.received_outside_hours else "")
        summary = (content.need_summary or content.need or "").strip()
        own_words = (content.need or "").strip()

        intro = (
            f"Cette demande pour <strong>{html.escape(content.business_name)}</strong> attend toujours une réponse."
            if content.is_reminder
            else f"<strong>{html.escape(content.assistant_name)}</strong>, votre réceptionniste virtuelle, a noté une "
            f"demande pour <strong>{html.escape(content.business_name)}</strong>."
        )
        sections: list[str] = [
            cls._paragraph(intro),
            cls._heading(label),
            cls._paragraph(html.escape(timing), muted=True),
        ]
        if summary:
            sections.append(cls._block("Ce qu'il faut savoir", html.escape(summary)))
        sections.append(cls._block("Coordonnées", cls._contact_html(content.visitor_name, content.contact)))
        if own_words and own_words != summary:
            sections.append(cls._block("Ses mots", html.escape(own_words)))
        if content.photo_urls:
            links = "<br/>".join(
                f'<a href="{html.escape(url, quote=True)}" style="color:#111">Photo {index}</a>'
                for index, url in enumerate(content.photo_urls, start=1)
            )
            sections.append(cls._block("Photos envoyées", links))
        if content.transcript:
            sections.append(cls._block("La conversation", cls._transcript_html(content)))
        sections.append(cls._button("Marquer comme traitée", content.handled_url))
        sections.append(
            cls._paragraph(
                "Répondez-lui directement avec les coordonnées ci-dessus. Ce lien marque la demande comme "
                "traitée pour qu'elle ne vous soit plus rappelée.",
                muted=True,
            )
        )
        body = "".join(sections)
        return RenderedEmail(
            subject=subject,
            html=(
                "<div style=\"font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;"
                'color:#111;max-width:560px;margin:0 auto;padding:24px 16px;line-height:1.5;font-size:15px">'
                f"{body}</div>"
            ),
        )

    @staticmethod
    def confirmation_page(title: str, message: str, *, action_label: str | None = None) -> str:
        """
        The small page behind the « marquer traitée » link.

        Opening the link only shows the page; the change happens when the owner presses the button
        (a POST to the same address), so mail scanners that open every link change nothing.

        Args:
            title: Headline (plain text).
            message: One sentence (plain text).
            action_label: Label of the button that confirms the action; no button when None.

        Returns:
            A standalone HTML document; every text is escaped.
        """
        action = (
            '<form method="post" style="margin:24px 0 0">'
            '<button type="submit" style="background:#111;color:#fff;border:0;border-radius:8px;padding:12px 18px;'
            f'font-size:15px;font-weight:600;cursor:pointer">{html.escape(action_label)}</button></form>'
            if action_label
            else ""
        )
        return (
            '<!doctype html><html lang="fr"><head><meta charset="utf-8"/>'
            '<meta name="viewport" content="width=device-width,initial-scale=1"/>'
            '<meta name="robots" content="noindex"/>'
            f"<title>{html.escape(title)}</title></head>"
            "<body style=\"margin:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;"
            'background:#fafaf7;color:#111">'
            '<main style="max-width:420px;margin:15vh auto;padding:0 20px;text-align:center">'
            f'<h1 style="font-size:22px;margin:0 0 10px">{html.escape(title)}</h1>'
            f'<p style="margin:0;color:#555;line-height:1.5">{html.escape(message)}</p>'
            f"{action}</main></body></html>"
        )

    @classmethod
    def _contact_html(cls, visitor_name: str, contact: str) -> str:
        """Name plus a tap-to-mail or tap-to-call link when the contact reads as one."""
        name = html.escape(visitor_name)
        cleaned = contact.strip()
        escaped = html.escape(cleaned)
        if cls._EMAIL_PATTERN.match(cleaned):
            return f'{name}<br/><a href="mailto:{html.escape(cleaned, quote=True)}" style="color:#111">{escaped}</a>'
        if cls._PHONE_PATTERN.match(cleaned):
            dial = re.sub(r"[^\d+]", "", cleaned)
            return f'{name}<br/><a href="tel:{dial}" style="color:#111">{escaped}</a>'
        return f"{name}<br/>{escaped}"

    @staticmethod
    def _transcript_html(content: RequestEmailContent) -> str:
        """The conversation, one line per turn, speakers in bold."""
        lines = []
        for line in content.transcript:
            speaker = html.escape(content.visitor_name) if line.role == "user" else html.escape(content.assistant_name)
            text = html.escape(line.content).replace("\n", "<br/>")
            lines.append(f'<p style="margin:0 0 8px"><strong>{speaker}</strong> : {text}</p>')
        return "".join(lines)

    @staticmethod
    def _heading(text: str) -> str:
        return f'<h1 style="font-size:20px;margin:24px 0 4px;font-weight:700">{html.escape(text)}</h1>'

    @staticmethod
    def _paragraph(inner_html: str, *, muted: bool = False) -> str:
        color = "#666" if muted else "#111"
        size = "13px" if muted else "15px"
        return f'<p style="margin:0 0 12px;color:{color};font-size:{size}">{inner_html}</p>'

    @staticmethod
    def _block(title: str, inner_html: str) -> str:
        return (
            '<div style="border:1px solid #e5e5e5;border-radius:10px;padding:12px 14px;margin:12px 0">'
            f'<p style="margin:0 0 6px;font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:#666">'
            f"{html.escape(title)}</p><div>{inner_html}</div></div>"
        )

    @staticmethod
    def _button(label: str, url: str) -> str:
        return (
            f'<p style="margin:20px 0"><a href="{html.escape(url, quote=True)}" '
            'style="display:inline-block;background:#111;color:#fff;text-decoration:none;padding:12px 18px;'
            f'border-radius:8px;font-weight:600">{html.escape(label)}</a></p>'
        )
