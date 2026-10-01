"""
The questions a widget opens with: the business's own, written once by the model and cleaned for a chip, else its
trade's, with the photo and appointment chips its trade gets.

The model is mocked: these tests pin the contract around it (what it is asked, how its answer is cleaned, what stays
when it fails) and the trade read from the Google category, shared with the request volume and the event intake.
"""

import asyncio
from typing import Any

import pytest
from sqlalchemy.orm import Session

import services.ai_assistant.assistant_service as assistant_module
import services.ai_assistant.source_service as source_module
import services.ai_assistant.suggested_questions as suggested_module
from api.v1.routes.ai_assistant_widget import get_public_assistant
from enums.ai_assistant_llm import AiAssistantLlmUsage
from enums.ai_assistant_trade import AiAssistantTrade
from models.ai_assistant import AiAssistant
from models.prospect_db import ProspectDB
from services.ai_assistant.assistant_service import ai_assistant_service
from services.ai_assistant.event_intake import AiAssistantEventIntake
from services.ai_assistant.knowledge_builder import ai_assistant_knowledge_builder
from services.ai_assistant.source_service import AiAssistantSourceService
from services.ai_assistant.suggested_questions import AiAssistantSuggestedQuestions, ai_assistant_suggested_questions
from services.ai_assistant.trade_openings import AiAssistantTradeOpenings
from services.ai_assistant.trade_resolver import AiAssistantTradeResolver
from tests.assistant_fakes import AsyncCallRecorder

_ROOFER_QUESTIONS = [
    "Combien coûte une réparation de toiture\u00a0?",
    "J'ai une fuite au toit, vous pouvez venir\u00a0?",
    "Vous faites le démoussage de toiture\u00a0?",
]
_ROOFER_ENRICHMENT: dict[str, Any] = {
    "logo_url": None,
    "rating": 4.8,
    "reviews_count": 52,
    "description": "Couvreur zingueur à Rennes depuis 1998.",
    "services": ["Réparation de toiture", "Démoussage", "Pose de fenêtres de toit"],
    "opening_hours": [],
    "reviews": [{"author": "Julie", "rating": 5, "text": "Fuite réparée le lendemain de la tempête, merci !"}],
    "social_links": {},
}


def _model_answering(monkeypatch: pytest.MonkeyPatch, answer: dict[str, Any] | None) -> AsyncCallRecorder:
    """The router answering every suggestions call with ``answer``; the calls are recorded."""
    recorder = AsyncCallRecorder(answer, record_args=True)
    monkeypatch.setattr(suggested_module.assistant_llm_router, "complete_json", recorder)
    return recorder


def _model_failing(monkeypatch: pytest.MonkeyPatch) -> None:
    """The router raising on every call, as an outage the router did not absorb would."""

    async def broken(*_: object, **__: object) -> None:
        raise RuntimeError("model down")

    monkeypatch.setattr(suggested_module.assistant_llm_router, "complete_json", broken)


def _assistant(db: Session, *, category: str | None, website: str | None = None) -> AiAssistant:
    prospect = ProspectDB(
        name="Toitures Morel", category=category, source="google", confidence=2, user_id=7, website=website
    )
    db.add(prospect)
    db.commit()
    return ai_assistant_service.create(
        db,
        user_id=7,
        business_name="Toitures Morel",
        prospect_id=prospect.id,
        city="Rennes",
        country="FR",
        enrichment=_ROOFER_ENRICHMENT,
        use_brand_color=False,
    )


