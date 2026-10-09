import asyncio
import ipaddress
import socket
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx2
from bs4 import BeautifulSoup
from pydantic import BaseModel

from automate_food_places_outreach.schemas.contacts import ContactCandidate
from automate_food_places_outreach.services.website_enrichment import extract_contacts


MAX_HTML_BYTES = 1_000_000
MAX_REDIRECTS = 2
MAX_CONTACT_PAGES = 2


class WebsiteFetchError(ValueError):
    """A website could not be fetched within our crawl rules."""


class HtmlPage(BaseModel):
    url: str
    html: str


class PageFailure(BaseModel):
    url: str
    reason: str


class WebsiteEnrichmentResult(BaseModel):
    pages_visited: list[str]
    contacts: list[ContactCandidate]
    failures: list[PageFailure]


def validate_website_url(url: str) -> str:
    try:
        parts = urlsplit(url)
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            raise WebsiteFetchError("Website must be an HTTP or HTTPS URL")
        if parts.username or parts.password:
            raise WebsiteFetchError("Website URL must not include credentials")
        expected_port = 443 if parts.scheme == "https" else 80
        if parts.port not in {None, expected_port}:
            raise WebsiteFetchError("Non-standard website ports are not supported")
        if parts.hostname == "localhost" or parts.hostname.endswith(".localhost"):
            raise WebsiteFetchError("Local websites are not allowed")
        # Also catches numeric private addresses before DNS resolution.
        try:
            address = ipaddress.ip_address(parts.hostname)
        except ValueError:
            address = None
        if address is not None and not address.is_global: #is global checks if ipaddr is globally routable over public internet
            raise WebsiteFetchError("Private or reserved addresses are not allowed")
        return urlunsplit((parts.scheme, parts.netloc, parts.path or "/", parts.query, ""))
        # parts.netloc stands for network location: [username:password@]hostname[:port]
    except ValueError as error:
        if isinstance(error, WebsiteFetchError):
            raise
        raise WebsiteFetchError("Malformed website URL") from error


async def resolve_public_ip(host: str, port: int) -> str:
    # resolves domain name/ IP string async and ensures all corresponding IP addr publicly routable over internet
    answers = await asyncio.get_running_loop().getaddrinfo( 
        # asyncio.get_running_loop() retrieves event loop currently executing async code 
        # getaddrinfo() asks os to resolve hostname and provide connection addresses
        host, port, type=socket.SOCK_STREAM,
        # type=socket.SOCK_STREAM asks for stream-socket results which we use for TCP connections
        # alternative is SOCK_DGRAM which uses UDP (things like video streaming, online games, voice calls etc)
    )
    # answers look like 
    # (
    # socket.AF_INET,          # Address family: IPv4
    # socket.SOCK_STREAM,      # Socket type: TCP stream
    # 6,                      # Protocol number: TCP
    # "",                     # Canonical name
    # ("93.184.216.34", 443),  # Connection address
    # )   
    addresses = [ipaddress.ip_address(answer[4][0]) for answer in answers]
    if not addresses or any(not address.is_global for address in addresses):
        raise WebsiteFetchError("Website resolves to a private or reserved address")
    return str(addresses[0])


def same_website(first: str, second: str) -> bool:
    # strips website to host names and compares if 2 websites are the same
    first_host = (urlsplit(first).hostname or "").removeprefix("www.")
    second_host = (urlsplit(second).hostname or "").removeprefix("www.")
    return first_host == second_host


