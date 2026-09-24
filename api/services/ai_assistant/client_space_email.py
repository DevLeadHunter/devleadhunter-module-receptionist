"""The emails of the client space: its link (from the dashboard or an expired link), and the alert-mobile change notice."""

from __future__ import annotations

import html
from datetime import date

from services.ai_assistant.request_email import AiAssistantRequestEmail, RenderedEmail


class AiAssistantClientSpaceEmail:
    """Renders the client-space link email: what the space holds, the button, how long the link lasts."""

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
