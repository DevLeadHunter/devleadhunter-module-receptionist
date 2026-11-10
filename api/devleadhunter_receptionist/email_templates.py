"""The receptionist's cold emails, appended to the core's shared library by its seeder.

Same frank rules as the core's library (who writes, the one link, the price in the very first message, the real day
the demo goes offline, how to say no). Proper to the receptionist:
  - The price is ``{prix_assistant}``, the user's monthly price (per country at send time).
  - The templates say plainly that the receptionist is a virtual assistant (an AI) living at an address of its own (a
    hosted page, the prospect needs no website), and that the first month is satisfied or refunded. Half the casting
    is masculine (Hugo, Marc, Nathan): the gendered words come from ``{receptionniste}`` and ``{assistant_virtuel}``,
    and the text names the receptionist by first name rather than « il » or « elle ».
  - One door per email: ``{lien_assistant}``, or the video thumbnail ``{vignette_video_assistant}`` for the « vidéo »
    templates (held back by the queue until the video exists).

Variables: {lien_assistant} {prenom_receptionniste} {receptionniste} {assistant_virtuel} {lien_video_assistant}
{vignette_video_assistant} {prix_assistant}, plus the core's ({salutation}, {entreprise}, {date_expiration}…).
"""

from __future__ import annotations

from enums.email_template_category import EmailTemplateCategory

_FIRST = EmailTemplateCategory.FIRST_EMAIL.value
_FOLLOW = EmailTemplateCategory.FOLLOW_UP.value

_SINGLE_ASK_WITH_EXIT = (
    "<p>Un mot me suffit : oui, non, ou une question. Si c'est non, dites-le-moi et je ne vous recontacte plus.</p>"
)

_RECEPTIONIST_PRICE_LINE = (
    "<p>C'est {prix_assistant} par mois, sans engagement. Le premier mois est satisfait ou remboursé.</p>"
)
_RECEPTIONIST_EXPIRY_LINE = "<p>La démo reste en ligne jusqu'au {date_expiration}. Après, je la retire.</p>"
_RECEPTIONIST_TIME_TO_THINK_LINE = (
    "<p>Besoin d'y réfléchir ? Prenez votre temps : la démo reste en ligne jusqu'au {date_expiration}.</p>"
)


