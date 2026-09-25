"""
The « §SUITE: » line an assistant's reply ends with: the questions the widget offers as chips under the reply,
held back from the stream, parsed from a whole reply, asked for by the system prompt.
"""

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import pytest

import services.ai_assistant.chat_service as chat_module
from services.ai_assistant.chat_service import ChatAnswer, ChatDelta, ai_assistant_chat_service
from services.ai_assistant.follow_up_marker import (
    FollowUpMarker,
    FollowUpMarkerStream,
    may_still_be_follow_up_marker,
    parse_follow_ups,
)
from services.ai_assistant.knowledge_builder import ai_assistant_knowledge_builder

_KB = {"identity": {"business_name": "Garage Morel", "city": "Rennes"}}
_MESSAGES = [{"role": "user", "content": "Vous faites la carrosserie ?"}]


def _deltas(*chunks: str):
    async def stream(*_args: Any, **_kwargs: Any) -> AsyncIterator[str]:
        for chunk in chunks:
            yield chunk

    return stream


def _answer_stream(**kwargs: Any) -> list[ChatDelta]:
    async def run() -> list[ChatDelta]:
        return [delta async for delta in ai_assistant_chat_service.answer_stream(**kwargs)]

    return asyncio.run(run())


def test_a_whole_reply_is_split_from_its_trailing_marker() -> None:
    reply = "Oui, nous faisons la carrosserie.\n\n§SUITE: Vos horaires ? | Un devis gratuit ? | Prendre rendez-vous"

    assert FollowUpMarker.split(reply) == (
        "Oui, nous faisons la carrosserie.",
        ("Vos horaires ?", "Un devis gratuit ?", "Prendre rendez-vous"),
    )
    # Tolerant of the typography: bold, a missing « § », a French space before the colon, other separators.
    assert FollowUpMarker.split("Oui.\n**§SUITE : A ? ; B ?**") == ("Oui.", ("A ?", "B ?"))
    assert FollowUpMarker.split("Oui.\nSUITE: A ? • B ? / C ? | D ?") == ("Oui.", ("A ?", "B ?", "C ?"))
    # Without a marker, the reply is untouched and there are no questions.
    assert FollowUpMarker.split("Oui, le samedi.\n- Matin\n- Après-midi") == (
        "Oui, le samedi.\n- Matin\n- Après-midi",
        (),
    )
    assert FollowUpMarker.split("§SUITE:") == ("", ())


def test_the_questions_are_distinct_trimmed_and_bounded() -> None:
    assert parse_follow_ups(" « Vos horaires ? » | vos horaires ? | *Un devis ?* | Encore | Trop") == (
        "Vos horaires ?",
        "Un devis ?",
        "Encore",
    )
    assert parse_follow_ups("x" * 100)[0] == "x" * 80
    assert may_still_be_follow_up_marker("§SU") and may_still_be_follow_up_marker("**suite")
    assert not may_still_be_follow_up_marker("Nous ") and not may_still_be_follow_up_marker("Suivant")


def test_the_stream_holds_only_the_lines_that_may_be_the_marker() -> None:
    """A plain line streams at once; the blank lines and the marker at the end never reach the visitor."""
    stream = FollowUpMarkerStream()

    assert stream.feed("Nous ouvrons le ") == "Nous ouvrons le "
    assert stream.feed("samedi.\n") == "samedi.\n"
    assert stream.feed("\n§SU") == ""
    assert stream.feed("ITE: Vos horaires ? | Un devis ?") == ""
    assert stream.finish() == ""
    assert stream.reply == "Nous ouvrons le samedi."
    assert stream.follow_ups == ("Vos horaires ?", "Un devis ?")


def test_the_stream_releases_a_held_line_once_it_cannot_be_the_marker() -> None:
    """« Sur devis. » shares its first letters with the marker: held for two characters, then released whole."""
    stream = FollowUpMarkerStream()

    assert stream.feed("Bonjour.\n\nSu") == "Bonjour.\n"
    assert stream.feed("r devis, ") == "\nSur devis, "
    assert stream.feed("le samedi.") == "le samedi."
    assert stream.finish() == ""
    assert stream.reply == "Bonjour.\n\nSur devis, le samedi."
    assert stream.follow_ups == ()


def test_a_marker_glued_to_the_last_sentence_is_held_from_its_sign() -> None:
    """The model forgot the line break: the text before « § » streams, the marker never shows."""
    stream = FollowUpMarkerStream()

    assert stream.feed("Voulez-vous un devis ? ") == "Voulez-vous un devis ? "
    assert stream.feed("§SU") == ""
    assert stream.feed("ITE: Vos horaires ? | Vous vous déplacez ?") == ""
    assert stream.finish() == ""
    assert stream.reply == "Voulez-vous un devis ?"
    assert stream.follow_ups == ("Vos horaires ?", "Vous vous déplacez ?")
    # In one piece, and a « § » that opens something else is released once it cannot be the marker.
    assert FollowUpMarker.split("Un devis ? §SUITE: A ? | B ?") == ("Un devis ?", ("A ?", "B ?"))
    assert FollowUpMarker.split("Voir le § 3 du contrat.") == ("Voir le § 3 du contrat.", ())
    assert FollowUpMarker.split("La suite : un devis sous 48 h.") == ("La suite : un devis sous 48 h.", ())


def test_the_stream_drops_trailing_blank_lines_and_keeps_a_marker_free_reply() -> None:
    stream = FollowUpMarkerStream()

    assert stream.feed("Oui.\n\n") == "Oui.\n"
    assert stream.finish() == ""
    assert stream.reply == "Oui."
    assert stream.follow_ups == ()


@pytest.mark.asyncio
async def test_the_answer_carries_the_follow_ups_after_both_markers(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_chat(_usage: Any, _messages: Any, **_kwargs: Any) -> str:
        return "§MANQUE: Livraison ?\n\nJe note votre question.\n\n§SUITE: Vos horaires ? | Prendre rendez-vous"

    monkeypatch.setattr(chat_module.assistant_llm_router, "chat", fake_chat)

    answer = await ai_assistant_chat_service.answer(knowledge=_KB, assistant_name="Sofia", history=_MESSAGES)

    assert answer == ChatAnswer(
        reply="Je note votre question.",
        unanswered_question="Livraison ?",
        follow_ups=("Vos horaires ?", "Prendre rendez-vous"),
    )


def test_the_streamed_answer_never_shows_the_marker_and_ends_with_the_follow_ups(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        chat_module.assistant_llm_router,
        "chat_stream",
        _deltas("Oui, la carrosserie ", "aussi.\n", "\n§SUITE: Un devis ?", " | Vos horaires ?"),
    )

    deltas = _answer_stream(knowledge=_KB, assistant_name="Sofia", history=_MESSAGES)

    assert deltas == [
        ChatDelta(text="Oui, la carrosserie "),
        ChatDelta(text="aussi.\n"),
        ChatDelta(final=ChatAnswer(reply="Oui, la carrosserie aussi.", follow_ups=("Un devis ?", "Vos horaires ?"))),
    ]


def test_the_system_prompt_asks_for_the_trailing_line_and_for_lists_when_enumerating() -> None:
    prompt = ai_assistant_knowledge_builder.render_system_prompt(_KB, assistant_name="Sofia")

    assert "Termine TOUJOURS ta réponse par une dernière ligne exacte « §SUITE: " in prompt
    # The chips are the visitor's next questions to the business, never the business's questions to the visitor.
    assert "Jamais une question que l'entreprise poserait au client" in prompt
    assert "UNE ligne par élément commençant par « - »" in prompt
    assert "liste à puces" not in prompt
