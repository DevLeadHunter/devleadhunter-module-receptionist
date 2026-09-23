"""Rewrite the 5 Assistant IA cold-email templates to the franc, price-direct copy.

The seeder is append-only and the earlier library reseed already ran, so this
migration updates the admin's already-seeded Assistant IA rows in place (subject,
body, variables) from ``EMAIL_TEMPLATE_LIBRARY``. Scoped to the 5 assistant
templates by name, so no other template is touched or archived. Idempotent.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from sqlalchemy import text

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.config import settings
from core.database import engine
from seeders.email_template_seeder import EMAIL_TEMPLATE_LIBRARY

_VARIABLE_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")

_ASSISTANT_NAMES = {
    "Assistant IA - réponses 24/7",
    "Assistant IA - multilingue",
    "Assistant IA - demandes captées",
    "Assistant IA - relance",
    "Assistant IA - le prix cash",
}


def _variables_json(subject: str, body_html: str) -> str:
    """Serialise the sorted, unique {variable} names of a template, like the seeder does."""
    return json.dumps(sorted(set(_VARIABLE_RE.findall(f"{subject} {body_html}"))))


def run_migration() -> None:
    with engine.connect() as conn:
        admin_id = conn.execute(
            text("SELECT id FROM users WHERE email = :email"), {"email": settings.admin_email}
        ).scalar()
        if admin_id is None:
            print(f"[SKIP] Admin user {settings.admin_email!r} not found — seeder will do the initial seed")
            return

        updated = 0
        for template in EMAIL_TEMPLATE_LIBRARY:
            name = str(template["name"])
            if name not in _ASSISTANT_NAMES:
                continue
            subject = str(template["subject"])
            body_html = str(template["body_html"])
            result = conn.execute(
                text(
                    """
                    UPDATE email_templates
                    SET subject = :subject, body_html = :body_html, variables = :variables, is_active = 1
                    WHERE user_id = :user_id AND name = :name
                    """
                ),
                {
                    "user_id": admin_id,
                    "name": name,
                    "subject": subject,
                    "body_html": body_html,
                    "variables": _variables_json(subject, body_html),
                },
            )
            updated += result.rowcount or 0

        conn.commit()
        print(f"[OK] Rewrote {updated} Assistant IA email templates for admin {admin_id}.")


if __name__ == "__main__":
    run_migration()
