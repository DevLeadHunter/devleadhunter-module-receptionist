"""Bench the assistant's model providers on 20 visitor questions (FR / DE / NL / EN).

For each provider with an API key (Mistral, Groq), every question is answered with the assistant's
real system prompt. The script prints, per provider, the latency (mean, p95), the tokens, the
estimated cost per answer and per conversation (4 answers), and how many answers quote a price;
every answer is written to a Markdown file for the quality review.

Usage::

    python scripts/bench_assistant_llm.py                        # the 3 most recent live assistants
    python scripts/bench_assistant_llm.py luma-immo toitures-morel
    python scripts/bench_assistant_llm.py --out bench.md

Nothing is written to the database. Each answer costs a few hundredths of a cent.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import statistics
import sys
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import settings
from core.database import SessionLocal
from enums.ai_assistant_status import AiAssistantStatus
from enums.assistant_llm import LlmProvider
from models.ai_assistant import AiAssistant
from services.ai_assistant.knowledge_builder import ai_assistant_knowledge_builder
from services.ai_assistant.llm_router import estimate_cost_eur
from services.ai_assistant.photo_service import AiAssistantPhotoVision
from services.llm_service import LlmCompletion, llm_service
from services.mistral_service import mistral_service

QUESTIONS: dict[str, tuple[str, ...]] = {
    "fr": (
        "Quels sont vos horaires d'ouverture ?",
        "Vous intervenez le samedi ?",
        "Combien coûte une intervention ?",
        "Je voudrais prendre rendez-vous la semaine prochaine.",
        "Vous faites les devis gratuitement ?",
    ),
    "de": (
        "Wie sind Ihre Öffnungszeiten?",
        "Arbeiten Sie auch am Samstag?",
        "Was kostet ein Einsatz?",
        "Ich möchte nächste Woche einen Termin vereinbaren.",
        "Sind Ihre Kostenvoranschläge kostenlos?",
    ),
    "nl": (
        "Wat zijn jullie openingsuren?",
        "Werken jullie ook op zaterdag?",
        "Hoeveel kost een interventie?",
        "Ik wil volgende week een afspraak maken.",
        "Zijn jullie offertes gratis?",
    ),
    "en": (
        "What are your opening hours?",
        "Do you work on Saturdays?",
        "How much does a call-out cost?",
        "I'd like to book an appointment next week.",
        "Are your quotes free?",
    ),
}
ANSWERS_PER_CONVERSATION = 4


@dataclass(frozen=True)
class Answer:
    """One provider's answer to one question."""

    provider: LlmProvider
    slug: str
    language: str
    question: str
    completion: LlmCompletion | None
    cost_eur: float


def _load_assistants(slugs: list[str]) -> list[AiAssistant]:
    """The assistants to bench: the given slugs, else the 3 most recent live ones."""
    db = SessionLocal()
    try:
        query = db.query(AiAssistant).filter(AiAssistant.deleted_at.is_(None))
        if slugs:
            return query.filter(AiAssistant.slug.in_(slugs)).all()
        live = (AiAssistantStatus.ACTIVE.value, AiAssistantStatus.DELIVERED.value)
        return query.filter(AiAssistant.status.in_(live)).order_by(AiAssistant.created_at.desc()).limit(3).all()
    finally:
        db.close()


async def _ask(provider: LlmProvider, assistant: AiAssistant, language: str, question: str) -> Answer:
    """Ask one provider one question with the assistant's system prompt."""
    system_prompt = ai_assistant_knowledge_builder.render_system_prompt(
        assistant.knowledge_json or {},
        assistant_name=assistant.assistant_name,
        languages=assistant.languages,
        tone=assistant.tone,
    )
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": question}]
    if provider is LlmProvider.MISTRAL:
        completion = await mistral_service.complete(messages, model=settings.mistral_chat_model, max_tokens=500)
    else:
        completion = await llm_service.complete(messages, max_tokens=500, temperature=0.5)
    cost = estimate_cost_eur(provider, completion) if completion else 0.0
    return Answer(provider, assistant.slug, language, question, completion, cost)


def _summary(provider: LlmProvider, answers: list[Answer]) -> str:
    """One line of figures for a provider."""
    served = [answer.completion for answer in answers if answer.completion is not None]
    if not served:
        return f"{provider.value:8} no answer ({len(answers)} failures)"
    latencies = sorted(completion.latency_ms for completion in served)
    p95 = latencies[min(len(latencies) - 1, round(0.95 * (len(latencies) - 1)))]
    mean_cost = statistics.mean(answer.cost_eur for answer in answers if answer.completion is not None)
    priced = sum(1 for completion in served if AiAssistantPhotoVision.PRICE_PATTERN.search(completion.text))
    tokens_in = statistics.mean(completion.prompt_tokens or 0 for completion in served)
    tokens_out = statistics.mean(completion.completion_tokens or 0 for completion in served)
    return (
        f"{provider.value:8} answers {len(served)}/{len(answers)} · latency mean {statistics.mean(latencies):.0f} ms, "
        f"p95 {p95} ms · tokens {tokens_in:.0f} in / {tokens_out:.0f} out · "
        f"{mean_cost * 100:.4f} c€/answer, {mean_cost * ANSWERS_PER_CONVERSATION * 100:.4f} c€/conversation · "
        f"{priced} answer(s) quoting a price"
    )


def _markdown(answers: list[Answer]) -> str:
    """Every answer, grouped by assistant and question, for the quality review."""
    lines = ["# Bench des modèles de l'assistant", ""]
    keys = sorted({(answer.slug, answer.language, answer.question) for answer in answers})
    for slug, language, question in keys:
        lines.append(f"## {slug} · {language} · {question}")
        for answer in answers:
            if (answer.slug, answer.language, answer.question) != (slug, language, question):
                continue
            text = answer.completion.text if answer.completion else "_(pas de réponse)_"
            latency = f"{answer.completion.latency_ms} ms" if answer.completion else "—"
            lines.append(f"- **{answer.provider.value}** ({latency}) : {text}")
        lines.append("")
    return "\n".join(lines)


async def _main(slugs: list[str], out: str) -> int:
    providers = [
        provider
        for provider, ready in (
            (LlmProvider.MISTRAL, mistral_service.is_configured),
            (LlmProvider.GROQ, llm_service.is_configured),
        )
        if ready
    ]
    if not providers:
        print("No provider configured: set MISTRAL_API_KEY and/or GROQ_API_KEY.")
        return 1
    assistants = _load_assistants(slugs)
    if not assistants:
        print("No assistant to bench.")
        return 1
    # Five questions per language, spread over the assistants: 20 questions per provider.
    plan = [
        (assistants[index % len(assistants)], language, question)
        for language, questions in QUESTIONS.items()
        for index, question in enumerate(questions)
    ]
    answers: list[Answer] = []
    for provider in providers:
        for assistant, language, question in plan:
            answers.append(await _ask(provider, assistant, language, question))
    print(f"Assistants: {', '.join(assistant.slug for assistant in assistants)} · {len(plan)} questions")
    for provider in providers:
        print(_summary(provider, [answer for answer in answers if answer.provider is provider]))
    with open(out, "w", encoding="utf-8") as handle:
        handle.write(_markdown(answers))
    print(f"Answers written to {out}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("slugs", nargs="*", help="Assistant slugs (default: the 3 most recent live ones)")
    parser.add_argument("--out", default="bench_assistant_llm.md", help="Markdown file for the answers")
    arguments = parser.parse_args()
    sys.exit(asyncio.run(_main(arguments.slugs, arguments.out)))
