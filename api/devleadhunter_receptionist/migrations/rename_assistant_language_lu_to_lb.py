"""Store Luxembourgish as « lb » (BCP 47) instead of « lu », which is Luba-Katanga.

The assistants' offered languages (a JSON list) and the language shares of the monthly reports (JSON snapshots) are
rewritten in Python, the other codes kept in their order; the language of the conversations, requests and legacy
leads is updated in SQL. The API still reads « lu » as « lb » (a widget left open in a browser), so the rewrite can
run before or after the new code. Re-runnable.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from sqlalchemy import inspect, text

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.database import engine

_LEGACY_CODE = "lu"
_CURRENT_CODE = "lb"
_TABLES_WITH_A_LANGUAGE = ("ai_assistant_conversations", "ai_assistant_requests", "ai_assistant_leads")


def _renamed(languages: list[object]) -> list[object]:
    """The offered languages with « lu » written « lb », each code once, in their order."""
    renamed: list[object] = []
    for code in languages:
        current = _CURRENT_CODE if code == _LEGACY_CODE else code
        if current not in renamed:
            renamed.append(current)
    return renamed


def _renamed_shares(stats: dict[str, object]) -> dict[str, object] | None:
    """A report's statistics with its « lu » language share written « lb », or None when it has none."""
    shares = stats.get("languages")
    if not isinstance(shares, list) or not any(
        isinstance(share, dict) and share.get("code") == _LEGACY_CODE for share in shares
    ):
        return None
    renamed = [
        {**share, "code": _CURRENT_CODE} if isinstance(share, dict) and share.get("code") == _LEGACY_CODE else share
        for share in shares
    ]
    return {**stats, "languages": renamed}


def run_migration() -> None:
    """Rewrite « lu » as « lb » wherever an assistant language is stored."""
    tables = set(inspect(engine).get_table_names())
    with engine.connect() as conn:
        if "ai_assistants" in tables:
            rows = conn.execute(text("SELECT id, languages FROM ai_assistants WHERE languages IS NOT NULL")).all()
            for assistant_id, stored in rows:
                languages = json.loads(stored) if isinstance(stored, str) else stored
                if not isinstance(languages, list) or _LEGACY_CODE not in languages:
                    continue
                conn.execute(
                    text("UPDATE ai_assistants SET languages = :languages WHERE id = :id"),
                    {"languages": json.dumps(_renamed(languages)), "id": assistant_id},
                )
                print(f"[OK] Assistant {assistant_id}: Luxembourgish now stored as « lb »")
        if "ai_assistant_reports" in tables:
            rows = conn.execute(
                text("SELECT id, stats_json FROM ai_assistant_reports WHERE stats_json IS NOT NULL")
            ).all()
            for report_id, stored in rows:
                stats = json.loads(stored) if isinstance(stored, str) else stored
                renamed_stats = _renamed_shares(stats) if isinstance(stats, dict) else None
                if renamed_stats is not None:
                    conn.execute(
                        text("UPDATE ai_assistant_reports SET stats_json = :stats WHERE id = :id"),
                        {"stats": json.dumps(renamed_stats), "id": report_id},
                    )
        for table in _TABLES_WITH_A_LANGUAGE:
            if table in tables:
                conn.execute(
                    text(f"UPDATE {table} SET language = :current WHERE language = :legacy"),
                    {"current": _CURRENT_CODE, "legacy": _LEGACY_CODE},
                )
        conn.commit()


if __name__ == "__main__":
    run_migration()
