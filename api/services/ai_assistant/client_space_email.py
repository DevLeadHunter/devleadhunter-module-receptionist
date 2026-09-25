"""
The emails of the client space: the welcome at the sale, its link (from the dashboard or an expired link), and the
notices of a changed alert mobile or a connected agenda.
"""

from __future__ import annotations

import html
from datetime import date

from services.ai_assistant.request_email import AiAssistantRequestEmail, RenderedEmail


class AiAssistantClientSpaceEmail:
    """Renders the client-space emails: the welcome, the link, the notices."""

    @staticmethod
    def render_welcome(
        *, business_name: str, assistant_name: str, url: str, expires_on: date, embed_snippet: str
    ) -> RenderedEmail:
        """
        Render the email a business receives right after subscribing: the line to paste, the space, what comes next.

        Args:
            business_name: The business.
            assistant_name: Its assistant's first name.
            url: The signed client-space link.
            expires_on: The last day the link opens the space.
            embed_snippet: The script tag to paste on the website.

        Returns:
            Subject and HTML body; every stored text is HTML-escaped.
        """
        name = html.escape(assistant_name)
        steps_html = "".join(
            f'<li style="margin:0 0 8px">{step}</li>'
            for step in (
                "<strong>Collez cette ligne</strong> sur votre site, juste avant la balise &lt;/body&gt; (ou "
                "transmettez-la à la personne qui s'occupe de votre site, ou répondez à cet email : on l'installe "
                "avec vous) :",
            )
        )
        code_html = (
            '<pre style="margin:0 0 16px;padding:12px 14px;border-radius:8px;background:#f4f0e8;font-size:13px;'
            f'white-space:pre-wrap;word-break:break-all">{html.escape(embed_snippet)}</pre>'
        )
        after_html = "".join(
            f'<li style="margin:0 0 6px">{item}</li>'
            for item in (
                "un SMS et un email à chaque demande, avec la conversation et la photo ;",
                "les rendez-vous dans votre agenda Google, si vous le connectez depuis l'espace ;",
                f"un rapport chaque début de mois : ce que {name} a traité pour vous.",
            )
        )
        body = "".join(
            [
                AiAssistantRequestEmail.paragraph(
                    f"Merci : <strong>{name}</strong> travaille désormais pour <strong>{html.escape(business_name)}</strong>. "
                    "Deux choses pour démarrer."
                ),
                f'<ol style="margin:0 0 6px;padding-left:22px">{steps_html}</ol>',
                code_html,
                AiAssistantRequestEmail.paragraph(
                    f"<strong>Ouvrez votre espace</strong> : les demandes que {name} reçoit, ses réponses à compléter, "
                    "vos alertes, votre abonnement."
                ),
                AiAssistantRequestEmail.button("Ouvrir mon espace", url),
                AiAssistantRequestEmail.paragraph("Ensuite, tout arrive chez vous :"),
                f'<ul style="margin:0 0 12px;padding-left:22px">{after_html}</ul>',
                AiAssistantRequestEmail.paragraph(
                    f"Ce lien personnel est valable jusqu'au {expires_on:%d/%m/%Y} ; chaque alerte vous en apporte un "
                    "nouveau. Ne le transférez pas : il donne accès à vos demandes. Une question ? Répondez à cet "
                    "email.",
                    muted=True,
                ),
            ]
        )
        return RenderedEmail(
            subject=f"Bienvenue : {assistant_name} travaille pour vous",
            html=AiAssistantRequestEmail.document(body),
        )

    @staticmethod
    def render(*, business_name: str, assistant_name: str, url: str, expires_on: date) -> RenderedEmail:
        """
        Render the email carrying a fresh client-space link.

        Args:
            business_name: The business.
            assistant_name: Its assistant's first name.
            url: The signed client-space link.
            expires_on: The last day the link opens the space.

        Returns:
            Subject and HTML body; every stored text is HTML-escaped.
        """
        name = html.escape(assistant_name)
        features_html = "".join(
            f'<li style="margin:0 0 6px">{feature}</li>'
            for feature in (
                f"les demandes reçues par {name}, à marquer traitées d'un clic ;",
                "le rapport du mois ;",
                "vos alertes : le mobile qui reçoit les SMS, les emails ;",
                "votre abonnement : factures, carte bancaire, résiliation.",
            )
        )
        body = "".join(
            [
                AiAssistantRequestEmail.paragraph(
                    f"Voici votre espace pour suivre le travail de <strong>{name}</strong> pour "
                    f"<strong>{html.escape(business_name)}</strong> :"
                ),
                f'<ul style="margin:0 0 12px;padding-left:22px">{features_html}</ul>',
                AiAssistantRequestEmail.button("Ouvrir mon espace", url),
                AiAssistantRequestEmail.paragraph(
                    f"Ce lien personnel est valable jusqu'au {expires_on:%d/%m/%Y}. Ne le transférez pas : il "
                    "donne accès à vos demandes. Chaque alerte vous en apporte un nouveau.",
                    muted=True,
                ),
            ]
        )
        return RenderedEmail(
            subject=f"Votre espace : les demandes reçues par {assistant_name}",
            html=AiAssistantRequestEmail.document(body),
        )

    @staticmethod
    def render_calendar_connected(
        *, assistant_name: str, business_name: str, account_email: str | None
    ) -> RenderedEmail:
        """
        Render the notice sent to the business address when a Google agenda is connected from the client space.

        Args:
            assistant_name: The assistant's first name.
            business_name: The business.
            account_email: The connected Google account, when Google told it.

        Returns:
            Subject and HTML body; every stored text is HTML-escaped.
        """
        name = html.escape(assistant_name)
        account = f" (<strong>{html.escape(account_email)}</strong>)" if account_email else ""
        body = "".join(
            [
                AiAssistantRequestEmail.paragraph(
                    f"Un agenda Google{account} vient d'être connecté à <strong>{name}</strong>, la réceptionniste "
                    f"de <strong>{html.escape(business_name)}</strong>. Les visiteurs de votre site y réservent "
                    "désormais leurs rendez-vous, sur vos créneaux libres et dans vos horaires."
                ),
                AiAssistantRequestEmail.paragraph(
                    "Si ce n'est pas vous, répondez tout de suite à cet email : nous déconnecterons cet agenda.",
                ),
            ]
        )
        return RenderedEmail(subject="Votre agenda Google est connecté", html=AiAssistantRequestEmail.document(body))

    @staticmethod
    def render_alert_phone_changed(*, assistant_name: str, new_phone: str | None) -> RenderedEmail:
        """
        Render the notice sent to the business address when the alert mobile changes from the client space.

        Args:
            assistant_name: The assistant's first name.
            new_phone: The new mobile in E.164, or None when the SMS alerts lost their number.

        Returns:
            Subject and HTML body; only the last two digits of the number are shown.
        """
        name = html.escape(assistant_name)
        change = (
            f"Les alertes SMS de <strong>{name}</strong> partent désormais vers le mobile se terminant par "
            f"<strong>{html.escape(new_phone[-2:])}</strong>."
            if new_phone
            else f"Les alertes SMS de <strong>{name}</strong> n'ont plus de mobile : elles ne partent plus."
        )
        body = "".join(
            [
                AiAssistantRequestEmail.paragraph(
                    f"Le mobile qui reçoit les alertes a été modifié depuis votre espace client. {change}"
                ),
                AiAssistantRequestEmail.paragraph(
                    "Si ce n'est pas vous, répondez tout de suite à cet email : nous rétablirons votre numéro.",
                ),
            ]
        )
        return RenderedEmail(
            subject="Votre mobile d'alerte a été modifié",
            html=AiAssistantRequestEmail.document(body),
        )
