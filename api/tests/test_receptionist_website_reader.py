"""The receptionist's website reader fetches the public internet only: an internal address is never read."""

import asyncio

import httpx
import pytest

import devleadhunter_receptionist.services.website_crawler as crawler_module
from devleadhunter_receptionist.services.website_crawler import AiAssistantWebsiteCrawler
from services.public_url_guard import PublicOnlyAsyncTransport, PublicUrlGuard

# What a fake DNS answers: a public site, a site pointing at the machine itself, and a rebinding-style double answer.
_DNS: dict[str, list[str]] = {
    "toiture-martin.fr": ["93.184.216.34"],
    "www.toiture-martin.fr": ["2606:4700:4700::1111", "93.184.216.35"],
    "interne.toiture-martin.fr": ["10.0.0.12"],
    "double.toiture-martin.fr": ["93.184.216.36", "127.0.0.1"],
}


@pytest.fixture
def fake_dns(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Resolve through the table above, recording the hosts asked."""
    asked: list[str] = []
    real_resolve = PublicUrlGuard.resolve

    def resolve(host: str, port: int) -> list[str]:
        asked.append(host)
        if host in _DNS:
            return list(_DNS[host])
        return real_resolve(host, port)

    monkeypatch.setattr(PublicUrlGuard, "resolve", staticmethod(resolve))
    return asked


def _recording_transport(requests: list[httpx.Request], routes: dict[str, httpx.Response]) -> httpx.MockTransport:
    """A mock network that records what reaches it and answers by path."""

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return routes.get(request.url.path, httpx.Response(404))

    return httpx.MockTransport(handler)


def test_the_website_reader_never_reaches_an_internal_address(
    fake_dns: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A website field set to an internal address, or a page redirecting to one, reads nothing from it."""
    requests: list[httpx.Request] = []
    home = (
        "<html><head><title>Toiture Martin</title></head><body><main><p>Couvreur à Poitiers.</p>"
        '<a href="/tarifs">Tarifs</a></main></body></html>'
    )
    network = _recording_transport(
        requests,
        {
            "/": httpx.Response(200, text=home, headers={"content-type": "text/html"}),
            "/tarifs": httpx.Response(302, headers={"location": "http://169.254.169.254/latest/meta-data/"}),
        },
    )
    monkeypatch.setattr(crawler_module, "PublicOnlyAsyncTransport", lambda: PublicOnlyAsyncTransport(network))

    internal = asyncio.run(AiAssistantWebsiteCrawler().crawl("http://localhost:8005/"))
    public = asyncio.run(AiAssistantWebsiteCrawler().crawl("toiture-martin.fr"))

    assert internal is None
    assert public is not None and [page["url"] for page in public["pages"]] == ["https://toiture-martin.fr/"]
    assert {request.url.host for request in requests} == {"93.184.216.34"}
