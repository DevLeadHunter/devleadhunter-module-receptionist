"""Point the assistant « prix cash » templates at ``{prix_assistant}`` instead of ``{prix}``.

The franc email + SMS models were seeded with ``{prix}`` (the *website* price, 500 €), which is wrong
for a 29 €/mois subscription. This swaps the token to ``{prix_assistant}/mois`` on the already-seeded
email row. Idempotent: it only touches that one template and only when ``{prix}`` is still present, so
a re-run — or a row Léo already edited — is a no-op. The SMS model lives in code and needs no migration.
"""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import text

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.database import engine


def run_migration() -> None:
    with engine.connect() as conn:
        conn.execute(
            text(
                """
                UPDATE email_templates
                SET body_html = REPLACE(body_html, '{prix}', '{prix_assistant}/mois')
                WHERE name = 'Assistant IA - le prix cash'
                  AND body_html LIKE '%{prix}%'
                """
            )
        )
        conn.commit()


if __name__ == "__main__":
    run_migration()
    print("assistant franc email template price variable fixed.")
