"""
The Gmail HTTP client: the consent page, the calls it makes, what it reads of Google's answers, and the errors that
call for a new consent. Every request goes through an httpx MockTransport.
"""

import asyncio
import base64
import json
from datetime import datetime
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

import services.ai_assistant.gmail_client as gmail_module
import services.google_oauth_client as oauth_module
from services.ai_assistant.gmail_client import GmailClient, GmailError


def _client_with(handler: Any, monkeypatch: pytest.MonkeyPatch) -> GmailClient:
    """A Gmail client whose every HTTP request is answered by ``handler``."""
    transport = httpx.MockTransport(handler)
    original = httpx.AsyncClient

    def patched_client(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs["transport"] = transport
        return original(*args, **kwargs)

    monkeypatch.setattr(gmail_module.httpx, "AsyncClient", patched_client)
    monkeypatch.setattr(oauth_module.httpx, "AsyncClient", patched_client)
    monkeypatch.setattr(gmail_module.settings, "google_client_id", "client-id")
    monkeypatch.setattr(gmail_module.settings, "google_client_secret", "client-secret")
    monkeypatch.setattr(
        gmail_module.settings, "google_mailbox_redirect_uri", "https://api.example.fr/ai-assistants/mailbox/cb"
    )
    return GmailClient()


def _error(status: int, reason: str) -> httpx.Response:
    """A Google API error answer."""
    return httpx.Response(
        status, json={"error": {"code": status, "message": "refused", "errors": [{"reason": reason}]}}
    )


def test_the_mailbox_is_configured_only_with_google_and_its_redirect_address(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client_with(lambda request: httpx.Response(200), monkeypatch)
    configured = client.is_configured
    monkeypatch.setattr(gmail_module.settings, "google_mailbox_redirect_uri", " ")

    assert configured is True
    assert client.is_configured is False


def test_the_consent_asks_offline_reading_and_drafts_only(monkeypatch: pytest.MonkeyPatch) -> None:
    _client_with(lambda request: httpx.Response(200), monkeypatch)
    query = parse_qs(urlparse(GmailClient.authorization_url("7.123.sig")).query)

    assert query["scope"][0].split() == [
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.compose",
    ]
    assert query["redirect_uri"] == ["https://api.example.fr/ai-assistants/mailbox/cb"]
    assert (query["access_type"], query["prompt"], query["state"]) == (["offline"], ["consent"], ["7.123.sig"])
    assert "include_granted_scopes" not in query


def test_the_drafts_link_opens_the_connected_account() -> None:
    assert GmailClient.drafts_url("garage.morel@gmail.com") == (
        "https://mail.google.com/mail/?authuser=garage.morel@gmail.com#drafts"
    )
    assert GmailClient.drafts_url(None) == "https://mail.google.com/mail/#drafts"


def test_the_history_gives_the_emails_received_and_the_threads_answered(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.params.get("pageToken") is None:
            return httpx.Response(
                200,
                json={
                    "history": [
                        {"messagesAdded": [{"message": {"id": "m1", "threadId": "t1", "labelIds": ["INBOX"]}}]},
                        {"messagesAdded": [{"message": {"id": "d1", "threadId": "t1", "labelIds": ["DRAFT"]}}]},
                        {"messagesAdded": [{"message": {"id": "s1", "threadId": "t0", "labelIds": ["SENT"]}}]},
                    ],
                    "nextPageToken": "p2",
                    "historyId": "1500",
                },
            )
        return httpx.Response(
            200,
            json={
                "history": [
                    {"messagesAdded": [{"message": {"id": "m1", "threadId": "t1", "labelIds": ["INBOX"]}}]},
                    {"messagesAdded": [{"message": {"id": "m2", "threadId": "t2", "labelIds": ["INBOX", "UNREAD"]}}]},
                    {"labelsAdded": [{"message": {"id": "s2", "threadId": "t3"}, "labelIds": ["SENT"]}]},
                ],
                "historyId": "1502",
            },
        )

    client = _client_with(handler, monkeypatch)
    changes = asyncio.run(client.changes_since("token", "1400"))

    assert changes is not None
    assert [(ref.message_id, ref.thread_id) for ref in changes.received] == [("m1", "t1"), ("m2", "t2")]
    assert changes.answered_thread_ids == frozenset({"t0", "t3"})
    assert changes.history_id == "1502"
    assert seen[0].headers["Authorization"] == "Bearer token"
    assert seen[0].url.params.get_list("historyTypes") == ["messageAdded", "labelAdded"]
    assert seen[0].url.params["startHistoryId"] == "1400"


def test_an_expired_history_id_or_a_backlog_too_long_reads_as_no_history(monkeypatch: pytest.MonkeyPatch) -> None:
    expired = _client_with(lambda request: _error(404, "notFound"), monkeypatch)
    assert asyncio.run(expired.changes_since("token", "1")) is None

    endless = _client_with(
        lambda request: httpx.Response(200, json={"history": [], "nextPageToken": "more", "historyId": "9"}),
        monkeypatch,
    )
    assert asyncio.run(endless.changes_since("token", "1")) is None


def test_the_recent_inbox_is_listed_oldest_first(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200, json={"messages": [{"id": "new", "threadId": "t2"}, {"id": "old", "threadId": "t1"}]}
        )

    refs = asyncio.run(_client_with(handler, monkeypatch).recent_inbox("token"))

    assert [ref.message_id for ref in refs] == ["old", "new"]
    assert seen[0].url.params["q"] == "in:inbox newer_than:1d"


def test_a_message_is_read_with_its_headers_labels_date_and_text(monkeypatch: pytest.MonkeyPatch) -> None:
    body = base64.urlsafe_b64encode("Bonjour, une fuite près de la cheminée.".encode()).decode()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/gone"):
            return _error(404, "notFound")
        return httpx.Response(
            200,
            json={
                "id": "m1",
                "threadId": "t1",
                "labelIds": ["INBOX", "UNREAD"],
                "internalDate": "1790064000000",
                "payload": {
                    "mimeType": "text/plain",
                    "headers": [{"name": "Subject", "value": "Fuite"}, {"name": "Message-ID", "value": "<m1@x>"}],
                    "body": {"data": body},
                },
            },
        )

    client = _client_with(handler, monkeypatch)
    full = asyncio.run(client.get_message("token", "m1", with_body=True))
    metadata = asyncio.run(client.get_message("token", "m1", with_body=False))

    assert full is not None and metadata is not None
    assert (full.message_id, full.thread_id, full.label_ids) == ("m1", "t1", frozenset({"INBOX", "UNREAD"}))
    assert full.headers == {"subject": "Fuite", "message-id": "<m1@x>"}
    assert full.received_at == datetime(2026, 9, 22, 8, 0)
    assert full.text == "Bonjour, une fuite près de la cheminée."
    assert metadata.text == ""
    assert asyncio.run(client.get_message("token", "gone", with_body=False)) is None


def test_a_draft_is_created_in_its_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"id": "r-42", "message": {"id": "d1", "threadId": "t1"}})

    draft_id = asyncio.run(_client_with(handler, monkeypatch).create_draft("token", thread_id="t1", raw="UkFX"))

    assert draft_id == "r-42"
    assert seen[0].method == "POST" and seen[0].url.path == "/gmail/v1/users/me/drafts"
    assert json.loads(seen[0].content) == {"message": {"raw": "UkFX", "threadId": "t1"}}


def test_the_profile_gives_the_address_and_the_history_id(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client_with(
        lambda request: httpx.Response(200, json={"emailAddress": "Garage.Morel@gmail.com", "historyId": "1234"}),
        monkeypatch,
    )

    profile = asyncio.run(client.get_profile("token"))

    assert (profile.email_address, profile.history_id) == ("garage.morel@gmail.com", "1234")


@pytest.mark.parametrize(
    ("response", "needs_reconnect"),
    [
        (_error(401, "authError"), True),
        (_error(403, "insufficientPermissions"), True),
        (_error(403, "domainPolicy"), True),
        (_error(403, "userRateLimitExceeded"), False),
        (_error(429, "rateLimitExceeded"), False),
        (_error(500, "backendError"), False),
    ],
)
def test_only_a_dead_token_missing_scopes_or_a_domain_policy_call_for_a_new_consent(
    monkeypatch: pytest.MonkeyPatch, response: httpx.Response, needs_reconnect: bool
) -> None:
    client = _client_with(lambda request: response, monkeypatch)

    with pytest.raises(GmailError) as caught:
        asyncio.run(client.get_profile("token"))

    assert caught.value.needs_reconnect is needs_reconnect
    assert caught.value.status_code == response.status_code


def test_tokens_are_exchanged_refreshed_and_revoked_through_the_shared_oauth_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/revoke":
            return httpx.Response(200)
        form = parse_qs(request.content.decode())
        if form.get("refresh_token") == ["dead"]:
            return httpx.Response(400, json={"error": "invalid_grant"})
        return httpx.Response(
            200, json={"access_token": "a", "refresh_token": "r", "expires_in": 3599, "scope": "openid"}
        )

    client = _client_with(handler, monkeypatch)
    tokens = asyncio.run(client.exchange_code("code"))
    revoked = asyncio.run(client.revoke("r"))
    with pytest.raises(GmailError) as caught:
        asyncio.run(client.refresh("dead"))

    assert (tokens.access_token, tokens.refresh_token) == ("a", "r")
    assert parse_qs(seen[0].content.decode())["redirect_uri"] == ["https://api.example.fr/ai-assistants/mailbox/cb"]
    assert revoked is True and parse_qs(seen[1].content.decode()) == {"token": ["r"]}
    assert caught.value.needs_reconnect is True
