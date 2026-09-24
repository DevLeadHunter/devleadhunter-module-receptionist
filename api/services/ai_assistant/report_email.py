"""
The monthly report email of a sold assistant, in the client's accent colour.

Two versions: the month's figures (conversations, requests by type, languages, share received outside
opening hours, handling delay, the questions visitors ask the most), or — for a month without a single
conversation or request — the two checks that bring visitors back to the assistant (the widget on the
site, the site on the Google business profile). Table layout and inline styles, so it reads the same
in Gmail, Apple Mail and on a phone; every stored or visitor-provided text is HTML-escaped.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import date
from typing import Any, ClassVar

from enums.ai_assistant_persona_gender import AiAssistantPersonaGender
from services.ai_assistant.knowledge_builder import LANGUAGE_NAMES
from services.ai_assistant.request_email import AiAssistantRequestEmail, RenderedEmail
from services.french_date_formatter import FrenchDateFormatter


@dataclass(frozen=True)
class LanguageShare:
    """One language's share of the month's conversations."""

    code: str
    share_pct: int


@dataclass(frozen=True)
class MonthlyStats:
    """The figures of one monthly report (tests excluded), stored with it as ``stats_json``."""

    # Conversations in which a visitor wrote during the month (a returning visitor's included).
    conversations: int
    requests: int
    quotes: int
    appointments: int
    urgent: int
    photo_requests: int
    handled: int
    # Share of the requests received outside the opening hours, among those whose hours are known.
    outside_hours_pct: int | None
    languages: tuple[LanguageShare, ...]
    # Mean delay between a request and its « traitée » mark, over the requests marked so far.
    average_handling_hours: float | None
    top_questions: tuple[str, ...]

    @property
    def is_empty(self) -> bool:
        """No conversation and no request: nobody reached the assistant all month."""
        return self.conversations == 0 and self.requests == 0

    @classmethod
    def from_json(cls, stats_json: dict[str, Any]) -> MonthlyStats:
        """
        Read back the figures stored on a report row.

        Args:
            stats_json: The row's ``stats_json``.

        Returns:
            The figures.
        """
        outside_hours = stats_json.get("outside_hours_pct")
        handling = stats_json.get("average_handling_hours")
        return cls(
            conversations=int(stats_json.get("conversations") or 0),
            requests=int(stats_json.get("requests") or 0),
            quotes=int(stats_json.get("quotes") or 0),
            appointments=int(stats_json.get("appointments") or 0),
            urgent=int(stats_json.get("urgent") or 0),
            photo_requests=int(stats_json.get("photo_requests") or 0),
            handled=int(stats_json.get("handled") or 0),
            outside_hours_pct=int(outside_hours) if outside_hours is not None else None,
            languages=tuple(
                LanguageShare(code=str(share["code"]), share_pct=int(share["share_pct"]))
                for share in stats_json.get("languages") or []
            ),
            average_handling_hours=float(handling) if handling is not None else None,
            top_questions=tuple(str(question) for question in stats_json.get("top_questions") or []),
        )


@dataclass(frozen=True)
class ReportEmailContent:
    """What the monthly report email shows."""

    business_name: str
    assistant_name: str
    persona_gender: AiAssistantPersonaGender
    month_first_day: date
    stats: MonthlyStats
    accent_color: str | None
    # The client's site where the widget is installed (``custom_domain``), when known.
    website: str | None = None
    # The day the service started, when it was during the reported month.
    service_start: date | None = None
    # The client space (every request, the settings).
    client_space_url: str | None = None


class AiAssistantReportEmail:
    """Renders the monthly report email."""

    DEFAULT_ACCENT: ClassVar[str] = "#111111"
    # Languages listed by name; the rest of the conversations are grouped under « autres ».
    MAX_LANGUAGES_LISTED: ClassVar[int] = 3
    _HEX_COLOR: ClassVar[re.Pattern[str]] = re.compile(r"^#(?:[0-9a-fA-F]{3}){1,2}$")
    _HOST: ClassVar[re.Pattern[str]] = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9-]+)*\.[a-z]{2,}$")
    _RECEPTIONIST: ClassVar[dict[AiAssistantPersonaGender, str]] = {
        AiAssistantPersonaGender.FEMININE: "votre réceptionniste virtuelle",
        AiAssistantPersonaGender.MASCULINE: "votre réceptionniste virtuel",
    }

    @classmethod
    def render(cls, content: ReportEmailContent) -> RenderedEmail:
        """
        Render the report of a month: its figures, or the visibility checks when nobody came.

        Args:
            content: What to show.

        Returns:
            Subject and HTML body.
        """
        accent = cls.accent(content.accent_color)
        if content.stats.is_empty:
            title = f"{content.assistant_name} n'a reçu aucune visite"
            body = cls._empty_body(content)
        else:
            title = f"{content.assistant_name} en {cls._month_name(content.month_first_day)}"
            body = cls._figures_body(content, accent)
        return RenderedEmail(subject=cls.subject(content), html=cls._frame(content, accent, title, body))

    @classmethod
    def subject(cls, content: ReportEmailContent) -> str:
        """
        The subject line: the month's headline figures (« Sofia en septembre : 43 demandes, 6 rendez-vous… »).

        Args:
            content: What the email shows.

        Returns:
            The subject, plain text.
        """
        stats = content.stats
        month = cls._month_name(content.month_first_day)
        if stats.is_empty:
            return f"{content.assistant_name} n'a reçu aucune visite en {month}"
        if stats.requests == 0:
            return f"{content.assistant_name} en {month} : {cls._count(stats.conversations, 'conversation')}"
        parts = [cls._count(stats.requests, "demande")]
        if stats.appointments:
            parts.append(f"{stats.appointments} rendez-vous")
        if stats.quotes:
            parts.append(f"{stats.quotes} devis")
        if stats.outside_hours_pct:
            parts.append(f"{stats.outside_hours_pct} % en dehors de vos horaires")
        return f"{content.assistant_name} en {month} : {', '.join(parts)}"

    @classmethod
    def accent(cls, color: str | None) -> str:
        """The client's accent when it is a plain hex colour (it lands in inline CSS), else black."""
        value = (color or "").strip()
        return value if cls._HEX_COLOR.match(value) else cls.DEFAULT_ACCENT

    @staticmethod
    def ink_on(color: str) -> str:
        """
        Black or white, whichever reads best on a hex colour.

        Args:
            color: A ``#rgb`` or ``#rrggbb`` colour.

        Returns:
            ``#111111`` on a light colour, ``#ffffff`` on a dark one.
        """
        digits = color.lstrip("#")
        if len(digits) == 3:
            digits = "".join(digit * 2 for digit in digits)
        red, green, blue = (int(digits[index : index + 2], 16) for index in (0, 2, 4))
        return "#111111" if (0.299 * red + 0.587 * green + 0.114 * blue) / 255 > 0.6 else "#ffffff"

    @classmethod
    def language_line(cls, languages: tuple[LanguageShare, ...]) -> str | None:
        """
        The conversations' languages in words (« français 72 %, anglais 20 %, autres 8 % »), a no-break
        space before each « % » so a figure never leaves its sign on the next line.

        Args:
            languages: Shares, largest first.

        Returns:
            The line, or None when no language is known.
        """
        if not languages:
            return None
        listed = languages[: cls.MAX_LANGUAGES_LISTED]
        parts = [f"{LANGUAGE_NAMES.get(share.code, share.code.upper())} {share.share_pct}\u00a0%" for share in listed]
        others = sum(share.share_pct for share in languages[cls.MAX_LANGUAGES_LISTED :])
        if others:
            parts.append(f"autres {others}\u00a0%")
        return ", ".join(parts)

    @classmethod
    def handling_line(cls, stats: MonthlyStats) -> str | None:
        """
        The handling sentence (« 31 demandes marquées traitées, en 5 h en moyenne. »).

        Args:
            stats: The month's figures.

        Returns:
            The sentence, or None when no request was marked handled.
        """
        if not stats.handled or stats.average_handling_hours is None:
            return None
        handled = "demande marquée traitée" if stats.handled == 1 else "demandes marquées traitées"
        return f"{stats.handled} {handled}, en {cls.delay_label(stats.average_handling_hours)} en moyenne."

    @staticmethod
    def delay_label(hours: float) -> str:
        """A handling delay in words (« moins d'une heure », « 5 h », « 3 jours »), unbreakable."""
        if hours < 1:
            return "moins d'une heure"
        if hours < 48:
            return f"{round(hours)}\u00a0h"
        return f"{round(hours / 24)}\u00a0jours"

    @classmethod
    def website_host(cls, website: str | None) -> str | None:
        """
        The client's site as a bare host (« agence-luma.lu »), when it reads as one.

        Args:
            website: The stored site, with or without scheme, ``www.`` or path.

        Returns:
            The lowercase host, or None when there is none or it does not look like a domain.
        """
        value = (website or "").strip().lower()
        value = re.sub(r"^https?://", "", value).split("/")[0].removeprefix("www.")
        return value if cls._HOST.match(value) else None

    @classmethod
    def _figures_body(cls, content: ReportEmailContent, accent: str) -> str:
        """The month's figures, then the languages, the handling and the most asked questions."""
        stats = content.stats
        receptionist = cls._RECEPTIONIST[content.persona_gender]
        intro = (
            f"Voici ce que <strong>{html.escape(content.assistant_name)}</strong>, {receptionist}, a fait pour "
            f"<strong>{html.escape(content.business_name)}</strong> en "
            f"{FrenchDateFormatter.month_year(content.month_first_day)}{cls._since(content)}."
        )
        cells = [
            (str(stats.conversations), cls._noun(stats.conversations, "conversation")),
            (str(stats.requests), cls._noun(stats.requests, "demande")),
            (str(stats.appointments), "rendez-vous"),
            (str(stats.quotes), "devis"),
        ]
        if stats.photo_requests:
            cells.append((str(stats.photo_requests), "avec photo"))
        if stats.urgent:
            cells.append((str(stats.urgent), cls._noun(stats.urgent, "urgence")))
        if stats.outside_hours_pct is not None:
            cells.append((f"{stats.outside_hours_pct} %", "hors horaires"))
        sections = [AiAssistantRequestEmail.paragraph(intro), cls._figures_table(cells, accent)]
        languages = cls.language_line(stats.languages)
        if languages:
            sections.append(AiAssistantRequestEmail.paragraph(f"Langues des conversations : {html.escape(languages)}."))
        handling = cls.handling_line(stats)
        if handling:
            sections.append(AiAssistantRequestEmail.paragraph(handling))
        if stats.top_questions:
            questions_html = "".join(
                f'<li style="margin:0 0 6px">{html.escape(question)}</li>' for question in stats.top_questions
            )
            sections.append(cls._heading("Ce que vos visiteurs demandent le plus"))
            sections.append(f'<ol style="margin:0 0 12px;padding-left:22px">{questions_html}</ol>')
            sections.append(
                AiAssistantRequestEmail.paragraph(
                    "Autant de réponses à mettre en avant sur votre site : vos clients les trouveront sans avoir à "
                    "demander.",
                    muted=True,
                )
            )
        if content.client_space_url:
            sections.append(AiAssistantRequestEmail.client_space_note(content.client_space_url))
        sections.append(
            AiAssistantRequestEmail.paragraph("Vous recevez ce rapport au début de chaque mois.", muted=True)
        )
        return "".join(sections)

    @classmethod
    def _empty_body(cls, content: ReportEmailContent) -> str:
        """The month nobody came: the two checks that bring visitors back to the assistant."""
        name = html.escape(content.assistant_name)
        host = cls.website_host(content.website)
        site = (
            f'<a href="https://{html.escape(host, quote=True)}" style="color:#111">{html.escape(host)}</a>'
            if host
            else "votre site"
        )
        steps = (
            f"<strong>Le widget est-il bien installé ?</strong> Ouvrez {site} : la bulle de {name} doit apparaître "
            "en bas à droite de chaque page. Sinon, répondez à cet email pour recevoir le code d'installation.",
            "<strong>Votre fiche Google mène-t-elle à votre site ?</strong> Dans votre fiche d'établissement "
            f"Google, ajoutez ou vérifiez le lien « Site Web » vers {site} : c'est là que {name} répond à vos "
            "clients, à toute heure.",
        )
        steps_html = "".join(f'<li style="margin:0 0 10px">{step}</li>' for step in steps)
        return "".join(
            [
                AiAssistantRequestEmail.paragraph(
                    f"En {FrenchDateFormatter.month_year(content.month_first_day)}{cls._since(content)}, aucun "
                    f"visiteur n'a écrit à <strong>{name}</strong> pour "
                    f"<strong>{html.escape(content.business_name)}</strong>."
                ),
                AiAssistantRequestEmail.paragraph(
                    f"C'est presque toujours que {name} n'est pas encore assez visible. Deux vérifications suffisent :"
                ),
                f'<ol style="margin:0 0 12px;padding-left:22px">{steps_html}</ol>',
                AiAssistantRequestEmail.paragraph("Répondez simplement à cet email pour qu'on s'en occupe ensemble."),
                AiAssistantRequestEmail.client_space_note(content.client_space_url) if content.client_space_url else "",
            ]
        )

    @classmethod
    def _frame(cls, content: ReportEmailContent, accent: str, title: str, body: str) -> str:
        """The accent header band (month, title) above the white body."""
        ink = cls.ink_on(accent)
        month = html.escape(FrenchDateFormatter.month_year(content.month_first_day))
        return (
            "<div style=\"font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;"
            'color:#111;max-width:560px;margin:0 auto;padding:24px 12px;line-height:1.5;font-size:15px">'
            f'<div style="background:{accent};color:{ink};padding:18px 20px;border-radius:12px 12px 0 0">'
            f'<p style="margin:0;font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:{ink}">'
            f"Rapport mensuel · {month}</p>"
            f'<h1 style="margin:6px 0 0;font-size:22px;line-height:1.25;color:{ink}">{html.escape(title)}</h1></div>'
            '<div style="border:1px solid #e5e5e5;border-top:0;border-radius:0 0 12px 12px;padding:20px">'
            f"{body}</div></div>"
        )

    @staticmethod
    def _figures_table(cells: list[tuple[str, str]], accent: str) -> str:
        """The figures, three per row, each over its label."""
        rows: list[str] = []
        for start in range(0, len(cells), 3):
            row = cells[start : start + 3]
            tds = "".join(
                '<td width="33%" style="padding:4px;vertical-align:top">'
                f'<div style="border:1px solid #e5e5e5;border-top:3px solid {accent};border-radius:10px;'
                'padding:10px 6px;text-align:center">'
                f'<div style="font-size:26px;font-weight:700;line-height:1.1;color:#111">{html.escape(value)}</div>'
                f'<div style="font-size:12px;color:#666;margin-top:2px">{html.escape(label)}</div></div></td>'
                for value, label in row
            )
            tds += '<td width="33%" style="padding:4px"></td>' * (3 - len(row))
            rows.append(f"<tr>{tds}</tr>")
        return (
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'style="border-collapse:collapse;margin:4px 0 12px">{"".join(rows)}</table>'
        )

    @staticmethod
    def _month_name(first_day: date) -> str:
        """The month's name alone (« septembre »)."""
        return FrenchDateFormatter.MONTHS[first_day.month - 1]

    @classmethod
    def _since(cls, content: ReportEmailContent) -> str:
        """« (depuis sa mise en service le 12 septembre) » when the service started during the month."""
        if content.service_start is None:
            return ""
        day = "1er" if content.service_start.day == 1 else str(content.service_start.day)
        return f" (depuis sa mise en service le {day} {cls._month_name(content.service_start)})"

    @staticmethod
    def _count(value: int, noun: str) -> str:
        """« 1 demande », « 43 demandes »."""
        return f"{value} {noun}" if value == 1 else f"{value} {noun}s"

    @staticmethod
    def _noun(value: int, noun: str) -> str:
        """A noun agreeing with a figure shown apart (« demande » under 1, « demandes » under 43)."""
        return noun if value <= 1 else f"{noun}s"

    @staticmethod
    def _heading(text: str) -> str:
        return f'<h2 style="font-size:16px;margin:20px 0 8px;font-weight:700">{html.escape(text)}</h2>'
