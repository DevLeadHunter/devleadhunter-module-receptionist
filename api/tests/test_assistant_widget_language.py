"""
Luxembourgish is « lb » (BCP 47) for the widget, the API and the stored data; the legacy « lu » is read as « lb »
wherever it still arrives (a widget left open, an old page), and the migration rewrites what is stored.
"""

import json

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

import migrations.rename_assistant_language_lu_to_lb as rename_migration
from enums.ai_assistant_widget_language import AiAssistantWidgetLanguage
from models.ai_assistant import AiAssistant
from models.ai_assistant_conversation import AiAssistantConversation
from models.ai_assistant_report import AiAssistantReport
from models.ai_assistant_request import AiAssistantRequest
from schemas.ai_assistant import AiAssistantChatRequest, AiAssistantLeadRequest, AiAssistantUpdateRequest
from services.ai_assistant.config_builder import ai_assistant_config_builder
from services.ai_assistant.knowledge_builder import LANGUAGE_NAMES


def test_the_widget_speaks_five_languages_with_luxembourgish_as_lb() -> None:
    assert [language.value for language in AiAssistantWidgetLanguage] == ["fr", "nl", "en", "de", "lb"]
    assert LANGUAGE_NAMES["lb"] == "luxembourgeois" and "lu" not in LANGUAGE_NAMES
    assert ai_assistant_config_builder.build_config(country="LU")["languages"] == ["fr", "de", "en", "lb"]


def test_a_code_is_read_whatever_its_case_region_or_legacy_spelling() -> None:
    read = AiAssistantWidgetLanguage.from_code

    assert [read(code) for code in ("lb", "LB", "lb-LU", "lb_LU", "lu", " fr ", "de-CH")] == [
        AiAssistantWidgetLanguage.LB,
        AiAssistantWidgetLanguage.LB,
        AiAssistantWidgetLanguage.LB,
        AiAssistantWidgetLanguage.LB,
        AiAssistantWidgetLanguage.LB,
        AiAssistantWidgetLanguage.FR,
        AiAssistantWidgetLanguage.DE,
    ]
    assert [read(code) for code in ("it", "", None)] == [None, None, None]
    assert AiAssistantWidgetLanguage("lu") is AiAssistantWidgetLanguage.LB
    assert AiAssistantWidgetLanguage.normalize_codes(["fr", "lu", "lb", "it", "DE"]) == ["fr", "lb", "de"]


def test_the_api_takes_lu_as_lb_and_keeps_the_widget_languages_only() -> None:
    assert AiAssistantChatRequest(language="lu").language == "lb"
    assert AiAssistantChatRequest(language="it").language == "it"
    assert AiAssistantChatRequest().language is None
    assert AiAssistantLeadRequest(name="Léa", contact="0612345678", language="LU").language == "lb"
    # The dashboard offers the widget's languages only: a legacy code sent back by an old page is dropped.
    assert AiAssistantUpdateRequest(languages=["fr", "lu", "it", "fr"]).languages == ["fr", "lb"]
    assert AiAssistantUpdateRequest().languages is None


@pytest.fixture
def migrated_engine(engine: Engine, monkeypatch: pytest.MonkeyPatch) -> Engine:
    monkeypatch.setattr(rename_migration, "engine", engine)
    return engine


def test_the_migration_rewrites_every_stored_lu_once(db: Session, migrated_engine: Engine) -> None:
    luxembourg = AiAssistant(user_id=1, slug="luma", business_name="LUMA", languages=["fr", "lu", "de", "lb"])
    france = AiAssistant(user_id=1, slug="morel", business_name="Morel", languages=["fr", "en"])
    db.add_all([luxembourg, france])
    db.flush()
    db.add(
        AiAssistantConversation(user_id=1, assistant_id=luxembourg.id, session_id="s1", language="lu", message_count=0)
    )
    db.add(
        AiAssistantRequest(
            user_id=1, assistant_id=luxembourg.id, name="Anna", contact="621123456", language="lu", type="other"
        )
    )
    db.add(
        AiAssistantReport(
            user_id=1,
            assistant_id=luxembourg.id,
            month="2026-08",
            stats_json={
                "conversations": 4,
                "languages": [{"code": "lu", "share_pct": 75}, {"code": "fr", "share_pct": 25}],
            },
        )
    )
    db.commit()

    rename_migration.run_migration()
    rename_migration.run_migration()

    db.expire_all()
    assert db.get(AiAssistant, luxembourg.id).languages == ["fr", "lb", "de"]
    assert db.get(AiAssistant, france.id).languages == ["fr", "en"]
    assert db.query(AiAssistantConversation).one().language == "lb"
    assert db.query(AiAssistantRequest).one().language == "lb"
    report = db.query(AiAssistantReport).one()
    assert report.stats_json["languages"] == [{"code": "lb", "share_pct": 75}, {"code": "fr", "share_pct": 25}]
    assert report.stats_json["conversations"] == 4
    with migrated_engine.connect() as conn:
        stored = conn.execute(
            text("SELECT languages FROM ai_assistants WHERE id = :id"), {"id": luxembourg.id}
        ).scalar()
    assert json.loads(stored) == ["fr", "lb", "de"]
