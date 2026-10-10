"""Narrow Gmail/OAuth HTTP operations. Never log tokens or provider bodies."""
import base64
import hashlib
import os
import secrets
import time
from json import JSONDecodeError
from threading import Lock
from dataclasses import dataclass
from email.message import EmailMessage
from email.policy import SMTP
from urllib.parse import urlencode, urlsplit

import httpx2
from cryptography.fernet import Fernet, InvalidToken


SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
OAUTH_STATES: dict[str, tuple[float, str]] = {}
STATE_LOCK = Lock()


class GmailError(ValueError):
    def __init__(self, detail: str, status_code: int = 503):
        super().__init__(detail)
        self.status_code = status_code


@dataclass(frozen=True)
class GmailConfig:
    client_id: str
    client_secret: str
    redirect_uri: str
    frontend_url: str
    cipher: Fernet


def configuration() -> GmailConfig:
    names = ("GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_SECRET", "GMAIL_TOKEN_ENCRYPTION_KEY")
    if any(not os.environ.get(name) for name in names):
        raise GmailError("Set backend OAuth client credentials and GMAIL_TOKEN_ENCRYPTION_KEY, then recreate the backend.")
    try:
        cipher = Fernet(os.environ["GMAIL_TOKEN_ENCRYPTION_KEY"].encode())
    except (ValueError, TypeError) as error:
        raise GmailError("GMAIL_TOKEN_ENCRYPTION_KEY is not a valid Fernet key.") from error
    redirect = os.environ.get("GOOGLE_OAUTH_REDIRECT_URI", "http://127.0.0.1:8000/gmail/callback")
    frontend = os.environ.get("GMAIL_FRONTEND_URL", "http://127.0.0.1:5173/settings")
    # This application has no public authentication layer yet; keep OAuth local.
    for value in (redirect, frontend):
        parts = urlsplit(value)
        if parts.scheme != "http" or parts.hostname not in {"localhost", "127.0.0.1"} or parts.username or parts.password or parts.query or parts.fragment:
            raise GmailError("Gmail callback and frontend URLs must be local HTTP URLs without credentials or query strings.")
    return GmailConfig(os.environ[names[0]], os.environ[names[1]], redirect, frontend, cipher)


def authorization_url(config: GmailConfig) -> tuple[str, str]:
    now = time.monotonic()
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    with STATE_LOCK:
        for expired in [key for key, (created, _) in OAUTH_STATES.items() if now - created > 600]:
            OAUTH_STATES.pop(expired, None)
        if len(OAUTH_STATES) >= 50:
            raise GmailError("Too many pending connections; wait ten minutes and retry.")
        OAUTH_STATES[state] = (now, verifier)
    params = {
        "client_id": config.client_id, "redirect_uri": config.redirect_uri,
        "response_type": "code", "scope": f"openid email {SEND_SCOPE}",
        "state": state, "access_type": "offline", "prompt": "consent",
        "code_challenge": challenge, "code_challenge_method": "S256",
    }
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params), state


def consume_state(state: str, cookie: str | None) -> str:
    if not cookie or not secrets.compare_digest(cookie, state):
        raise GmailError("Invalid Gmail connection state; reconnect from Settings.", 400)
    with STATE_LOCK:
        saved = OAUTH_STATES.pop(state, None)
    if not saved or time.monotonic() - saved[0] > 600:
        raise GmailError("Gmail connection expired; reconnect from Settings.", 400)
    return saved[1]


