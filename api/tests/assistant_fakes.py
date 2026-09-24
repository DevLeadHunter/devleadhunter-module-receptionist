"""Fakes shared by the receptionist tests: a recorder of async calls, an SMS provider, a visitor's request."""

from typing import Any

from starlette.requests import Request

from services.sms.sms_provider import SmsSendResult

# A visitor's request as the public routes read it (its address feeds the rate limits).
VISITOR_REQUEST = Request({"type": "http", "headers": [], "client": ("203.0.113.9", 0)})


class AsyncCallRecorder:
    """Collects the calls of a mocked async function and returns a fixed result."""

    def __init__(self, result: Any = None, *, record_args: bool = False) -> None:
        self.calls: list[dict[str, Any]] = []
        self.result = result
        self._record_args = record_args

    async def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append({"args": args, **kwargs} if self._record_args else kwargs)
        return self.result


class AcceptingSmsProvider:
    """A configured SMS provider that accepts everything."""

    is_configured = True

    def __init__(self) -> None:
        self.texts: list[str] = []

    async def send(self, *, to_e164: str, sender: str, text: str, **_: Any) -> SmsSendResult:
        self.texts.append(text)
        return SmsSendResult(success=True, provider_message_id=f"m{len(self.texts)}", price_cents=6)
