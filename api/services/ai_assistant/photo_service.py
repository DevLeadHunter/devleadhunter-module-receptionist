"""
Quote by photo: a visitor sends a photo of the job (leak, dent, roof, garden…) through the widget.

The photo is re-encoded (1600 px max, no metadata: EXIF, location, comments dropped), stored on R2
under an unguessable key, and shown to a vision model that says what it sees, how urgent it looks and
what is missing to quote it — never a price. An off-topic photo is refused politely and deleted from
storage at once. The photos of a visit are attached to the request the visitor leaves
(``photos_json``), so the owner's email and SMS carry them; they are deleted after 90 days.
"""

from __future__ import annotations

import asyncio
import io
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar

from PIL import Image, ImageOps
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from enums.ai_assistant_photo import AiAssistantPhotoRejection, AiAssistantPhotoUrgency
from enums.ai_assistant_request import AiAssistantRequestChannel, AiAssistantRequestStatus
from enums.assistant_llm import AssistantLlmUsage
from models.ai_assistant import AiAssistant
from models.ai_assistant_message import AiAssistantMessage
from models.ai_assistant_photo import AiAssistantPhoto
from models.ai_assistant_request import AiAssistantRequest
from services.ai_assistant.assistant_service import ai_assistant_service
from services.ai_assistant.conversation_service import ai_assistant_conversation_service
from services.ai_assistant.knowledge_builder import LANGUAGE_NAMES
from services.ai_assistant.llm_router import assistant_llm_router
from services.r2_storage_service import r2_storage

logger = logging.getLogger(__name__)

MAX_PHOTO_BYTES = 8 * 1024 * 1024
MAX_PHOTOS_PER_SESSION = 3
# A 48-megapixel phone photo passes; a small file declaring a huge canvas (decompression bomb) does not.
# A PNG or WEBP decodes whole (only JPEG shrinks while decoding): 30 Mpx is about 120 Mo of pixels.
MAX_PIXELS = 30_000_000
MAX_EDGE_PX = 1600
# The widget uploads a JPEG; only photo formats are decoded, never Pillow's rarer readers (EPS, PSD, TGA...).
ACCEPTED_FORMATS = ("JPEG", "PNG", "WEBP")
JPEG_QUALITY = 82
RETENTION = timedelta(days=90)
# Photos count toward one quote request for as long as a visit can add to it (the request merge window).
QUOTA_WINDOW = timedelta(hours=24)
# How a photo shows in the conversation journal (the owner reads it in French).
PHOTO_JOURNAL_MARKER = "Photo envoyée"
_MAX_FIELD_CHARS = 255
_MAX_REPLY_CHARS = 600


def _utc_now() -> datetime:
    """Current time as naive UTC, the storage convention."""
    return datetime.now(UTC).replace(tzinfo=None)


class PhotoRejectedError(Exception):
    """A photo refused before any analysis (too large, unreadable, over quota) or that could not be stored."""

    def __init__(self, reason: AiAssistantPhotoRejection, message: str) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message


@dataclass(frozen=True)
class PhotoAnalysis:
    """What the vision model saw in a photo, and what the assistant answers the visitor."""

    relevant: bool | None
    object_label: str | None
    damage: str | None
    urgency: AiAssistantPhotoUrgency | None
    missing_questions: tuple[str, ...]
    reply: str