@pytest.mark.parametrize(
    ("category", "trade"),
    [
        ("Food truck", AiAssistantTrade.FOOD_TRUCK),
        ("Traiteur", AiAssistantTrade.CATERER),
        ("Salle de réception", AiAssistantTrade.EVENT_VENUE),
        ("Photographe de mariage", AiAssistantTrade.EVENT_VENUE),
        ("Photographe", AiAssistantTrade.EVENT_SERVICE),
        ("Couvreur", AiAssistantTrade.ROOFER),
        ("Charpentier couvreur", AiAssistantTrade.CARPENTER),
        ("Atelier de carrosserie automobile", AiAssistantTrade.BODYWORK),
        ("Garagiste", AiAssistantTrade.GARAGE),
        ("Installateur de portes de garage", AiAssistantTrade.DOORS_AND_WINDOWS),
        ("Plombier chauffagiste", AiAssistantTrade.PLUMBER),
        ("Paysagiste", AiAssistantTrade.LANDSCAPER),
        ("Entretien des espaces verts", AiAssistantTrade.LANDSCAPER),
        ("Restauration rapide", AiAssistantTrade.RESTAURANT),
        ("Crêperie", AiAssistantTrade.RESTAURANT),
        ("Barbier", AiAssistantTrade.HAIRDRESSER),
        ("Institut de formation", AiAssistantTrade.OTHER),
        (None, AiAssistantTrade.OTHER),
    ],
)
def test_the_trade_is_read_from_the_words_of_the_google_category(category: str | None, trade: AiAssistantTrade) -> None:
    assert AiAssistantTradeResolver.of_category(category) is trade


def test_the_event_intake_reads_the_same_trades() -> None:
    assert AiAssistantEventIntake.is_event_trade("Photographe") is True
    assert AiAssistantEventIntake.is_event_trade("Domaine pour séminaires") is True
    assert AiAssistantEventIntake.is_event_trade("Food truck") is False
    assert AiAssistantEventIntake.is_event_trade(None) is False


def test_the_model_questions_are_cleaned_for_a_chip() -> None:
    cleaned = AiAssistantSuggestedQuestions.clean(
        [
            "1. « où êtes-vous cette semaine ? »",
            "OÙ ÊTES-VOUS CETTE SEMAINE ?",
            "Vous livrez ? Et le dimanche ?",
            "Appelez-nous au 06 12 34 56 78 ?",
            "Prix ?",
            "Combien coûte une réparation complète de toiture en ardoise ?",
            42,
            "- Je peux voir le menu.",
            "Vous faites les mariages et les fêtes",
            "Une quatrième question en trop ?",
        ],
        offers_appointment=False,
    )

    assert cleaned == [
        "Où êtes-vous cette semaine\u00a0?",
        "Je peux voir le menu\u00a0?",
        "Vous faites les mariages et les fêtes\u00a0?",
    ]


def test_questions_given_as_one_text_are_split() -> None:
    assert AiAssistantSuggestedQuestions.clean(
        "Où êtes-vous ce soir ? | Je peux voir le menu ?\nVous faites les fêtes ?", offers_appointment=True
    ) == ["Où êtes-vous ce soir\u00a0?", "Je peux voir le menu\u00a0?", "Vous faites les fêtes\u00a0?"]
    assert AiAssistantSuggestedQuestions.clean(None, offers_appointment=True) == []


def test_a_trade_without_appointments_never_offers_a_question_that_opens_the_booking_panel() -> None:
    questions = ["Je peux réserver pour samedi ?", "Vous avez un créneau demain ?", "Je peux voir la carte ?"]

    assert AiAssistantSuggestedQuestions.clean(questions, offers_appointment=False) == ["Je peux voir la carte\u00a0?"]
    assert len(AiAssistantSuggestedQuestions.clean(questions, offers_appointment=True)) == 3


@pytest.mark.parametrize("trade", list(AiAssistantTrade))
def test_every_trade_has_three_questions_that_fit_a_chip(trade: AiAssistantTrade) -> None:
    opening = AiAssistantTradeOpenings.of(trade)

    cleaned = AiAssistantSuggestedQuestions.clean(opening.questions, offers_appointment=opening.offers_appointment)

    assert len(cleaned) == 3
    assert [question.replace("\u00a0?", " ?") for question in cleaned] == list(opening.questions)
    assert all(len(question) <= AiAssistantSuggestedQuestions.QUESTION_MAX_CHARS for question in cleaned)


