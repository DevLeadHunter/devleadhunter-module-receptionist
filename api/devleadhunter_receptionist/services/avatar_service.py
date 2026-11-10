"""
The receptionist's own portrait: a photo or the business's logo, uploaded from the dashboard in place of the casting.

The image is normalised once, at upload: turned upright, then made square at 512 px. A photo is cropped to its centre,
whatever its format. A logo is fitted whole: trimmed of its empty edges, then scaled so its farthest visible point stays
inside the disc. A cut-out one keeps its transparency, so the disc shows around it in the colour the owner chose; one on
a plain background (its four edges the same colour) sits on a disc of that colour. It is stored as WebP on R2 under a
new key at each upload, so no cache serves the previous one, which is then deleted. The image stays at hand while the
receptionist shows a casting face: it only shows once chosen (``avatar_enabled``).
"""

from __future__ import annotations

import logging
import math
import re
from io import BytesIO
from typing import ClassVar

from fastapi import UploadFile
from PIL import Image, ImageChops, ImageOps, UnidentifiedImageError
from sqlalchemy.orm import Session

from models.ai_assistant import AiAssistant
from services.r2_storage_service import r2_storage

logger = logging.getLogger(__name__)


class AvatarRefusal(ValueError):
    """An image the portrait cannot take, with the sentence the dashboard shows; ``is_too_large`` answers 413."""

    def __init__(self, message: str, *, is_too_large: bool = False) -> None:
        super().__init__(message)
        self.is_too_large = is_too_large


class AvatarStorageError(RuntimeError):
    """The image was fine but storage refused it: nothing changed on the assistant."""


