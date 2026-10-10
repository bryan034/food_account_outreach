import re #python's regular expression module. describe text patterns 
from urllib.parse import unquote, urljoin, urlsplit #unquote decodes url escapes: %40 becomes @

from bs4 import BeautifulSoup

from automate_food_places_outreach.schemas.contacts import ContactCandidate


# Conservative support for common public business email addresses.
EMAIL_PATTERN = re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,}")
INSTAGRAM_NON_PROFILE_PATHS = {
    "accounts", "about", "developer", "direct", "directory", "explore",
    "legal", "p", "reel", "reels", "stories", "share", "tv", "web",
}


def parse_contact_link(href: str, source_url: str) -> ContactCandidate | None:
    absolute_url = urljoin(source_url, href.strip())
    parts = urlsplit(absolute_url) #splits url into scheme, hostname, path, query

    if parts.scheme == "mailto":
        email = unquote(parts.path).strip()
        if EMAIL_PATTERN.fullmatch(email) is None: #requires email to fully match re.compile() pattern above
            return None
        local, domain = email.rsplit("@", 1)
        value = f"{local}@{domain.lower()}"
        return ContactCandidate(
            contact_type="email", value=value,
            direct_url=f"mailto:{value}", source_url=source_url,
        )

    if parts.scheme not in {"http", "https"} or parts.username or parts.password:
        return None
    if parts.port not in {None, 80, 443}: #these are the conventional http/https ports. reject unusual ports
        return None

    host = parts.hostname
    path = parts.path.strip("/")
    if host in {"tiktok.com", "www.tiktok.com"}:
        if re.fullmatch(r"@[A-Za-z0-9_][A-Za-z0-9_.]{0,23}", path) is None:
            return None
        contact_type = "tiktok"
        value = path[1:].lower()
        direct_url = f"https://www.tiktok.com/@{value}"
    elif host in {"instagram.com", "www.instagram.com"}:
        if re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.]{0,29}", path) is None:
            return None
        value = path.lower()
        if value in INSTAGRAM_NON_PROFILE_PATHS:
            return None
        contact_type = "instagram"
        direct_url = f"https://www.instagram.com/{value}/"
    else:
        return None

    return ContactCandidate(
        contact_type=contact_type, value=value,
        direct_url=direct_url, source_url=source_url,
    )


def extract_contacts(html: str, source_url: str) -> list[ContactCandidate]:
    soup = BeautifulSoup(html, "html.parser") #parses supplied html, doesnt download anyth
    contacts: list[ContactCandidate] = []
    seen: set[tuple[str, str]] = set()

    for link in soup.find_all("a", href=True): #finds all <a> elem w href attribute
        href = link.get("href")
        if not isinstance(href, str):
            continue
        try:
            contact = parse_contact_link(href, source_url)
        except ValueError:
            # Malformed URLs (for example, invalid ports) are not contacts.
            continue
        if contact is None:
            continue
        identity = (contact.contact_type, contact.value)
        if identity in seen:
            continue
        seen.add(identity)
        contacts.append(contact)

    return contacts