@pytest.mark.parametrize(
    ("category", "first_question", "offers_photo_quote", "offers_appointment"),
    [
        ("Couvreur", "Combien coûte une réparation de toiture\u00a0?", True, True),
        ("Carrosserie", "Combien coûte la réparation d'une rayure\u00a0?", True, True),
        ("Food truck", "Où êtes-vous cette semaine\u00a0?", False, False),
        ("Salon de coiffure", "Quels sont vos tarifs\u00a0?", False, True),
        ("Institut de formation", "Quels services proposez-vous\u00a0?", True, True),
        (None, "Quels services proposez-vous\u00a0?", True, True),
    ],
)
def test_without_questions_of_its_own_a_business_gets_its_trade_ones(
    category: str | None, first_question: str, offers_photo_quote: bool, offers_appointment: bool
) -> None:
    opening = AiAssistantSuggestedQuestions.opening({"identity": {"business_name": "X"}}, category)

    assert len(opening.questions) == 3
    assert opening.questions[0] == first_question
    assert (opening.offers_photo_quote, opening.offers_appointment) == (offers_photo_quote, offers_appointment)


def test_the_stored_questions_take_the_place_of_the_trade_ones() -> None:
    knowledge = {"suggested_questions": ["Vous êtes où demain midi ?", "La galette du mois, c'est quoi ?"]}

    opening = AiAssistantSuggestedQuestions.opening(knowledge, "Food truck")

    assert opening.questions == ("Vous êtes où demain midi\u00a0?", "La galette du mois, c'est quoi\u00a0?")
    assert (opening.offers_photo_quote, opening.offers_appointment) == (False, False)