RECEPTIONIST_EMAIL_TEMPLATES: list[dict[str, object]] = [
    {
        "name": "Réceptionniste IA - franc",
        "category": _FIRST,
        "sort_order": 16,
        "subject": "{receptionniste} pour {entreprise}",
        "body_html": (
            "<p>{salutation},</p>"
            "<p>Je fais des outils web pour les artisans et les commerçants, et j'ai préparé "
            "{prenom_receptionniste} pour {entreprise} : {assistant_virtuel} (IA) qui répond à vos clients quand "
            "vous ne pouvez pas. {prenom_receptionniste} est déjà en ligne, à une adresse à son nom : "
            "{lien_assistant}</p>" + _RECEPTIONIST_PRICE_LINE + _RECEPTIONIST_EXPIRY_LINE + _SINGLE_ASK_WITH_EXIT
        ),
    },
    {
        "name": "Réceptionniste IA - en bref",
        "category": _FIRST,
        "sort_order": 15,
        "subject": "votre réceptionniste, en bref",
        "body_html": (
            "<p>{salutation},</p>"
            "<p>Je fais des outils web pour les artisans et les commerçants, et j'ai préparé "
            "{prenom_receptionniste} pour {entreprise} : {assistant_virtuel} (IA). En bref :</p>"
            "<ul>"
            "<li>Réponses à vos clients 24 h sur 24, dans leur langue</li>"
            "<li>Demandes de devis avec photo</li>"
            "<li>Prise de rendez-vous dans votre agenda Google</li>"
            "<li>Chaque demande transmise par mail, les urgentes aussi par SMS</li>"
            "<li>Uniquement vos vraies informations : rien d'inventé</li>"
            "<li>Une adresse à son nom pour votre fiche Google, pas besoin de site</li>"
            "<li>Un bilan chaque mois</li>"
            "</ul>"
            "<p>{prenom_receptionniste} est déjà en ligne : {lien_assistant}</p>"
            + _RECEPTIONIST_PRICE_LINE
            + _RECEPTIONIST_EXPIRY_LINE
            + _SINGLE_ASK_WITH_EXIT
        ),
    },
    {
        "name": "Réceptionniste IA - le soir, personne ne répond",
        "category": _FIRST,
        "sort_order": 10,
        "subject": "vos clients du soir",
        "body_html": (
            "<p>{salutation},</p>"
            "<p>Je fais des outils web pour les artisans et les commerçants, et j'ai préparé "
            "{prenom_receptionniste} pour {entreprise} : {assistant_virtuel} (IA) qui, le soir et le week-end, "
            "répond tout de suite à vos clients et vous transmet chaque demande. {prenom_receptionniste} est déjà "
            "en ligne, à une adresse à son nom : {lien_assistant}</p>"
            "{vignette_video_assistant}" + _RECEPTIONIST_PRICE_LINE + _RECEPTIONIST_EXPIRY_LINE + _SINGLE_ASK_WITH_EXIT
        ),
    },
    {
        "name": "Réceptionniste IA - devis par photo",
        "category": _FIRST,
        "sort_order": 11,
        "subject": "une photo, une demande de devis",
        "body_html": (
            "<p>{salutation},</p>"
            "<p>Je fais des outils web pour les artisans et les commerçants, et j'ai préparé "
            "{prenom_receptionniste} pour {entreprise} : {assistant_virtuel} (IA). Un client envoie la photo de son "
            "problème à 22 h, et vous recevez une demande de devis complète, avec les bonnes questions déjà posées. "
            "{prenom_receptionniste} est déjà en ligne, à une adresse à son nom, et accepte n'importe quelle "
            "photo : {lien_assistant}</p>"
            "{vignette_video_assistant}" + _RECEPTIONIST_PRICE_LINE + _RECEPTIONIST_EXPIRY_LINE + _SINGLE_ASK_WITH_EXIT
        ),
    },
    {
        "name": "Réceptionniste IA - dans leur langue",
        "category": _FIRST,
        "sort_order": 12,
        "subject": "vos clients, dans leur langue",
        "body_html": (
            "<p>{salutation},</p>"
            "<p>Une partie des clients de {entreprise} n'ose pas écrire en français et repart sans rien demander. "
            "Je fais des outils web pour les artisans et les commerçants, et j'ai préparé pour vous "
            "{prenom_receptionniste} : {assistant_virtuel} (IA) qui répond à vos clients dans leur langue, "
            "24 h sur 24, et vous transmet leur demande en français. {prenom_receptionniste} est déjà en ligne, à "
            "une adresse à son nom : {lien_assistant}</p>"
            "{vignette_video_assistant}" + _RECEPTIONIST_PRICE_LINE + _RECEPTIONIST_EXPIRY_LINE + _SINGLE_ASK_WITH_EXIT
        ),
    },
    # The video as its only door, held back until generated.
    {
        "name": "Réceptionniste IA - en vidéo",
        "category": _FIRST,
        "sort_order": 9,
        "subject": "votre réceptionniste, en vidéo",
        "body_html": (
            "<p>{salutation},</p>"
            "<p>Je fais des outils web pour les artisans et les commerçants, et j'ai préparé "
            "{prenom_receptionniste} pour {entreprise} : {assistant_virtuel} (IA) qui répond à vos clients le soir "
            "et le week-end et vous transmet chaque demande. Je vous montre comment ça marche, en 30 secondes :</p>"
            "{vignette_video_assistant}" + _RECEPTIONIST_PRICE_LINE + _RECEPTIONIST_EXPIRY_LINE + _SINGLE_ASK_WITH_EXIT
        ),
    },
    {
        "name": "Réceptionniste IA - relance",
        "category": _FOLLOW,
        "sort_order": 10,
        "subject": "avant que je retire la démo",
        "body_html": (
            "<p>{salutation},</p>"
            "<p>Dernier mail de ma part. Pour {entreprise}, {prenom_receptionniste} ({assistant_virtuel}, IA) "
            "répond toujours à cette adresse : {lien_assistant}</p>"
            "<p>Pour garder {prenom_receptionniste}, c'est {prix_assistant} par mois, sans engagement, premier mois "
            "satisfait ou remboursé. Sinon, rien à faire.</p>" + _RECEPTIONIST_TIME_TO_THINK_LINE
        ),
    },
    {
        "name": "Réceptionniste IA - le prix, sans détour",
        "category": _FOLLOW,
        "sort_order": 13,
        "subject": "le prix, sans détour",
        "body_html": (
            "<p>{salutation},</p>"
            "<p>Sans détour : {prix_assistant} par mois pour que {prenom_receptionniste}, votre réceptionniste "
            "({assistant_virtuel}, IA), réponde à vos clients à votre place quand vous ne pouvez pas. Sans "
            "engagement, premier mois satisfait ou remboursé.</p>"
            "<p>{prenom_receptionniste} répond déjà à cette adresse : {lien_assistant}</p>"
            "<p>Je retire la démo le {date_expiration}. Un mot me suffit, même un non.</p>"
        ),
    },
]