class AiAssistantPhotoVision:
    """Asks the vision model what a visitor's photo shows, to prepare a quote — never a price."""

    SYSTEM_PROMPT: ClassVar[str] = (
        "Tu es l'assistante virtuelle d'une entreprise. Un visiteur de son site t'envoie une photo pour "
        "obtenir un devis. Le métier de l'entreprise t'est donné : juge la photo AVEC CE MÉTIER en tête. "
        "Regarde la photo et réponds UNIQUEMENT par un objet JSON :\n"
        '{"relevant": true|false, "object": "…", "damage": "…", "urgency": "low"|"medium"|"high", '
        '"missing_questions": ["…"], "reply": "…"}\n'
        "- relevant : true dès que la photo peut aider à comprendre le besoin d'un client de ce métier. "
        "Pour un métier manuel, c'est l'objet ou le lieu du problème (toit, fuite, voiture, jardin, plat, "
        "pièce à rénover…). Pour un métier du numérique ou du service (agence web, développeur, graphiste, "
        "photographe, comptable…), c'est aussi bien un écran, une capture de site ou d'application, un "
        "logo, une maquette, un message d'erreur ou un document : un client montre son site actuel ou "
        "celui qu'il veut, c'est son besoin. false seulement si la photo n'a aucun rapport avec le métier "
        "(selfie, paysage, image choquante…).\n"
        "- object : ce qui est photographié, en quelques mots (ex. « aile avant gauche d'une voiture », "
        "« page d'accueil d'un site vitrine, vue sur tablette »).\n"
        "- damage : le problème ou le besoin visible, factuel (ex. « rayure profonde, peinture à refaire », "
        "« site daté, texte peu lisible, pas de bouton de contact ») ; vide si tu ne vois rien à améliorer.\n"
        "- urgency : high seulement pour un risque immédiat (fuite active, câble à nu, structure qui "
        "cède, site ou boutique en ligne hors service) ; medium si ça peut s'aggraver ; low sinon.\n"
        "- missing_questions : 1 ou 2 questions courtes, indispensables pour chiffrer (dimensions, "
        "accès, matériau, nombre de pages, ce qui doit changer…).\n"
        "- reply : 2 ou 3 phrases au visiteur, dans la langue demandée : ce que tu vois, dit avec les mots "
        "du métier (un développeur parle du site montré, pas de l'écran qui l'affiche), les questions "
        "manquantes, puis l'invitation à laisser son prénom et un téléphone pour recevoir le devis. Si "
        "la photo est hors sujet : refus poli, en invitant à envoyer une photo de ce dont il a besoin.\n"
        "Règles absolues : JAMAIS de prix, de fourchette, de coût ni de délai d'intervention — le devis "
        "est établi par l'entreprise. Ne décris pas les personnes. Ne diagnostique que ce qui est visible."
    )
    # Written by us, per widget language, when the model is unavailable or breaks a rule.
    FALLBACK_REPLIES: ClassVar[dict[str, str]] = {
        "fr": (
            "Merci pour la photo, je la transmets pour votre devis. Décrivez-moi le problème en quelques "
            "mots, et laissez-moi votre prénom et un téléphone pour être recontacté."
        ),
        "nl": (
            "Bedankt voor de foto, ik geef hem door voor uw offerte. Beschrijf het probleem in een paar "
            "woorden en laat uw voornaam en telefoonnummer achter, dan nemen we contact op."
        ),
        "en": (
            "Thank you for the photo, I am passing it on for your quote. Describe the problem in a few "
            "words and leave your first name and a phone number so we can get back to you."
        ),
        "de": (
            "Danke für das Foto, ich leite es für Ihr Angebot weiter. Beschreiben Sie das Problem kurz und "
            "hinterlassen Sie Ihren Vornamen und eine Telefonnummer, damit wir Sie kontaktieren."
        ),
        "lu": (
            "Merci fir d'Foto, ech ginn se fir Ären Devis weider. Beschreift de Problem a puer Wierder a "
            "loosst Äre Virnumm an eng Telefonsnummer, da mellen mir eis."
        ),
    }
    OFF_TOPIC_REPLIES: ClassVar[dict[str, str]] = {
        "fr": "Je ne vois pas sur cette photo de quoi préparer un devis. Envoyez-moi une photo du problème.",
        "nl": "Op deze foto zie ik niets om een offerte voor te maken. Stuur me een foto van het probleem.",
        "en": "I can't see anything to quote on this photo. Please send me a photo of the problem.",
        "de": "Auf diesem Foto sehe ich nichts für ein Angebot. Schicken Sie mir bitte ein Foto des Problems.",
        "lu": "Op dëser Foto gesinn ech näischt fir en Devis. Schéckt mer w.e.g. eng Foto vum Problem.",
    }
    # A figure with a currency, either way round (« 250 € », « EUR 250 », « 250,- Euro », « CHF 90 »):
    # nothing shown to the visitor may carry a price.
    PRICE_PATTERN: ClassVar[re.Pattern[str]] = re.compile(
        r"(?:€|\bchf|\beur(?:os?)?)\s?\d|\d[\d\s.,]*-?\s?(?:€|\b(?:eur|euros?|chf)\b)", re.IGNORECASE
    )
    _YES: ClassVar[frozenset[bool | int | str]] = frozenset({True, "true", "yes", "oui", "1"})
    _NO: ClassVar[frozenset[bool | int | str]] = frozenset({False, "false", "no", "non", "0"})

    async def describe(
        self, *, url: str, business_name: str, trade: str | None, language: str | None, eu_only: bool = False
    ) -> PhotoAnalysis:
        """
        Ask the vision model about a photo (Mistral first, see ``llm_router``).

        Args:
            url: Public URL of the stored photo.
            business_name: The business the visitor asks.
            trade: Its trade (the prospect category), to judge what is on-topic.
            language: The widget language, for the reply.
            eu_only: The assistant only allows Mistral (no Groq fallback).

        Returns:
            The analysis; a neutral one (``relevant`` None) when no model is available.
        """
        context = (
            f"Entreprise : {business_name}" + (f" ({trade})" if trade else "") + ". "
            f"Réponds au visiteur en {LANGUAGE_NAMES[self._lang(language)]}."
        )
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [{"type": "text", "text": context}, {"type": "image_url", "image_url": {"url": url}}],
            },
        ]
        try:
            answer = await assistant_llm_router.complete_json(
                AssistantLlmUsage.VISION, messages, eu_only=eu_only, max_tokens=700, temperature=0.2, timeout=60.0
            )
        except Exception:
            logger.warning("Vision call failed for a photo", exc_info=True)
            answer = None
        return self.parse(answer, language)

    @classmethod
    def parse(cls, answer: dict[str, Any] | None, language: str | None) -> PhotoAnalysis:
        """
        Validate the model's answer, keeping only what honours the contract.

        Args:
            answer: The parsed JSON, or None when the model failed.
            language: The widget language, for our own wording.

        Returns:
            The analysis; our own reply replaces one that is empty or quotes a price, and a description
            quoting a price is dropped.
        """
        if not isinstance(answer, dict):
            return cls.fallback(language)
        lang = cls._lang(language)
        relevant = cls._verdict(answer.get("relevant"))
        if relevant is False:
            reply = cls._text(answer.get("reply"), _MAX_REPLY_CHARS)
            safe = reply if reply and not cls.PRICE_PATTERN.search(reply) else cls.OFF_TOPIC_REPLIES[lang]
            return PhotoAnalysis(False, None, None, None, (), safe)
        urgency_value = answer.get("urgency")
        urgency_text = urgency_value.strip().lower() if isinstance(urgency_value, str) else None
        urgency = (
            AiAssistantPhotoUrgency(urgency_text)
            if urgency_text in {level.value for level in AiAssistantPhotoUrgency}
            else None
        )
        raw_questions = answer.get("missing_questions")
        questions = (
            cls._text(item, _MAX_FIELD_CHARS) for item in (raw_questions if isinstance(raw_questions, list) else [])
        )
        missing = tuple(question for question in questions if question and not cls.PRICE_PATTERN.search(question))[:2]
        reply = cls._text(answer.get("reply"), _MAX_REPLY_CHARS)
        if not reply or cls.PRICE_PATTERN.search(reply):
            reply = cls.FALLBACK_REPLIES[lang]
        return PhotoAnalysis(
            relevant=relevant,
            object_label=cls._without_price(cls._text(answer.get("object"), _MAX_FIELD_CHARS)),
            damage=cls._without_price(cls._text(answer.get("damage"), _MAX_FIELD_CHARS)),
            urgency=urgency,
            missing_questions=missing,
            reply=reply,
        )

    @classmethod
    def fallback(cls, language: str | None) -> PhotoAnalysis:
        """
        The analysis used when the model cannot look at the photo: kept, unjudged, a neutral reply.

        Args:
            language: The widget language.

        Returns:
            A neutral analysis.
        """
        return PhotoAnalysis(None, None, None, None, (), cls.FALLBACK_REPLIES[cls._lang(language)])

    @classmethod
    def _lang(cls, language: str | None) -> str:
        """A supported widget language (French by default)."""
        code = (language or "").strip().lower()[:2]
        return code if code in cls.FALLBACK_REPLIES else "fr"

    @classmethod
    def _without_price(cls, text: str | None) -> str | None:
        """A description, dropped when it slips in a price."""
        return None if text and cls.PRICE_PATTERN.search(text) else text

    @classmethod
    def _verdict(cls, value: Any) -> bool | None:
        """The on-topic verdict read leniently (« false », "0"…); None when the model gave none."""
        normalized = value.strip().lower() if isinstance(value, str) else value
        if isinstance(normalized, bool | str):
            if normalized in cls._YES:
                return True
            if normalized in cls._NO:
                return False
        if isinstance(normalized, int):
            return bool(normalized)
        return None

    @staticmethod
    def _text(value: Any, max_chars: int) -> str | None:
        """A trimmed, bounded string, or None."""
        if not isinstance(value, str):
            return None
        cleaned = " ".join(value.split())
        return cleaned[:max_chars] or None