async def exchange_code(client: httpx2.AsyncClient, config: GmailConfig, code: str, verifier: str) -> tuple[str, str]:
    # code: temp authorisation code google returned to /gmail/callback
    # verifier: secret PKCE value BE generated when starting this connection 
    # on success, fn returns 2 strings: account email and encrypted refresh token (not auth code)
    try:
        response = await client.post("https://oauth2.googleapis.com/token", data={ #sends form encoded fields rather than json
            "client_id": config.client_id, "client_secret": config.client_secret,
            "code": code, "code_verifier": verifier, "redirect_uri": config.redirect_uri,
            "grant_type": "authorization_code",
        })
        if not response.is_success:
            raise GmailError("Google refused the OAuth connection. Check the client and exact redirect URI.", 400)
        tokens = response.json()
        if SEND_SCOPE not in tokens.get("scope", "").split() or not tokens.get("refresh_token"):
            raise GmailError("Gmail send permission and offline access are required. Reconnect and approve both.", 400)
        account = await client.get("https://openidconnect.googleapis.com/v1/userinfo", headers={"Authorization": f"Bearer {tokens['access_token']}"})
        # identifies which google acc was connected. Bearer means authorise this request using the following token
        if not account.is_success:
            raise GmailError("Could not verify the connected Google account.", 502)
        profile = account.json()
        if profile.get("email_verified") is not True or not profile.get("email"):
            raise GmailError("Google did not return a verified account email.", 502)
        return profile["email"], config.cipher.encrypt(tokens["refresh_token"].encode()).decode()
    except (httpx2.RequestError, KeyError, TypeError, JSONDecodeError) as error:
        raise GmailError("Google connection failed; reconnect from Settings.") from error


async def access_token(client: httpx2.AsyncClient, encrypted_token: str) -> str:
    config = configuration()
    try:
        refresh = config.cipher.decrypt(encrypted_token.encode()).decode()
    except InvalidToken as error:
        raise GmailError("Stored Gmail connection cannot be decrypted. Restore the encryption key or reconnect.") from error
    try:
        response = await client.post("https://oauth2.googleapis.com/token", data={
            "client_id": config.client_id, "client_secret": config.client_secret,
            "refresh_token": refresh, "grant_type": "refresh_token",
        })
        if not response.is_success:
            raise GmailError("Gmail permission expired or was revoked. Reconnect from Settings.", 401)
        return response.json()["access_token"]
    except (httpx2.RequestError, KeyError, TypeError, JSONDecodeError) as error:
        raise GmailError("Could not refresh Gmail access. No email was sent.") from error


def encode_email(sender: str, recipient: str, subject: str, body: str, message_id: str) -> str:
    message = EmailMessage(policy=SMTP)
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject
    message["Message-ID"] = message_id
    # set_content() appends a newline. Preserve the exact approved UTF-8 body instead.
    message["MIME-Version"] = "1.0"
    message["Content-Type"] = "text/plain; charset=utf-8"
    message["Content-Transfer-Encoding"] = "base64"
    message.set_payload(base64.encodebytes(body.encode("utf-8")).decode("ascii"))
    # body.encode("utf-8"): converts the approved text into bytes.
    # base64.encodebytes(...): represents those bytes using Base64 characters.
    # .decode("ascii"): converts that representation into a string.
    # set_payload(...): assigns it as the email body.
    return base64.urlsafe_b64encode(message.as_bytes()).decode()
    # serialise message into bytes
    # converts bytes into base64url format gmail expects 
    # decodes into text


async def deliver(client: httpx2.AsyncClient, token: str, raw: str) -> tuple[str, str | None]:
    # Never retry this POST: a timeout does not prove Gmail failed to send.
    try:
        response = await client.post("https://gmail.googleapis.com/gmail/v1/users/me/messages/send", headers={"Authorization": f"Bearer {token}"}, json={"raw": raw})
        # uses http client to send a request to gmail's endpt
        # authorisation: bearer token supplies access token. google checks it; function doesnt authenticate it locally 
        # json = {"raw":raw} sends json object whose raw field contains base64url encoded email, not plain message text
        if response.is_success:
            identity = response.json().get("id")
            return ("sent", identity) if identity else ("unknown", None)
        if response.status_code >= 500 or response.status_code == 408:
            return "unknown", None
        return "failed", None
    except (httpx2.RequestError, ValueError, TypeError):
        return "unknown", None
