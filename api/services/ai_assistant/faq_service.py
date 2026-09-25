"""
The questions an assistant could not answer, and the FAQ the business writes to answer them.

Both live in ``AiAssistant.knowledge_json`` (``unanswered`` and ``faq``): the prompt reads the FAQ straight from
the knowledge, no table needed. An unanswered question comes from the « §MANQUE: » line of a reply
(``missing_info_marker``); asked again it counts up instead of piling up, and answered in the FAQ it leaves the list.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from models.ai_assistant import AiAssistant
from services.text_normalizer import TextNormalizer

MAX_FAQ_ENTRIES = 50
MAX_UNANSWERED_ENTRIES = 30
MAX_QUESTION_CHARS = 200
MAX_ANSWER_CHARS = 1000


def _utc_now() -> datetime:
    """Current time, naive UTC (patched in tests)."""
    return datetime.now(UTC).replace(tzinfo=None)


@dataclass(frozen=True)
class FaqEntry:
    """A question and the answer the business wrote for it."""

    question: str
    answer: str
    created_at: datetime | None


@dataclass(frozen=True)
class UnansweredQuestion:
    """A question visitors asked that the assistant's knowledge could not answer."""

    question: str
    count: int
    first_seen: datetime | None
    last_seen: datetime | None


class AiAssistantFaqService:
    """Reads and edits the FAQ and the unanswered questions stored in an assistant's knowledge."""

    @staticmethod
    def faq_of(knowledge: dict[str, Any] | None) -> list[FaqEntry]:
        """
        The FAQ stored in an assistant's knowledge.

        Args:
            knowledge: Its ``knowledge_json``.

        Returns:
            The entries in their order; a malformed one is left out, a bad date read as unknown.
        """
        return [
            FaqEntry(question=entry["question"], answer=entry["answer"], created_at=_parse(entry["created_at"]))
            for entry in AiAssistantFaqService._stored_faq(knowledge)
        ]

    @staticmethod
    def unanswered_of(knowledge: dict[str, Any] | None) -> list[UnansweredQuestion]:
        """
        The unanswered questions stored in an assistant's knowledge.

        Args:
            knowledge: Its ``knowledge_json``.

        Returns:
            The questions, first asked first; a malformed one is left out, a bad date read as unknown.
        """
        return [
            UnansweredQuestion(
                question=entry["question"],
                count=entry["count"],
                first_seen=_parse(entry["first_seen"]),
                last_seen=_parse(entry["last_seen"]),
            )
            for entry in AiAssistantFaqService._stored_unanswered(knowledge)
        ]

    def record_unanswered(self, db: Session, assistant: AiAssistant, question: str) -> None:
        """
        File a question the assistant could not answer.

        Args:
            db: Active database session.
            assistant: The assistant.
            question: The visitor's question, as the reply's marker reformulated it.

        Raises:
            ValueError: The question is empty.
        """
        question = _bounded(question, MAX_QUESTION_CHARS)
        if not question:
            raise ValueError("La question est vide.")
        now = _utc_now().isoformat()
        entries = self._stored_unanswered(assistant.knowledge_json)
        key = _key(question)
        for entry in entries:
            if _key(entry["question"]) == key:
                entry["count"] += 1
                entry["last_seen"] = now
                break
        else:
            if len(entries) >= MAX_UNANSWERED_ENTRIES:
                entries.remove(min(entries, key=lambda entry: _parse(entry["last_seen"]) or datetime.min))
            entries.append({"question": question, "count": 1, "first_seen": now, "last_seen": now})
        self._save(db, assistant, unanswered=entries)

    def add_faq(self, db: Session, assistant: AiAssistant, question: str, answer: str) -> None:
        """
        Add a question and its answer to the FAQ; the same question leaves the unanswered list.

        Args:
            db: Active database session.
            assistant: The assistant.
            question: The question, cut to 200 characters.
            answer: The business's answer, cut to 1,000 characters.

        Raises:
            ValueError: An empty question or answer, or a full FAQ.
        """
        entry = _faq_entry(question, answer)
        faq = self._stored_faq(assistant.knowledge_json)
        if len(faq) >= MAX_FAQ_ENTRIES:
            raise ValueError(f"La FAQ est pleine ({MAX_FAQ_ENTRIES} questions au plus).")
        faq.append({**entry, "created_at": _utc_now().isoformat()})
        key = _key(entry["question"])
        unanswered = [
            item for item in self._stored_unanswered(assistant.knowledge_json) if _key(item["question"]) != key
        ]
        self._save(db, assistant, faq=faq, unanswered=unanswered)

    def update_faq(self, db: Session, assistant: AiAssistant, index: int, question: str, answer: str) -> None:
        """
        Rewrite an entry of the FAQ (its creation date stays).

        Args:
            db: Active database session.
            assistant: The assistant.
            index: The entry's position in the FAQ.
            question: The new question, cut to 200 characters.
            answer: The new answer, cut to 1,000 characters.

        Raises:
            IndexError: No entry at that position.
            ValueError: An empty question or answer.
        """
        faq = self._stored_faq(assistant.knowledge_json)
        _check_index(faq, index)
        faq[index] = {**faq[index], **_faq_entry(question, answer)}
        self._save(db, assistant, faq=faq)

    def delete_faq(self, db: Session, assistant: AiAssistant, index: int) -> None:
        """
        Remove an entry of the FAQ.

        Args:
            db: Active database session.
            assistant: The assistant.
            index: The entry's position in the FAQ.

        Raises:
            IndexError: No entry at that position.
        """
        faq = self._stored_faq(assistant.knowledge_json)
        _check_index(faq, index)
        del faq[index]
        self._save(db, assistant, faq=faq)

    def dismiss_unanswered(self, db: Session, assistant: AiAssistant, index: int) -> None:
        """
        Drop an unanswered question without answering it.

        Args:
            db: Active database session.
            assistant: The assistant.
            index: The question's position in the list.

        Raises:
            IndexError: No question at that position.
        """
        unanswered = self._stored_unanswered(assistant.knowledge_json)
        _check_index(unanswered, index)
        del unanswered[index]
        self._save(db, assistant, unanswered=unanswered)

    @staticmethod
    def _stored_faq(knowledge: dict[str, Any] | None) -> list[dict[str, Any]]:
        """The FAQ as stored, copied, the entries without a text question and answer left out."""
        return [
            {
                "question": entry["question"],
                "answer": entry["answer"],
                "created_at": entry.get("created_at") if isinstance(entry.get("created_at"), str) else "",
            }
            for entry in _stored_list(knowledge, "faq")
            if isinstance(entry.get("answer"), str) and entry["answer"].strip()
        ]

    @staticmethod
    def _stored_unanswered(knowledge: dict[str, Any] | None) -> list[dict[str, Any]]:
        """The unanswered questions as stored, copied, a missing count read as one."""
        return [
            {
                "question": entry["question"],
                "count": entry["count"] if isinstance(entry.get("count"), int) and entry["count"] > 0 else 1,
                "first_seen": entry.get("first_seen") if isinstance(entry.get("first_seen"), str) else "",
                "last_seen": entry.get("last_seen") if isinstance(entry.get("last_seen"), str) else "",
            }
            for entry in _stored_list(knowledge, "unanswered")
        ]

    @staticmethod
    def _save(
        db: Session,
        assistant: AiAssistant,
        *,
        faq: list[dict[str, Any]] | None = None,
        unanswered: list[dict[str, Any]] | None = None,
    ) -> None:
        """Store the lists given; a new dict on the JSON column so SQLAlchemy sees the change."""
        knowledge = dict(assistant.knowledge_json or {})
        if faq is not None:
            knowledge["faq"] = faq
        if unanswered is not None:
            knowledge["unanswered"] = unanswered
        assistant.knowledge_json = knowledge
        db.commit()
        db.refresh(assistant)