class AiAssistantPhotoService:
    """Receives the visitors' photos, attaches them to their request and forgets them after 90 days."""

    def __init__(self, vision: AiAssistantPhotoVision | None = None) -> None:
        self._vision = vision or AiAssistantPhotoVision()

    async def receive(
        self,
        db: Session,
        *,
        assistant: AiAssistant,
        data: bytes,
        session_id: str,
        language: str | None,
        is_test: bool = False,
    ) -> AiAssistantPhoto:
        """
        Store a visitor's photo, have it described, and journal the exchange.

        Args:
            db: Active database session (committed).
            assistant: The assistant the visitor talks to.
            data: The uploaded bytes.
            session_id: The widget session (non-blank; at most 3 photos per quote request).
            language: The widget language, for the reply.
            is_test: Sent from an internal visit (``?internal=1``).

        Returns:
            The photo row; ``relevant`` False means refused (and already deleted from storage).

        Raises:
            PhotoRejectedError: Too large, not a readable image, over the quota, or storage unavailable.
        """
        normalized_session = session_id.strip()[:64]
        if self.kept_count(db, assistant.id, normalized_session) >= MAX_PHOTOS_PER_SESSION:
            raise PhotoRejectedError(
                AiAssistantPhotoRejection.QUOTA, f"{MAX_PHOTOS_PER_SESSION} photos maximum par demande."
            )
        if len(data) > MAX_PHOTO_BYTES:
            raise PhotoRejectedError(AiAssistantPhotoRejection.TOO_LARGE, "Photo trop lourde (8 Mo maximum).")
        # Decoding is CPU work: off the event loop, so the API keeps serving meanwhile.
        jpeg = await asyncio.to_thread(self.normalize, data)
        # Photos sent at the same time all passed the first check: count again before keeping this one.
        if self.kept_count(db, assistant.id, normalized_session) >= MAX_PHOTOS_PER_SESSION:
            raise PhotoRejectedError(
                AiAssistantPhotoRejection.QUOTA, f"{MAX_PHOTOS_PER_SESSION} photos maximum par demande."
            )
        business_name = assistant.business_name
        eu_only = bool(assistant.eu_only)
        trade = ai_assistant_service.business_category(db, assistant)
        # The row comes first: a restart mid-way leaves a known key for the purge, the quota sees the
        # photo at once, and the commit hands the connection back during the slow storage and vision calls.
        photo = AiAssistantPhoto(
            user_id=assistant.user_id,
            prospect_id=assistant.prospect_id,
            assistant_id=assistant.id,
            session_id=normalized_session,
            storage_key=r2_storage.assistant_photo_key(),
            size_bytes=len(jpeg),
            is_test=is_test,
        )
        db.add(photo)
        db.commit()
        try:
            url = await r2_storage.upload_bytes_async(photo.storage_key, jpeg, "image/jpeg")
        except Exception as exc:
            logger.warning("Photo %s: storage upload failed", photo.id, exc_info=True)
            photo.storage_key = None
            photo.deleted_at = _utc_now()
            db.commit()
            raise PhotoRejectedError(
                AiAssistantPhotoRejection.UNAVAILABLE, "Envoi de photo indisponible pour le moment."
            ) from exc
        analysis = await self._vision.describe(
            url=url, business_name=business_name, trade=trade, language=language, eu_only=eu_only
        )
        photo.url = url
        photo.relevant = analysis.relevant
        photo.object_label = analysis.object_label
        photo.damage = analysis.damage
        photo.urgency = analysis.urgency.value if analysis.urgency else None
        photo.missing_questions = list(analysis.missing_questions) or None
        photo.reply = analysis.reply
        # An off-topic photo leaves storage at once; if that fails, its link is hidden and the purge retries.
        if analysis.relevant is False and not await self._forget(photo):
            photo.url = None
        db.commit()
        db.refresh(photo)
        try:
            ai_assistant_conversation_service.record_turn(
                db,
                assistant=assistant,
                session_id=normalized_session,
                language=language,
                visitor_message=PHOTO_JOURNAL_MARKER,
                reply=analysis.reply,
                is_test=is_test,
                visitor_photo_url=photo.url,
            )
        except Exception:
            logger.warning("Photo %s: journal failed", photo.id, exc_info=True)
            db.rollback()
        return photo

    def kept_count(self, db: Session, assistant_id: int, session_id: str, *, now: datetime | None = None) -> int:
        """
        How many photos of a widget session count toward the current quote request.

        Refused, deleted and older photos do not count, nor those of a request already handled: a
        returning visitor starts a new request with a fresh quota.

        Args:
            db: Active database session.
            assistant_id: The assistant.
            session_id: The widget session.
            now: Current naive UTC time (tests); defaults to now.

        Returns:
            The number of photos counting against the quota.
        """
        current = now or _utc_now()
        open_requests = select(AiAssistantRequest.id).where(
            AiAssistantRequest.status == AiAssistantRequestStatus.NEW.value
        )
        return (
            db.query(AiAssistantPhoto.id)
            .filter(
                AiAssistantPhoto.assistant_id == assistant_id,
                AiAssistantPhoto.session_id == session_id,
                AiAssistantPhoto.relevant.is_not(False),
                AiAssistantPhoto.deleted_at.is_(None),
                AiAssistantPhoto.created_at >= current - QUOTA_WINDOW,
                or_(AiAssistantPhoto.request_id.is_(None), AiAssistantPhoto.request_id.in_(open_requests)),
            )
            .count()
        )

    def attach_to_request(self, db: Session, request: AiAssistantRequest) -> None:
        """
        Link the kept photos of this visit to its request and list them in ``photos_json`` (3 at most).

        Args:
            db: Active database session (the caller commits).
            request: The request just captured or updated (flushed, so it has an id).
        """
        if not request.session_id:
            return
        recent = _utc_now() - QUOTA_WINDOW
        photos = (
            db.query(AiAssistantPhoto)
            .filter(
                AiAssistantPhoto.assistant_id == request.assistant_id,
                AiAssistantPhoto.session_id == request.session_id,
                AiAssistantPhoto.relevant.is_not(False),
                AiAssistantPhoto.url.is_not(None),
                or_(
                    AiAssistantPhoto.request_id == request.id,
                    and_(AiAssistantPhoto.request_id.is_(None), AiAssistantPhoto.created_at >= recent),
                ),
            )
            .order_by(AiAssistantPhoto.id)
            .limit(MAX_PHOTOS_PER_SESSION)
            .all()
        )
        if not photos:
            return
        for photo in photos:
            photo.request_id = request.id
        request.photos_json = [
            {"url": photo.url, "object": photo.object_label, "damage": photo.damage, "urgency": photo.urgency}
            for photo in photos
        ]
        request.channel = AiAssistantRequestChannel.PHOTO.value

    async def purge_expired(self, db: Session, *, now: datetime | None = None) -> int:
        """
        Delete from storage the photos older than 90 days (and the off-topic ones not deleted yet),
        and their links from the requests.

        Args:
            db: Active database session (committed).
            now: Current naive UTC time (tests); defaults to now.

        Returns:
            How many photos were forgotten (a failed storage delete is retried on the next pass).
        """
        current = now or _utc_now()
        due = (
            db.query(AiAssistantPhoto)
            .filter(
                AiAssistantPhoto.deleted_at.is_(None),
                or_(AiAssistantPhoto.created_at < current - RETENTION, AiAssistantPhoto.relevant.is_(False)),
            )
            .all()
        )
        forgotten: list[AiAssistantPhoto] = []
        gone_urls: set[str] = set()
        for photo in due:
            url = photo.url
            if await self._forget(photo, now=current):
                forgotten.append(photo)
                if url:
                    gone_urls.add(url)
        if gone_urls:
            # The journal showed the photo beside the visitor's turn: the link goes with the file.
            db.query(AiAssistantMessage).filter(AiAssistantMessage.photo_url.in_(gone_urls)).update(
                {AiAssistantMessage.photo_url: None}, synchronize_session=False
            )
        request_ids = {photo.request_id for photo in forgotten if photo.request_id is not None}
        if request_ids:
            for request in db.query(AiAssistantRequest).filter(AiAssistantRequest.id.in_(request_ids)).all():
                request.photos_json = [
                    {**entry, "url": None} if isinstance(entry, dict) and entry.get("url") in gone_urls else entry
                    for entry in (request.photos_json or [])
                ]
        db.commit()
        return len(forgotten)

    @staticmethod
    def normalize(data: bytes) -> bytes:
        """
        Re-encode a photo as a bounded JPEG, upright, without any metadata (EXIF, location, comment).

        Args:
            data: The uploaded bytes.

        Returns:
            The JPEG bytes (1600 px on the longest side at most).

        Raises:
            PhotoRejectedError: When the bytes are not a JPEG, PNG or WEBP image, or declare too many pixels.
        """
        try:
            with Image.open(io.BytesIO(data), formats=ACCEPTED_FORMATS) as source:
                width, height = source.size
                if width * height > MAX_PIXELS:
                    raise PhotoRejectedError(
                        AiAssistantPhotoRejection.TOO_LARGE, "Photo trop grande (50 mégapixels maximum)."
                    )
                # A JPEG decodes straight at a reduced scale: fast and light even for a 48 Mpx photo.
                source.draft("RGB", (MAX_EDGE_PX, MAX_EDGE_PX))
                image = ImageOps.exif_transpose(source).convert("RGB")
        except PhotoRejectedError:
            raise
        except Exception as exc:  # Pillow raises many types on a corrupted file (SyntaxError included).
            raise PhotoRejectedError(
                AiAssistantPhotoRejection.UNREADABLE, "Format non pris en charge : envoyez une photo JPEG ou PNG."
            ) from exc
        image.thumbnail((MAX_EDGE_PX, MAX_EDGE_PX))
        # No comment, colour profile or other metadata may travel to the public file.
        image.info.clear()
        output = io.BytesIO()
        image.save(output, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        return output.getvalue()

    @staticmethod
    async def _forget(photo: AiAssistantPhoto, *, now: datetime | None = None) -> bool:
        """
        Delete a photo's image from storage and clear its link (its description stays).

        Returns:
            False when storage could not delete it (nothing is cleared, a later pass retries).
        """
        if photo.storage_key:
            try:
                await r2_storage.delete_async(photo.storage_key)
            except Exception:
                logger.warning("Photo %s: storage delete failed", photo.id, exc_info=True)
                return False
        photo.storage_key = None
        photo.url = None
        photo.deleted_at = now or _utc_now()
        return True


ai_assistant_photo_service = AiAssistantPhotoService()
