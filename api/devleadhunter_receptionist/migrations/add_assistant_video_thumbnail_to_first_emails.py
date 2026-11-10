"""Add the receptionist's video thumbnail to the three Assistant IA first emails.

« Vos clients écrivent le soir, personne ne répond », « Une photo, un devis demandé » and « Vos clients,
dans leur langue » carry ``{vignette_video_assistant}`` after their demo link, as the site's first emails
carry ``{vignette_video}``: the thumbnail shows once the receptionist's video is generated, and until then
the variable stays empty so the email reads as before. Only the admin's rows still holding the seeded
text are rewritten; a template edited by hand is left as is. Idempotent.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from sqlalchemy import text

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.config import settings
from core.database import engine
from seeders.email_template_seeder import EMAIL_TEMPLATE_LIBRARY, _extract_variables

# The texts as the seeder wrote them before the thumbnail: only rows still carrying one of them are rewritten.
_PREVIOUSLY_SEEDED: dict[str, str] = {
    "Assistant IA - réponses 24/7": "16bc2bef46b253a6d2604f47dccf84eb57a6432b7a0b3efe84018d8b56f2fec8",
    "Assistant IA - devis par photo": "5f225e21d14eafeca1c26de7a383b51dbf8b77e10df9dda0415201f35fcd3258",
    "Assistant IA - multilingue": "2cdecf594a8832f1592f6c1d465af33bd9b2203f3523dde3afb5244ad448fa4f",
}


def _digest(subject: str, body_html: str) -> str:
    """SHA-256 of a template's subject and body, to tell a seeded text from a hand-edited one."""
    return hashlib.sha256(f"{subject}\n{body_html}".encode()).hexdigest()


def run_migration() -> None:
    """Rewrite the admin's untouched Assistant IA first emails with the video thumbnail."""
    library = {str(template["name"]): template for template in EMAIL_TEMPLATE_LIBRARY}
    with engine.connect() as conn:
        admin_id = conn.execute(
            text("SELECT id FROM users WHERE email = :email"), {"email": settings.admin_email}
        ).scalar()
        if admin_id is None:
            print(f"[SKIP] Admin user {settings.admin_email!r} not found, the seeder will add the templates")
            return

        updated = 0
        for name, previous_digest in _PREVIOUSLY_SEEDED.items():
            subject = str(library[name]["subject"])
            body_html = str(library[name]["body_html"])
            current = conn.execute(
                text("SELECT subject, body_html FROM email_templates WHERE user_id = :user_id AND name = :name"),
                {"user_id": admin_id, "name": name},
            ).first()
            if current is None:
                continue
            if _digest(str(current[0]), str(current[1])) not in (previous_digest, _digest(subject, body_html)):
                # Edited by hand since it was seeded: the owner's wording wins over the library's.
                print(f"[SKIP] {name!r} was edited by hand, left as is")
                continue
            result = conn.execute(
                text(
                    """
                    UPDATE email_templates
                    SET body_html = :body_html, variables = :variables
                    WHERE user_id = :user_id AND name = :name
                    """
                ),
                {
                    "user_id": admin_id,
                    "name": name,
                    "body_html": body_html,
                    "variables": json.dumps(_extract_variables(subject, body_html)),
                },
            )
            updated += result.rowcount or 0

        conn.commit()
        print(f"[OK] Added the video thumbnail to {updated} Assistant IA first emails for admin {admin_id}.")


if __name__ == "__main__":
    run_migration()
