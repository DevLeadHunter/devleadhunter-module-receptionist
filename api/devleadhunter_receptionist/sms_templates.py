"""The receptionist's SMS templates, added to the core's SMS library.

Same frank rules as the core's library (one segment in France, the price a month, the sign-off last). The
receptionist goes by its first name and « réceptionniste IA »: no word agrees with its gender.
"""

from enums.sms_template_category import SmsTemplateCategory
from services.sms.templates import SmsTemplate

_SIGN_OFF: str = "{signature}, {telephone}"

RECEPTIONIST_SMS_TEMPLATES: list[SmsTemplate] = [
    SmsTemplate(
        key="assistant-24-7",
        name="Réceptionniste IA - le soir, personne ne répond",
        category=SmsTemplateCategory.FIRST_CONTACT,
        body=(
            "{salutation}, {prenom_receptionniste}, votre réceptionniste IA, répond le soir : {lien_assistant} "
            "{prix_assistant}/mois. " + _SIGN_OFF
        ),
    ),
    SmsTemplate(
        key="assistant-langues",
        name="Réceptionniste IA - dans leur langue",
        category=SmsTemplateCategory.FIRST_CONTACT,
        body=(
            "{salutation}, {prenom_receptionniste}, votre réceptionniste IA multilingue : {lien_assistant} "
            "{prix_assistant}/mois. " + _SIGN_OFF
        ),
    ),
    SmsTemplate(
        key="assistant-demandes",
        name="Réceptionniste IA - devis par photo",
        category=SmsTemplateCategory.FIRST_CONTACT,
        body=(
            "{salutation}, {prenom_receptionniste}, réceptionniste IA, prend vos demandes par photo : {lien_assistant} "
            "{prix_assistant}/mois. " + _SIGN_OFF
        ),
    ),
    SmsTemplate(
        key="assistant-video",
        name="Réceptionniste IA - en vidéo",
        category=SmsTemplateCategory.FIRST_CONTACT,
        body=(
            "{salutation}, {prenom_receptionniste}, votre réceptionniste IA, en 30 s de vidéo : {lien_video_assistant} "
            "{prix_assistant}/mois. " + _SIGN_OFF
        ),
        fallback_key="assistant-24-7",
    ),
    SmsTemplate(
        key="assistant-relance",
        name="Réceptionniste IA - relance",
        category=SmsTemplateCategory.FOLLOW_UP,
        body=(
            "{salutation}, après mon email, {prenom_receptionniste} (IA) répond toujours : {lien_assistant} "
            "{prix_assistant}/mois. " + _SIGN_OFF
        ),
        recalls_an_email=True,
    ),
    SmsTemplate(
        key="assistant-relance-video",
        name="Réceptionniste IA - relance vidéo",
        category=SmsTemplateCategory.FOLLOW_UP,
        body=(
            "{salutation}, la vidéo de mon email : {prenom_receptionniste}, réceptionniste IA : {lien_video_assistant} "
            "{prix_assistant}/mois. " + _SIGN_OFF
        ),
        fallback_key="assistant-relance",
        recalls_an_email=True,
    ),
    SmsTemplate(
        key="assistant-prix-cash",
        name="Réceptionniste IA - le prix, sans détour",
        category=SmsTemplateCategory.FOLLOW_UP,
        body=(
            "{salutation}, {prenom_receptionniste}, votre réceptionniste IA : {prix_assistant}/mois, 1er mois "
            "remboursé. {lien_assistant} " + _SIGN_OFF
        ),
    ),
]
