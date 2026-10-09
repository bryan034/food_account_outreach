import asyncio
import socket

import httpx2
import pytest

from automate_food_places_outreach.services import website_fetching as fetching


@pytest.fixture
def mock_web(monkeypatch):
    pages = {}
    requests = []
    real_client = httpx2.AsyncClient

    async def public_ip(host, port):
        return "93.184.216.34"

    def handle(request):
        requests.append(request)
        return pages.get(request.url.path, httpx2.Response(404))

    def fake_client(**kwargs):
        assert kwargs["trust_env"] is False
        return real_client(transport=httpx2.MockTransport(handle), **kwargs)

    monkeypatch.setattr(fetching, "resolve_public_ip", public_ip)
    monkeypatch.setattr(fetching.httpx2, "AsyncClient", fake_client)
    return pages, requests


def html_response(html):
    return httpx2.Response(200, headers={"content-type": "text/html; charset=utf-8"}, text=html)


def test_homepage_and_contact_page_keep_sources_and_skip_external_links(mock_web):
    pages, requests = mock_web
    pages["/"] = html_response('''
        <a href="mailto:hello@example.com">Email</a>
        <a href="https://outside.example/contact">External contact</a>
        <a href="/contact#email">Contact</a>
        <a href="/contact">Same contact</a>
        <a href="/about">About</a>
        <a href="/contact-extra">Over budget</a>
    ''')
    pages["/contact"] = html_response('''
        <a href="mailto:hello@example.com">Same email, another source</a>
        <a href="https://instagram.com/examplecafe">Instagram</a>
    ''')
    pages["/about"] = html_response('<a href="https://tiktok.com/@examplecafe">TikTok</a>')

    result = asyncio.run(fetching.enrich_website("https://example.com/"))

    assert result.pages_visited == ["https://example.com/", "https://example.com/contact", "https://example.com/about"]
    assert len(requests) == 3
    assert len(result.contacts) == 4
    assert [contact.source_url for contact in result.contacts if contact.contact_type == "email"] == [
        "https://example.com/", "https://example.com/contact",
    ]
    assert result.failures == []
    assert all(request.url.host == "93.184.216.34" for request in requests)
    assert all(request.headers["host"] == "example.com" for request in requests)
    assert all(request.extensions["sni_hostname"] == "example.com" for request in requests)
    assert all("X-Goog-Api-Key" not in request.headers for request in requests)


def test_broken_contact_page_preserves_homepage_contacts(mock_web):
    pages, _requests = mock_web
    pages["/"] = html_response('<a href="mailto:hello@example.com">Email</a><a href="/contact">Contact</a>')
    result = asyncio.run(fetching.enrich_website("https://example.com"))
    assert len(result.contacts) == 1
    assert result.failures[0].url == "https://example.com/contact"
    assert "404" in result.failures[0].reason


@pytest.mark.parametrize("url", [
    "file:///etc/passwd", "http://localhost", "http://127.0.0.1",
    "http://10.0.0.1", "http://[::1]", "https://example.com:8000",
    "https://user:password@example.com", "https://example.com:bad",
])
def test_unsafe_urls_rejected(url):
    with pytest.raises(fetching.WebsiteFetchError):
        fetching.validate_website_url(url)


def test_dns_resolving_private_address_is_rejected(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443)),
    ])
    with pytest.raises(fetching.WebsiteFetchError, match="private"):
        asyncio.run(fetching.resolve_public_ip("example.com", 443))


def test_redirect_source_url_is_final_page(mock_web):
    pages, requests = mock_web
    pages["/"] = httpx2.Response(302, headers={"location": "/home"})
    pages["/home"] = html_response('<a href="mailto:hello@example.com">Email</a>')
    result = asyncio.run(fetching.enrich_website("https://example.com"))
    assert result.contacts[0].source_url == "https://example.com/home"
    assert len(requests) == 2


@pytest.mark.parametrize("destination", ["http://127.0.0.1", "https://other.example/contact", "http://example.com/contact"])
def test_unsafe_redirect_is_not_followed(mock_web, destination):
    pages, requests = mock_web
    pages["/"] = httpx2.Response(302, headers={"location": destination})
    with pytest.raises(fetching.WebsiteFetchError):
        asyncio.run(fetching.enrich_website("https://example.com"))
    assert len(requests) == 1


def test_redirect_loop_is_bounded(mock_web):
    pages, requests = mock_web
    pages["/"] = httpx2.Response(302, headers={"location": "/"})
    with pytest.raises(fetching.WebsiteFetchError, match="redirect"):
        asyncio.run(fetching.enrich_website("https://example.com"))
    assert len(requests) == 3


def test_non_html_is_rejected(mock_web):
    pages, _requests = mock_web
    pages["/"] = httpx2.Response(200, headers={"content-type": "application/pdf"}, content=b"pdf")
    with pytest.raises(fetching.WebsiteFetchError, match="not HTML"):
        asyncio.run(fetching.enrich_website("https://example.com"))


def test_oversized_response_is_rejected(mock_web):
    pages, _requests = mock_web
    pages["/"] = html_response("x" * (fetching.MAX_HTML_BYTES + 1))
    with pytest.raises(fetching.WebsiteFetchError, match="size limit"):
        asyncio.run(fetching.enrich_website("https://example.com"))


def test_network_timeout_has_clear_error(mock_web, monkeypatch):
    async def timed_out(host, port):
        raise TimeoutError("DNS timeout")
    monkeypatch.setattr(fetching, "resolve_public_ip", timed_out)
    with pytest.raises(fetching.WebsiteFetchError, match="timeout"):
        asyncio.run(fetching.enrich_website("https://example.com"))


def test_homepage_http_error_stops_crawl(mock_web):
    pages, requests = mock_web
    pages["/"] = httpx2.Response(403)
    with pytest.raises(fetching.WebsiteFetchError, match="403"):
        asyncio.run(fetching.enrich_website("https://example.com"))
    assert len(requests) == 1