def _stored_list(knowledge: dict[str, Any] | None, key: str) -> list[dict[str, Any]]:
    """The dict entries of a stored list that carry a text question (anything else is malformed)."""
    raw = (knowledge or {}).get(key)
    return [
        entry
        for entry in (raw if isinstance(raw, list) else [])
        if isinstance(entry, dict) and isinstance(entry.get("question"), str) and entry["question"].strip()
    ]


def _faq_entry(question: str, answer: str) -> dict[str, str]:
    """A validated FAQ entry, trimmed and bounded; empty text is refused."""
    entry = {"question": _bounded(question, MAX_QUESTION_CHARS), "answer": _bounded(answer, MAX_ANSWER_CHARS)}
    if not entry["question"]:
        raise ValueError("La question est vide.")
    if not entry["answer"]:
        raise ValueError("La réponse est vide.")
    return entry


def _bounded(text: str, max_chars: int) -> str:
    """The text trimmed and cut to ``max_chars``."""
    return (text or "").strip()[:max_chars].strip()


def _key(question: str) -> str:
    """Two spellings of one question compare equal: case, accents, spacing and the final « ? » aside."""
    return " ".join(TextNormalizer.fold(question).split()).rstrip(" ?!.")


def _check_index(entries: list[dict[str, Any]], index: int) -> None:
    """Refuse a position outside the list (a negative one included)."""
    if not 0 <= index < len(entries):
        raise IndexError(index)


def _parse(value: str) -> datetime | None:
    """A stored ISO date as naive UTC, or None when it cannot be read."""
    try:
        moment = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    return moment.astimezone(UTC).replace(tzinfo=None) if moment.tzinfo else moment


ai_assistant_faq_service = AiAssistantFaqService()
