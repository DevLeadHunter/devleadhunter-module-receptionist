"""Rewrite the 5 Assistant IA cold-email templates around the request left unanswered.

« Vos clients écrivent le soir, personne ne répond », « Une photo, un devis demandé », « Vos clients,
dans leur langue », the follow-up and « le prix cash ». The « demandes captées » template becomes
« devis par photo », renamed in place so the campaigns using it keep it (archived instead when a
« devis par photo » row already exists). The admin's seeded rows get the library's subject, body,
category and sort order; no other template is touched. Idempotent.
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

_RENAMED: dict[str, str] = {"Assistant IA - demandes captées": "Assistant IA - devis par photo"}


def _digest(subject: str, body_html: str) -> str:
    """SHA-256 of a template's subject and body, to tell a seeded text from a hand-edited one."""
    return hashlib.sha256(f"{subject}\n{body_html}".encode()).hexdigest()


# The texts as the seeder wrote them before this rewrite: only rows still carrying one of them are rewritten.
_PREVIOUSLY_SEEDED: dict[str, str] = {
    "Assistant IA - réponses 24/7": "41e0811d9562a98315b2db190249bb41cfe77d16e6fd6c3818d150cbafdd48a1",
    "Assistant IA - devis par photo": "2a8c681aeeb7896d28f6959587b90ee5c414a47f3e42d483b459d6a87583c199",
    "Assistant IA - multilingue": "d5d463ade7c99e17a5d981fcbef8ff925da3d1ed2c1e5509758d4232fcc1f9f4",
    "Assistant IA - relance": "6928416192885f6c67d876b1047a2b44a17a59e12c51ff7e98d68872475e4070",
    "Assistant IA - le prix cash": "18e739a88e9256de7ccab1653e1e973b0799234df1506af8b7ca66f5b1856350",
}
# Per template: the previous seeded text and the new one (a rerun finds the new text and rewrites it harmlessly).
_KNOWN_DIGESTS: dict[str, frozenset[str]] = {
    str(template["name"]): frozenset(
        digest
        for digest in (
            _PREVIOUSLY_SEEDED.get(str(template["name"])),
            _digest(str(template["subject"]), str(template["body_html"])),
        )
        if digest
    )
    for template in EMAIL_TEMPLATE_LIBRARY
    if str(template["name"]).startswith("Assistant IA")
}
_ASSISTANT_NAMES: frozenset[str] = frozenset(
    {
        "Assistant IA - réponses 24/7",
        "Assistant IA - devis par photo",
        "Assistant IA - multilingue",
        "Assistant IA - relance",
        "Assistant IA - le prix cash",
    }
)


def run_migration() -> None:
    """Rename, then rewrite the admin's Assistant IA templates in place."""
    with engine.connect() as conn:
        admin_id = conn.execute(
            text("SELECT id FROM users WHERE email = :email"), {"email": settings.admin_email}
        ).scalar()
        if admin_id is None:
            print(f"[SKIP] Admin user {settings.admin_email!r} not found — the seeder will add the templates")
            return

        for old_name, new_name in _RENAMED.items():
            taken = conn.execute(
                text("SELECT COUNT(*) FROM email_templates WHERE user_id = :user_id AND name = :name"),
                {"user_id": admin_id, "name": new_name},
            ).scalar()
            if taken:
                # The seeder got there first: keep its row, retire the old copy.
                conn.execute(
                    text("UPDATE email_templates SET is_active = 0 WHERE user_id = :user_id AND name = :old"),
                    {"user_id": admin_id, "old": old_name},
                )
            else:
                conn.execute(
                    text("UPDATE email_templates SET name = :new WHERE user_id = :user_id AND name = :old"),
                    {"user_id": admin_id, "new": new_name, "old": old_name},
                )

        updated = 0
        for template in EMAIL_TEMPLATE_LIBRARY:
            name = str(template["name"])
            if name not in _ASSISTANT_NAMES:
                continue
            subject = str(template["subject"])
            body_html = str(template["body_html"])
            current = conn.execute(
                text("SELECT subject, body_html FROM email_templates WHERE user_id = :user_id AND name = :name"),
                {"user_id": admin_id, "name": name},
            ).first()
            if current is not None and _digest(str(current[0]), str(current[1])) not in _KNOWN_DIGESTS[name]:
                # Edited by hand since it was seeded: the owner's wording wins over the library's.
                print(f"[SKIP] {name!r} was edited by hand, left as is")
                continue
            result = conn.execute(
                text(
                    """
                    UPDATE email_templates
                    SET subject = :subject, body_html = :body_html, variables = :variables, category = :category,
                        sort_order = :sort_order, is_active = 1
                    WHERE user_id = :user_id AND name = :name
                    """
                ),
                {
                    "user_id": admin_id,
                    "name": name,
                    "subject": subject,
                    "body_html": body_html,
                    "variables": json.dumps(_extract_variables(subject, body_html)),
                    "category": str(template["category"]),
                    "sort_order": int(template["sort_order"]),  # type: ignore[arg-type]
                },
            )
            updated += result.rowcount or 0

        conn.commit()
        print(f"[OK] Rewrote {updated} Assistant IA email templates for admin {admin_id}.")


if __name__ == "__main__":
    run_migration()