class AiAssistantAvatarService:
    """Stores, serves and removes a receptionist's own portrait."""

    MAX_BYTES: ClassVar[int] = 2 * 1024 * 1024
    SIDE_PX: ClassVar[int] = 512
    # A fitted image reaches at most this share of the disc's radius; the rest is the disc around it.
    FITTED_REACH: ClassVar[float] = 0.86
    # Pixels at most this opaque are left out of a fitted image's outline (a faint shadow, a halo).
    VISIBLE_ALPHA: ClassVar[int] = 16
    # A logo's outline and an image's edges are measured on a copy reduced to this side.
    SAMPLE_SIDE_PX: ClassVar[int] = 128
    # How far (per channel, out of 255) a pixel may be from a plain background and still count as that background.
    PLAIN_TOLERANCE: ClassVar[int] = 24
    # The share of an opaque image's edges that must be one colour for it to be read as a logo on a plain background.
    PLAIN_EDGE_SHARE: ClassVar[float] = 0.97
    # Above this many pixels, an image is refused before it is decoded in full.
    MAX_PIXELS: ClassVar[int] = 40_000_000
    # Where an opaque photo is cropped: centred, a little above the middle, where a face usually is.
    CROP_CENTERING: ClassVar[tuple[float, float]] = (0.5, 0.42)
    _ALLOWED_CONTENT_TYPES: ClassVar[frozenset[str]] = frozenset({"image/png", "image/jpeg", "image/webp"})
    _HEX_COLOR: ClassVar[re.Pattern[str]] = re.compile(r"^#[0-9a-f]{6}$")

    async def store(self, db: Session, assistant: AiAssistant, file: UploadFile) -> AiAssistant:
        """
        Keep an uploaded image as the business's own portrait, in place of any previous one; it shows once chosen.

        Args:
            db: Active database session.
            assistant: The assistant.
            file: The uploaded PNG, JPEG or WebP.

        Returns:
            The refreshed assistant.

        Raises:
            AvatarRefusal: When the file is not an accepted, readable image of 2 MB at most.
            AvatarStorageError: When storage refused the normalised image.
        """
        content_type = (file.content_type or "").lower().split(";")[0].strip()
        if content_type not in self._ALLOWED_CONTENT_TYPES:
            raise AvatarRefusal("Format non pris en charge : envoyez une image PNG, JPG ou WebP.")
        data = await file.read(self.MAX_BYTES + 1)
        if not data:
            raise AvatarRefusal("Le fichier est vide.")
        if len(data) > self.MAX_BYTES:
            raise AvatarRefusal("L'image dépasse 2 Mo.", is_too_large=True)
        portrait, is_transparent = self.normalized(data)
        key = r2_storage.assistant_avatar_key(assistant.id)
        try:
            await r2_storage.upload_bytes_async(key, portrait, "image/webp")
        except Exception as exc:
            logger.exception("Assistant %s: its portrait could not be stored", assistant.id)
            raise AvatarStorageError("L'image n'a pas pu être enregistrée. Réessayez.") from exc
        previous_key = assistant.avatar_key
        assistant.avatar_key = key
        assistant.avatar_is_transparent = is_transparent
        db.commit()
        db.refresh(assistant)
        if previous_key:
            await self._delete_quietly(previous_key)
        return assistant

    async def clear(self, db: Session, assistant: AiAssistant) -> AiAssistant:
        """
        Delete the business's own image: the receptionist shows its casting face again.

        Args:
            db: Active database session.
            assistant: The assistant.

        Returns:
            The refreshed assistant.
        """
        previous_key = assistant.avatar_key
        assistant.avatar_key = None
        assistant.avatar_enabled = False
        assistant.avatar_is_transparent = None
        db.commit()
        db.refresh(assistant)
        if previous_key:
            await self._delete_quietly(previous_key)
        return assistant

    @classmethod
    def normalized(cls, data: bytes) -> tuple[bytes, bool]:
        """
        The image as the portrait shows it: upright, square, ``SIDE_PX`` wide, as WebP.

        Args:
            data: The uploaded file.

        Returns:
            The WebP bytes, and whether the portrait has transparent areas (where the disc shows).

        Raises:
            AvatarRefusal: When the file is not a readable image, or far too large to decode.
        """
        try:
            image = Image.open(BytesIO(data))
            if image.width * image.height > cls.MAX_PIXELS:
                raise AvatarRefusal("Cette image est trop grande : réduisez-la sous 6 000 pixels de côté.")
            image = ImageOps.exif_transpose(image)
            image.load()
        except AvatarRefusal:
            raise
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
            raise AvatarRefusal("Cette image ne s'ouvre pas : essayez un autre fichier.") from exc
        rgba = image.convert("RGBA")
        alpha = rgba.getchannel("A")
        if alpha.getextrema()[0] < 255:
            visible = alpha.point(lambda value: 255 if value > cls.VISIBLE_ALPHA else 0)
            return cls._encoded(cls._fitted(rgba, visible, (0, 0, 0, 0))), True
        background = cls._plain_edge_colour(rgba)
        if background is not None:
            on_background = cls._fitted(rgba, cls._unlike(rgba, background), (*background, 255))
            return cls._encoded(on_background.convert("RGB")), False
        photo = ImageOps.fit(
            rgba.convert("RGB"), (cls.SIDE_PX, cls.SIDE_PX), Image.Resampling.LANCZOS, centering=cls.CROP_CENTERING
        )
        return cls._encoded(photo), False

    @staticmethod
    def public_url(assistant: AiAssistant) -> str | None:
        """
        The address of the assistant's own portrait, shown or not.

        Args:
            assistant: The assistant.

        Returns:
            Its public URL, or None when no image was sent (or storage has no public address here).
        """
        if not assistant.avatar_key:
            return None
        try:
            return r2_storage.public_url(assistant.avatar_key)
        except RuntimeError:
            logger.warning("Assistant %s: its portrait has no public address (storage not configured)", assistant.id)
            return None

    @classmethod
    def shown_url(cls, assistant: AiAssistant) -> str | None:
        """
        The business's own image, when the receptionist shows it.

        Args:
            assistant: The assistant.

        Returns:
            Its public URL, or None when the receptionist shows its casting face.
        """
        return cls.public_url(assistant) if assistant.avatar_enabled else None

    @staticmethod
    def shown_background(assistant: AiAssistant) -> str | None:
        """
        The colour of the disc around the business's own image, when the receptionist shows a cut-out one.

        Args:
            assistant: The assistant.

        Returns:
            The colour, or None for the accent's tint (a casting face, or an image covering the disc).
        """
        if assistant.avatar_enabled and assistant.avatar_key and assistant.avatar_is_transparent:
            return assistant.avatar_background
        return None

    @classmethod
    def background_of(cls, value: str | None) -> str | None:
        """
        The disc colour to keep from an edit.

        Args:
            value: The colour typed or picked (« #F4E9DC »), or empty for the accent's tint.

        Returns:
            The colour in lower case, or None for the accent's tint.

        Raises:
            ValueError: When the value is not a « #rrggbb » colour.
        """
        cleaned = (value or "").strip().lower()
        if not cleaned:
            return None
        if not cls._HEX_COLOR.match(cleaned):
            raise ValueError("Couleur de fond invalide : une couleur au format #rrggbb est attendue")
        return cleaned

    @staticmethod
    def _encoded(portrait: Image.Image) -> bytes:
        """The portrait as the WebP file stored on R2."""
        buffer = BytesIO()
        portrait.save(buffer, format="WEBP", quality=90, method=6)
        return buffer.getvalue()

    @classmethod
    def _fitted(cls, image: Image.Image, visible: Image.Image, fill: tuple[int, int, int, int]) -> Image.Image:
        """
        The visible part of the image, centred on a square of ``fill`` and scaled so none of it leaves the disc.

        Args:
            image: The upright image, in RGBA.
            visible: Its visible pixels (non-zero): the opaque ones, or those unlike its plain background.
            fill: The colour around it: transparent, or the plain background it came on.

        Returns:
            The square portrait.

        Raises:
            AvatarRefusal: When nothing in the image is visible.
        """
        box = visible.getbbox()
        if box is None:
            raise AvatarRefusal("Cette image ne montre rien : choisissez-en une autre.")
        content = image.crop(box)
        scale = (cls.SIDE_PX / 2 * cls.FITTED_REACH) / cls._visible_reach(visible.crop(box))
        content = content.resize(
            (max(1, round(content.width * scale)), max(1, round(content.height * scale))), Image.Resampling.LANCZOS
        )
        canvas = Image.new("RGBA", (cls.SIDE_PX, cls.SIDE_PX), fill)
        canvas.alpha_composite(content, ((cls.SIDE_PX - content.width) // 2, (cls.SIDE_PX - content.height) // 2))
        return canvas

    @classmethod
    def _plain_edge_colour(cls, image: Image.Image) -> tuple[int, int, int] | None:
        """
        The colour all around an opaque image when its four edges are one plain colour, as a logo on its background.

        Args:
            image: The upright, opaque image.

        Returns:
            That colour, or None when the edges vary (a photo).
        """
        sample = image.convert("RGB")
        sample.thumbnail((cls.SAMPLE_SIDE_PX, cls.SAMPLE_SIDE_PX), Image.Resampling.BOX)
        pixels = sample.load()
        last_column, last_row = sample.width - 1, sample.height - 1
        edges = [pixels[column, row] for column in range(sample.width) for row in {0, last_row}]
        edges += [pixels[column, row] for row in range(1, last_row) for column in {0, last_column}]
        median = tuple(sorted(channel)[len(channel) // 2] for channel in zip(*edges, strict=True))
        alike = sum(
            1 for pixel in edges if max(abs(a - b) for a, b in zip(pixel, median, strict=True)) <= cls.PLAIN_TOLERANCE
        )
        return (median[0], median[1], median[2]) if alike >= cls.PLAIN_EDGE_SHARE * len(edges) else None

    @classmethod
    def _unlike(cls, image: Image.Image, background: tuple[int, int, int]) -> Image.Image:
        """
        The pixels that stand out from a plain background.

        Args:
            image: The upright, opaque image.
            background: Its plain background colour.

        Returns:
            A mask, non-zero where a pixel differs from the background by more than ``PLAIN_TOLERANCE``.
        """
        difference = ImageChops.difference(image.convert("RGB"), Image.new("RGB", image.size, background))
        red, green, blue = difference.split()
        strongest = ImageChops.lighter(ImageChops.lighter(red, green), blue)
        return strongest.point(lambda value: 255 if value > cls.PLAIN_TOLERANCE else 0)

    @classmethod
    def _visible_reach(cls, mask: Image.Image) -> float:
        """
        How far the visible pixels reach from the centre of their mask: a square logo by its corners, a round one by
        its edge, so neither is clipped by the disc.

        Args:
            mask: The visible pixels (non-zero), trimmed to their bounding box.

        Returns:
            The distance in the mask's pixels, never less than one.
        """
        sample = mask.copy()
        sample.thumbnail((cls.SAMPLE_SIDE_PX, cls.SAMPLE_SIDE_PX), Image.Resampling.BOX)
        step_x, step_y = mask.width / sample.width, mask.height / sample.height
        centre_x, centre_y = mask.width / 2, mask.height / 2
        reach = 1.0
        for index, value in enumerate(sample.getdata()):
            if not value:
                continue
            column, row = index % sample.width, index // sample.width
            reach_x = max(abs(column * step_x - centre_x), abs((column + 1) * step_x - centre_x))
            reach_y = max(abs(row * step_y - centre_y), abs((row + 1) * step_y - centre_y))
            reach = max(reach, math.hypot(reach_x, reach_y))
        return reach

    @staticmethod
    async def _delete_quietly(key: str) -> None:
        """Delete a replaced portrait; a failure only leaves a file the purge of the assistant will catch."""
        try:
            await r2_storage.delete_async(key)
        except Exception:
            logger.warning("A replaced portrait could not be deleted: %s", key, exc_info=True)


ai_assistant_avatar_service = AiAssistantAvatarService()
