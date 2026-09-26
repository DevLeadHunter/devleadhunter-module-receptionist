"""
What a visitor types as their contact: a phone number the business can dial, or an email it can write to.

The widget and the API apply the same rule, so a request always carries something the business can act on: a
national number has 9 to 11 digits, an international one (« + » or « 00 » first) 10 to 15, and an address has
one « @ » with a domain after it. Anything else (a made-up string of digits, a word) is refused before it reaches
the business.
"""

from __future__ import annotations

import re
from typing import ClassVar

# Prefix, digits and the separators people type between them: spaces, dots, dashes, slashes, parentheses.
_PHONE_CHARS = re.compile(r"^\+?[\d\s.()/-]+$")
_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]{2,}")


class VisitorContact:
    """Tells a phone number from an email address in what a visitor typed, and refuses the rest."""

    MIN_NATIONAL_DIGITS: ClassVar[int] = 9
    MAX_NATIONAL_DIGITS: ClassVar[int] = 11
    MIN_INTERNATIONAL_DIGITS: ClassVar[int] = 10
    MAX_INTERNATIONAL_DIGITS: ClassVar[int] = 15

    @staticmethod
    def is_email(text: str) -> bool:
        """
        Whether a contact reads as an email address.

        Args:
            text: What the visitor typed.

        Returns:
            True for « nom@domaine.tld », spaces around aside.
        """
        return _EMAIL.fullmatch(text.strip()) is not None

    @classmethod
    def is_phone(cls, text: str) -> bool:
        """
        Whether a contact reads as a phone number the business can dial.

        Args:
            text: What the visitor typed.

        Returns:
            True for 9 to 11 digits (national), or 10 to 15 behind « + » or « 00 » (international), with any
            separators between them; False for letters, too few digits or too many.
        """
        cleaned = text.strip()
        if not cleaned or _PHONE_CHARS.fullmatch(cleaned) is None:
            return False
        digits = re.sub(r"\D", "", cleaned)
        if cleaned.startswith("+") or digits.startswith("00"):
            return cls.MIN_INTERNATIONAL_DIGITS <= len(digits) <= cls.MAX_INTERNATIONAL_DIGITS
        return cls.MIN_NATIONAL_DIGITS <= len(digits) <= cls.MAX_NATIONAL_DIGITS

    @classmethod
    def is_reachable(cls, text: str) -> bool:
        """
        Whether the business can reach the visitor with what they typed.

        Args:
            text: What the visitor typed.

        Returns:
            True for a phone number or an email address.
        """
        return cls.is_email(text) or cls.is_phone(text)