async def fetch_html(url: str, *, website_url: str) -> HtmlPage:
    current_url = validate_website_url(url)
    try:
        async with asyncio.timeout(15): #gives entire page fetch 15s deadline, including DNS resolution, redirects, and reading body
            for redirect_count in range(MAX_REDIRECTS + 1):
                if not same_website(website_url, current_url):
                    raise WebsiteFetchError("Redirect left the restaurant website")
                original = httpx2.URL(current_url)
                port = original.port or (443 if original.scheme == "https" else 80)
                address = await resolve_public_ip(original.host, port) 
                destination = original.copy_with(host=address) #creates another URL w hostname replaced by checked IP address
                # Fresh client: no Google API key, ambient proxy, or login cookies.
                async with httpx2.AsyncClient(trust_env=False, timeout=5.0) as client:
                    async with client.stream(
                        "GET", destination, #starts GET req to checked IP and gives streaming response 
                        # Streaming lets us inspect and read the response progressively instead of deliberately loading its whole body upfront.
                        headers={
                            "Host": original.netloc.decode("ascii"),
                            "User-Agent": "FoodOutreachResearch/0.1",
                            "Accept": "text/html, application/xhtml+xml",
                        },
                        extensions={"sni_hostname": original.host},
                        follow_redirects=False,
                    ) as response:
                        if response.status_code in {301, 302, 303, 307, 308}:
                            location = response.headers.get("location")
                            if not location or redirect_count == MAX_REDIRECTS:
                                raise WebsiteFetchError("Missing redirect location or too many redirects")
                            next_url = validate_website_url(urljoin(current_url, location))
                            if original.scheme == "https" and urlsplit(next_url).scheme != "https":
                                raise WebsiteFetchError("HTTPS downgrade redirect is not allowed")
                            current_url = next_url
                            continue
                        response.raise_for_status() #raises HTTPStatusError for an unsuccessful HTTP response like 403/404
                        media_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                        if media_type not in {"text/html", "application/xhtml+xml"}:
                            raise WebsiteFetchError("Page is not HTML")
                        body = bytearray() #bytes are immutable, bytearray() can grow using .extend()
                        async for chunk in response.aiter_bytes(chunk_size=65536): #aiter_bites() async generator used in async http clients (HTTPX) and web frameworks like fastapi/ starlette to stream raw binary response data incrementally instead of loading entire payload into memory at once
                            if len(body) + len(chunk) > MAX_HTML_BYTES:
                                raise WebsiteFetchError("HTML page exceeds size limit")
                            body.extend(chunk)
                        return HtmlPage(url=current_url, html=body.decode(response.encoding or "utf-8", errors="replace"))
    except httpx2.HTTPStatusError as error:
        raise WebsiteFetchError(f"Website returned HTTP {error.response.status_code}") from error
    except (httpx2.RequestError, TimeoutError, OSError, LookupError) as error:
        raise WebsiteFetchError("Website connection, encoding, or timeout failure") from error
    raise WebsiteFetchError("Could not retrieve HTML")


def find_contact_pages(html: str, source_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    pages: list[str] = []
    for link in soup.find_all("a", href=True):
        href = link.get("href")
        if not isinstance(href, str):
            continue
        label = f"{href} {link.get_text(' ', strip=True)}".lower()
        # get_text extracts text inside the <a> elem, uses spaces between nested text fragments and removes surrounding whitespace
        if not any(word in label for word in ("contact", "about", "get-in-touch")):
            continue
        try:
            target = validate_website_url(urljoin(source_url, href))
        except WebsiteFetchError:
            continue
        if not same_website(source_url, target) or target == source_url or target in pages:
            continue
        pages.append(target)
        if len(pages) == MAX_CONTACT_PAGES:
            break
    return pages #returns selected urls of contact pages


async def enrich_website(website_url: str) -> WebsiteEnrichmentResult:
    website_url = validate_website_url(website_url)
    homepage = await fetch_html(website_url, website_url=website_url)
    pages = [homepage]
    failures: list[PageFailure] = []
    visited = {homepage.url}
    for target in find_contact_pages(homepage.html, homepage.url):
        try:
            page = await fetch_html(target, website_url=homepage.url)
        except WebsiteFetchError as error:
            failures.append(PageFailure(url=target, reason=str(error)))
            continue
        if page.url not in visited:
            pages.append(page)
            visited.add(page.url)

    contacts: list[ContactCandidate] = []
    seen: set[tuple[str, str, str]] = set()
    for page in pages:
        for contact in extract_contacts(page.html, page.url):
            # Retain distinct source pages for the same contact as evidence.
            identity = (contact.contact_type, contact.value, contact.source_url)
            if identity not in seen:
                seen.add(identity)
                contacts.append(contact)
    return WebsiteEnrichmentResult(
        pages_visited=[page.url for page in pages], contacts=contacts, failures=failures,
    )
