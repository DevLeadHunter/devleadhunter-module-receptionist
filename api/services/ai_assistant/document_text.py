"""
The text of a document a business gives its assistant (price list, terms, brochure, FAQ), read from a PDF.

The text is extracted with pypdf, cleaned (hyphenated line breaks joined, blank runs collapsed, control
characters dropped) and bounded: the assistant reads it as data, never as instructions. A scanned PDF (no
text layer) or a password-protected one is refused with a sentence the operator can act on.

A PDF can be built to make its reading endless (a small file inflating into megabytes of drawing instructions),
so it is read in a separate process (``python -m services.ai_assistant.document_text``: the PDF on stdin, the text
as JSON on stdout), one at a time, killed after ``TIMEOUT_SECONDS``: the API never shares its interpreter with the
reading. pypdf's decompression and heavy pages are bounded too.
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import re
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from pypdf import PageObject, PdfReader, apply_configuration

logger = logging.getLogger(__name__)

# The reading process runs this module from the API's root, where ``services`` is importable.
_API_ROOT = Path(__file__).resolve().parents[2]
_READER_MODULE = "services.ai_assistant.document_text"


class DocumentRejected(ValueError):
    """A PDF refused, with a sentence the operator can act on (shown as is)."""


class DocumentReaderBusy(RuntimeError):
    """Another PDF is being read: the documents are read one at a time."""


@dataclass(frozen=True)
class ExtractedDocument:
    """The cleaned text of a document, its page count, and whether the text was cut."""

    text: str
    pages: int
    truncated: bool


class AiAssistantDocumentText:
    """Extracts and cleans the text of an uploaded PDF."""

    MAX_BYTES: ClassVar[int] = 10 * 1024 * 1024
    MAX_PAGES: ClassVar[int] = 60
    MAX_CHARS: ClassVar[int] = 30_000
    # Below this, a PDF has no usable text layer (a scan, a picture brochure).
    MIN_CHARS: ClassVar[int] = 40
    TIMEOUT_SECONDS: ClassVar[float] = 30.0
    # A page whose decoded drawing instructions exceed this is artwork, not text: it is skipped.
    MAX_PAGE_CONTENT_BYTES: ClassVar[int] = 1024 * 1024
    # What one compressed stream may inflate to (pypdf's default is 75 MB).
    MAX_STREAM_BYTES: ClassVar[int] = 8 * 1024 * 1024
    # The reading process's memory, where the system can bound it (not on Windows).
    MAX_PROCESS_MEMORY_BYTES: ClassVar[int] = 768 * 1024 * 1024
    UNREADABLE: ClassVar[str] = "PDF illisible : exportez-le à nouveau depuis son logiciel"
    TOO_SLOW: ClassVar[str] = "PDF trop long à lire : exportez-le à nouveau, plus léger"
    BUSY: ClassVar[str] = "Un autre PDF est en cours de lecture : réessayez dans un instant"
    _CONTROL: ClassVar[re.Pattern[str]] = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
    # A word cut at the end of a line (« répara-\ntion »); digits and capitals are left alone (« 6-\n12 ans »,
    # « Saint-\nÉtienne »).
    _HYPHENATED: ClassVar[re.Pattern[str]] = re.compile(r"([a-zß-öø-ÿ])-\n([a-zß-öø-ÿ])")
    _READING: ClassVar[threading.Lock] = threading.Lock()

    @classmethod
    async def read(cls, data: bytes) -> ExtractedDocument:
        """
        Read a PDF in a separate process, one at a time, stopped after ``TIMEOUT_SECONDS``.

        Args:
            data: The file's bytes.

        Returns:
            The cleaned, bounded text (see :meth:`extract`).

        Raises:
            DocumentRejected: When the file is refused or its reading takes too long.
            DocumentReaderBusy: When another PDF is being read.
        """
        return await asyncio.to_thread(cls._read_in_process, data)

    @classmethod
    def _read_in_process(cls, data: bytes) -> ExtractedDocument:
        """Run the reading process on the file, kill it when it runs out of time, and read its answer."""
        if not cls._READING.acquire(blocking=False):
            raise DocumentReaderBusy(cls.BUSY)
        try:
            completed = subprocess.run(  # This module, run by the API's own interpreter.
                [sys.executable, "-m", _READER_MODULE],
                input=data,
                capture_output=True,
                timeout=cls.TIMEOUT_SECONDS,
                cwd=_API_ROOT,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:  # subprocess.run has killed the process.
            logger.warning("PDF reading stopped after %s s", cls.TIMEOUT_SECONDS)
            raise DocumentRejected(cls.TOO_SLOW) from exc
        finally:
            cls._READING.release()
        try:
            answer = json.loads(completed.stdout.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:  # The process died without answering.
            logger.warning(
                "PDF reading process failed with code %s: %s",
                completed.returncode,
                completed.stderr.decode("utf-8", "replace")[-500:],
            )
            raise DocumentRejected(cls.UNREADABLE) from exc
        if isinstance(answer.get("error"), str):
            raise DocumentRejected(answer["error"])
        return ExtractedDocument(
            text=str(answer["text"]), pages=int(answer["pages"]), truncated=bool(answer["truncated"])
        )

    @classmethod
    def bound_process(cls) -> None:
        """Bound the reading process's memory where the system allows it (the timeout stops it anyway)."""
        try:
            import resource

            resource.setrlimit(resource.RLIMIT_AS, (cls.MAX_PROCESS_MEMORY_BYTES, cls.MAX_PROCESS_MEMORY_BYTES))
        except (ImportError, ValueError, OSError):
            logger.info("PDF reading process left without a memory bound")

    @classmethod
    def extract(cls, data: bytes) -> ExtractedDocument:
        """
        Read the text of a PDF (in the calling process: see :meth:`read`).

        Args:
            data: The file's bytes.

        Returns:
            The cleaned text, bounded to ``MAX_CHARS`` at a line break.

        Raises:
            DocumentRejected: When the file is not a readable PDF, is protected, is too large, or has no text layer.
        """
        if len(data) > cls.MAX_BYTES:
            raise DocumentRejected("Fichier trop lourd (10 Mo au plus)")
        if not data.startswith(b"%PDF"):
            raise DocumentRejected("Ce fichier n'est pas un PDF")
        limits = dict.fromkeys(
            (
                "zlib_maximum_output_length",
                "lzw_maximum_output_length",
                "run_length_maximum_output_length",
                "array_based_stream_maximum_output_length",
                "jbig2_maximum_output_length",
            ),
            cls.MAX_STREAM_BYTES,
        )
        try:
            with apply_configuration(**limits):
                reader = PdfReader(io.BytesIO(data), strict=False)
                if reader.is_encrypted and not reader.decrypt(""):
                    raise DocumentRejected("PDF protégé par un mot de passe : enregistrez-le sans protection")
                pages = [cls._page_text(page) for page in reader.pages[: cls.MAX_PAGES]]
                page_count = len(reader.pages)
        except DocumentRejected:
            raise
        except Exception as exc:  # pypdf's own errors: parsing, limits, unsupported encryption.
            logger.warning("Unreadable PDF: %s: %s", exc.__class__.__name__, exc)
            raise DocumentRejected(cls.UNREADABLE) from exc
        text = cls.clean("\n\n".join(pages))
        if len(text) < cls.MIN_CHARS:
            raise DocumentRejected("Ce PDF ne contient pas de texte lisible (document scanné ?)")
        bounded, truncated = cls.bound(text, cls.MAX_CHARS)
        return ExtractedDocument(text=bounded, pages=page_count, truncated=truncated or page_count > cls.MAX_PAGES)

    @classmethod
    def _page_text(cls, page: PageObject) -> str:
        """The text of a page, or nothing for a page of artwork (heavy drawing instructions)."""
        contents = page.get_contents()
        if contents is not None and len(contents.get_data()) > cls.MAX_PAGE_CONTENT_BYTES:
            return ""
        return page.extract_text() or ""

    @classmethod
    def clean(cls, raw: str) -> str:
        """
        Tidy extracted text: control characters out, hyphenated breaks joined, spaces and blank lines collapsed.

        Args:
            raw: Text as pypdf returns it.

        Returns:
            The cleaned text.
        """
        text = cls._CONTROL.sub(" ", raw.replace("\r\n", "\n").replace("\r", "\n"))
        text = cls._HYPHENATED.sub(r"\1\2", text)
        lines = [" ".join(line.split()) for line in text.split("\n")]
        cleaned: list[str] = []
        for line in lines:
            if line or (cleaned and cleaned[-1]):
                cleaned.append(line)
        return "\n".join(cleaned).strip()

    @staticmethod
    def bound(text: str, max_chars: int) -> tuple[str, bool]:
        """
        Cut a text to a size, at the last line break (or space) before it.

        Args:
            text: The text.
            max_chars: The size not to exceed.

        Returns:
            The text and whether it was cut.
        """
        if len(text) <= max_chars:
            return text, False
        head = text[:max_chars]
        cut = head.rfind("\n")
        if cut <= max_chars // 2:
            cut = head.rfind(" ")
        return (head[:cut] if cut > max_chars // 2 else head).rstrip() + " […]", True


def _main() -> None:
    """The reading process: a PDF on stdin, its text (or the sentence that refuses it) as JSON on stdout."""
    AiAssistantDocumentText.bound_process()
    try:
        document = AiAssistantDocumentText.extract(sys.stdin.buffer.read())
        answer: dict[str, object] = {"text": document.text, "pages": document.pages, "truncated": document.truncated}
    except DocumentRejected as exc:
        answer = {"error": str(exc)}
    except Exception:  # Memory exhausted, or anything pypdf raised past extract's net: the file cannot be read.
        answer = {"error": AiAssistantDocumentText.UNREADABLE}
    sys.stdout.buffer.write(json.dumps(answer).encode("utf-8"))


if __name__ == "__main__":
    _main()