def test_the_model_is_asked_once_on_the_business_knowledge(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = _model_answering(
        monkeypatch,
        {
            "questions": [
                "Vous faites le démoussage ?",
                "Combien coûte une réparation de toiture ?",
                "Vous intervenez après une tempête ?",
            ]
        },
    )
    knowledge = ai_assistant_knowledge_builder.build_knowledge(
        business_name="Toitures Morel", city="Rennes", enrichment=_ROOFER_ENRICHMENT
    )

    questions = asyncio.run(ai_assistant_suggested_questions.generate(knowledge, category="Couvreur", eu_only=True))

    assert questions == [
        "Vous faites le démoussage\u00a0?",
        "Combien coûte une réparation de toiture\u00a0?",
        "Vous intervenez après une tempête\u00a0?",
    ]
    assert len(recorder.calls) == 1
    call = recorder.calls[0]
    system, user = call["args"][1]
    assert call["args"][0] is AiAssistantLlmUsage.SUGGESTIONS
    assert call["eu_only"] is True
    assert "45 caractères au plus" in system["content"] and "DONNÉES" in system["content"]
    assert user["content"].startswith("Métier (catégorie Google) : Couvreur\nENTREPRISE : Toitures Morel.")
    assert "Démoussage" in user["content"] and "Fuite réparée le lendemain" in user["content"]


@pytest.mark.parametrize(
    "answer",
    [None, {"questions": "rien"}, {"questions": ["Une seule question utilisable ?", "Prix ?"]}, {"other": []}],
)
def test_too_few_usable_questions_is_a_failed_generation(
    monkeypatch: pytest.MonkeyPatch, answer: dict[str, Any] | None
) -> None:
    _model_answering(monkeypatch, answer)

    assert asyncio.run(ai_assistant_suggested_questions.generate({}, category="Couvreur", eu_only=False)) == []


def test_a_model_error_never_stops_the_generation(monkeypatch: pytest.MonkeyPatch) -> None:
    _model_failing(monkeypatch)

    assert asyncio.run(ai_assistant_suggested_questions.generate({}, category="Couvreur", eu_only=False)) == []


def test_new_questions_are_stored_and_the_old_ones_stay_when_the_model_fails(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    assistant = _assistant(db, category="Couvreur")
    _model_answering(monkeypatch, {"questions": _ROOFER_QUESTIONS})
    stored = asyncio.run(ai_assistant_suggested_questions.refresh(db, assistant, category="Couvreur"))
    _model_failing(monkeypatch)
    kept = asyncio.run(ai_assistant_suggested_questions.refresh(db, assistant, category="Couvreur"))

    assert (stored, kept) == (True, False)
    assert assistant.knowledge_json["suggested_questions"] == _ROOFER_QUESTIONS


def test_a_regeneration_keeps_the_questions_until_new_ones_are_written(db: Session) -> None:
    assistant = _assistant(db, category="Couvreur")
    assistant.knowledge_json = {**assistant.knowledge_json, "suggested_questions": _ROOFER_QUESTIONS}
    db.commit()
    prospect = db.get(ProspectDB, assistant.prospect_id)

    ai_assistant_service.regenerate(db, assistant=assistant, prospect=prospect, enrichment=_ROOFER_ENRICHMENT)

    assert assistant.knowledge_json["suggested_questions"] == _ROOFER_QUESTIONS


def _enriched_without_a_crawl(monkeypatch: pytest.MonkeyPatch) -> None:
    """The prospect's enrichment served without scraping; it has no website to read."""

    async def ensure_enriched(*_: object) -> object:
        return object()

    monkeypatch.setattr(assistant_module.enrichment_service, "ensure_enriched", ensure_enriched)
    monkeypatch.setattr(assistant_module.enrichment_service, "to_dict", lambda _record: _ROOFER_ENRICHMENT)


def test_a_generated_receptionist_opens_with_its_own_questions(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    _enriched_without_a_crawl(monkeypatch)
    _model_answering(monkeypatch, {"questions": _ROOFER_QUESTIONS})
    prospect = ProspectDB(name="Toitures Morel", category="Couvreur", source="google", confidence=2, user_id=7)
    db.add(prospect)
    db.commit()

    assistant = asyncio.run(ai_assistant_service.create_for_prospect(db, user_id=7, prospect=prospect))
    config = asyncio.run(get_public_assistant(assistant.slug, db))

    assert config.suggested_questions == _ROOFER_QUESTIONS
    assert (config.offers_photo_quote, config.offers_appointment) == (True, True)


def test_a_model_error_never_stops_a_food_truck_receptionist_from_being_generated(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enriched_without_a_crawl(monkeypatch)
    _model_failing(monkeypatch)
    prospect = ProspectDB(name="Le Camion Gourmand", category="Food truck", source="google", confidence=2, user_id=7)
    db.add(prospect)
    db.commit()

    assistant = asyncio.run(ai_assistant_service.create_for_prospect(db, user_id=7, prospect=prospect))
    config = asyncio.run(get_public_assistant(assistant.slug, db))

    assert assistant.status == "active" and "suggested_questions" not in assistant.knowledge_json
    assert config.suggested_questions == [
        "Où êtes-vous cette semaine\u00a0?",
        "Je peux voir le menu\u00a0?",
        "Vous faites les mariages et les fêtes\u00a0?",
    ]
    assert (config.offers_photo_quote, config.offers_appointment) == (False, False)


def test_a_website_read_on_demand_or_with_changed_pages_writes_the_questions_again(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    assistant = _assistant(db, category="Couvreur", website="https://toitures-morel.fr")
    page = {"url": "https://toitures-morel.fr/", "title": "Accueil", "text": "Couverture, zinguerie, démoussage."}
    crawls: list[dict[str, Any] | None] = [
        {"url": "https://toitures-morel.fr/", "pages": [page]},
        {"url": "https://toitures-morel.fr/", "pages": [page]},
        {"url": "https://toitures-morel.fr/", "pages": [page]},
        None,
    ]

    async def crawl(_prospect: ProspectDB) -> dict[str, Any] | None:
        return crawls.pop(0)

    monkeypatch.setattr(source_module.ai_assistant_service, "crawl_prospect_website", crawl)
    refreshes = AsyncCallRecorder(True)
    monkeypatch.setattr(source_module.ai_assistant_suggested_questions, "refresh", refreshes)
    service = AiAssistantSourceService()

    asyncio.run(service.refresh_website(db, assistant))  # a weekly read finding a new page
    asyncio.run(service.refresh_website(db, assistant))  # a weekly read with nothing new
    asyncio.run(service.refresh_website(db, assistant, force=True))  # « Mettre à jour », nothing new
    asyncio.run(service.refresh_website(db, assistant, force=True))  # the site down

    assert [call["category"] for call in refreshes.calls] == ["Couvreur", "Couvreur"]
