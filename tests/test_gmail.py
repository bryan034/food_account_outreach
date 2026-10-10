import base64
import json
from datetime import datetime, timedelta, timezone
from email import policy
from email.parser import BytesParser
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import httpx2
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from automate_food_places_outreach.api import app
from automate_food_places_outreach.database import engine
from automate_food_places_outreach.dependencies import get_http_client, get_session, require_google_places_api_key
from automate_food_places_outreach import email_api
from automate_food_places_outreach.models.email import GmailAccount, ApprovedEmail, Contact
from automate_food_places_outreach.models.outreach import OutreachAttempt
from automate_food_places_outreach.schemas.contacts import ContactCandidate
from automate_food_places_outreach.services import gmail
from automate_food_places_outreach.services.website_fetching import HtmlPage, WebsiteEnrichmentResult


@pytest.fixture
def setup(monkeypatch):
    # Every endpoint commit releases a SAVEPOINT, never our outer test transaction.
    # Rollback restores any pre-existing connection; tests never overwrite real tokens.
    connection = engine.connect()
    transaction = connection.begin()
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "test-client")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "test-secret")
    key = Fernet.generate_key()
    cipher = Fernet(key)
    monkeypatch.setenv("GMAIL_TOKEN_ENCRYPTION_KEY", key.decode())
    monkeypatch.setenv("GOOGLE_OAUTH_REDIRECT_URI", "http://127.0.0.1:8000/gmail/callback")
    monkeypatch.setenv("GMAIL_FRONTEND_URL", "http://127.0.0.1:5173/settings")
    monkeypatch.setenv("GMAIL_DAILY_SEND_LIMIT", "100000")
    monkeypatch.setattr(gmail, "OAUTH_STATES", {})
    state = {"outcome": "sent", "send_calls": 0, "token_calls": 0}

    def google(request):
        if request.url.host == "places.googleapis.com":
            return httpx2.Response(200, json={"id": request.url.path.rsplit("/", 1)[1], "displayName": {"text": "Test Café"}, "websiteUri": "https://example.com"})
        if request.url.host == "oauth2.googleapis.com":
            state["token_calls"] += 1
            if state.get("token_fail"):
                return httpx2.Response(400, json={"error": "invalid_grant"})
            return httpx2.Response(200, json={"access_token": "fake-access", "refresh_token": "fake-refresh", "scope": gmail.SEND_SCOPE + " openid email"})
        if request.url.host == "openidconnect.googleapis.com":
            return httpx2.Response(200, json={"email": "creator@example.com", "email_verified": True})
        assert request.url.path.endswith("/messages/send")
        state["send_calls"] += 1
        state["message"] = BytesParser(policy=policy.default).parsebytes(base64.urlsafe_b64decode(json.loads(request.content)["raw"]))
        assert request.headers["Authorization"] == "Bearer fake-access"
        if state["outcome"] == "timeout":
            raise httpx2.ReadTimeout("simulated ambiguity", request=request)
        return httpx2.Response(200 if state["outcome"] == "sent" else 403, json={"id": "fake-gmail-id"} if state["outcome"] == "sent" else {"error": "denied"})

    async def http_client():
        async with httpx2.AsyncClient(transport=httpx2.MockTransport(google)) as client:
            yield client

    def database():
        with Session(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False) as session:
            yield session

    async def enrich(_url):
        return WebsiteEnrichmentResult(pages_visited=["https://example.com/contact"], failures=[], contacts=[ContactCandidate(contact_type="email", value="hello@example.com", direct_url="mailto:hello@example.com", source_url="https://example.com/contact")])

    async def fetch(url, *, website_url):
        return HtmlPage(url=url, html='<a href="mailto:hello@example.com">Business email</a>')

    monkeypatch.setitem(app.dependency_overrides, get_session, database)
    monkeypatch.setitem(app.dependency_overrides, get_http_client, http_client)
    monkeypatch.setitem(app.dependency_overrides, require_google_places_api_key, lambda: "test-key")
    monkeypatch.setattr(email_api, "enrich_website", enrich)
    monkeypatch.setattr(email_api, "fetch_html", fetch)
    with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
        session.merge(GmailAccount(id=1, email="creator@example.com", encrypted_refresh_token=cipher.encrypt(b"fake-refresh").decode()))
        session.commit()
    client = TestClient(app, base_url="http://127.0.0.1:8000", headers={"Origin": "http://127.0.0.1:5173"})
    place_id = f"gmail-test-{uuid4()}"
    payload = {"google_place_id": place_id, "recipient": "hello@example.com", "source_url": "https://example.com/contact", "subject": "A factual café collaboration", "message_text": "  Exact approved message.\n", "approved": True, "verified_public_business_email": True}
    try:
        yield client, payload, state, connection, cipher
    finally:
        client.close()
        transaction.rollback()
        connection.close()


def test_source_discovery_then_approval_does_not_send(setup):
    client, payload, state, connection, _ = setup
    contacts = client.post(f"/discovery/google-places/{payload['google_place_id']}/contacts")
    assert contacts.status_code == 200
    assert contacts.json()[0]["verified"] is False
    response = client.post("/outreach/email/approve", json=payload)
    assert response.status_code == 201
    assert response.json()["status"] == "email_approved"
    assert response.json()["sent_at"] is None
    assert response.json()["message_text"] == payload["message_text"]
    assert client.patch(f"/outreach/{response.json()['id']}/status", json={"status": "sent"}).status_code == 409
    assert state["send_calls"] == 0
    with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
        assert session.scalar(select(Contact).where(Contact.restaurant_id == response.json()["restaurant_id"])).verified is True


def test_gmail_send_persists_exact_approval_and_blocks_second_channel(setup):
    client, payload, state, _, _ = setup
    approved = client.post("/outreach/email/approve", json=payload).json()
    assert client.post("/outreach/email/approve", json=payload).status_code == 409
    assert client.post("/outreach/from-place/mark-sent", json={"google_place_id": payload["google_place_id"], "channel": "tiktok", "message_text": "duplicate", "confirmed_sent": True}).status_code == 409
    endpoint = f"/outreach/{approved['id']}/email/send"
    assert client.post(endpoint, json={"approved": False}).status_code == 422
    response = client.post(endpoint, json={"approved": True})
    assert response.status_code == 200
    assert response.json()["status"] == "sent"
    assert response.json()["sent_at"]
    assert response.json()["email"]["gmail_message_id"] == "fake-gmail-id"
    assert state["message"]["To"] == payload["recipient"]
    assert state["message"]["Subject"] == payload["subject"]
    assert state["message"].get_content() == payload["message_text"]
    assert client.post(endpoint, json={"approved": True}).status_code == 409
    assert state["send_calls"] == 1


def test_sent_email_is_in_outreach_and_business_notes_can_change(setup):
    client, payload, state, _, _ = setup
    approved = client.post("/outreach/email/approve", json=payload).json()
    sent = client.post(f"/outreach/{approved['id']}/email/send", json={"approved": True}).json()
    assert any(row["id"] == sent["id"] and row["status"] == "sent"
               for row in client.get("/outreach?limit=100").json())
    endpoint = f"/restaurants/{sent['restaurant_id']}"
    updated = client.patch(endpoint, json={"name": "My café notes", "category": "cafe", "area": "East",
        "address": "Agreed meeting address", "website_url": "https://example.com/contact"})
    assert updated.status_code == 200
    assert client.get(endpoint).json()["name"] == "My café notes"
    # Unspecified note fields survive a name-only PATCH; explicit null clears one.
    assert client.patch(endpoint, json={"name": "New label", "area": None}).json()["address"] == "Agreed meeting address"
    assert client.get(endpoint).json()["area"] is None
    assert client.patch(endpoint, json={"name": "   "}).status_code == 422
    assert client.patch(endpoint, json={"name": "Valid", "message_text": "overwrite"}).status_code == 422
    history = next(row for row in client.get("/outreach?limit=100").json() if row["id"] == sent["id"])
    assert history["message_text"] == payload["message_text"]
    assert history["email"]["recipient"] == payload["recipient"]
    assert history["email"]["subject"] == payload["subject"]
    assert history["sent_at"] == sent["sent_at"]
    assert state["send_calls"] == 1


@pytest.mark.parametrize("body", ["No trailing newline", "  Café café!\n\n", "First\r\nSecond"])
def test_mime_encoding_preserves_exact_approved_body(body):
    raw = gmail.encode_email("creator@example.com", "hello@example.com", "A café collaboration", body, "<test@example.com>")
    message = BytesParser(policy=policy.default).parsebytes(base64.urlsafe_b64decode(raw))
    assert message.get_content() == body
    assert message["Subject"] == "A café collaboration"


@pytest.mark.parametrize("outcome,expected", [("timeout", "email_unknown"), ("denied", "email_failed")])
def test_gmail_failure_never_claims_sent_or_retries(setup, outcome, expected):
    client, payload, state, _, _ = setup
    identity = client.post("/outreach/email/approve", json=payload).json()["id"]
    state["outcome"] = outcome
    endpoint = f"/outreach/{identity}/email/send"
    response = client.post(endpoint, json={"approved": True})
    assert response.json()["status"] == expected
    assert response.json()["sent_at"] is None
    assert client.post(endpoint, json={"approved": True}).status_code == 409
    assert state["send_calls"] == 1


def test_revoked_token_leaves_email_approved_and_unsent(setup):
    client, payload, state, _, _ = setup
    identity = client.post("/outreach/email/approve", json=payload).json()["id"]
    state["token_fail"] = True
    assert client.post(f"/outreach/{identity}/email/send", json={"approved": True}).status_code == 401
    assert state["send_calls"] == 0


@pytest.mark.parametrize("changes", [{"approved": False}, {"verified_public_business_email": False}, {"recipient": "cafe.sg"}, {"subject": "Bad\r\nBcc: other@example.com"}, {"message_text": "   "}, {"source_url": "http://127.0.0.1/contact"}, {"source_url": "https://unrelated.example/contact"}, {"recipient": "not-on-source@example.com"}])
def test_approval_rejects_unverified_or_invalid_inputs(setup, changes):
    client, payload, state, _, _ = setup
    assert client.post("/outreach/email/approve", json=payload | changes).status_code == 422
    assert state["send_calls"] == 0


def test_connection_uses_state_cookie_and_encrypts_refresh_token(setup):
    client, _, state, connection, cipher = setup
    response = client.post("/gmail/connect")
    params = parse_qs(urlsplit(response.json()["authorization_url"]).query)
    assert params["scope"] == ["openid email " + gmail.SEND_SCOPE]
    assert params["code_challenge_method"] == ["S256"]
    assert "HttpOnly" in response.headers["set-cookie"]
    callback = client.get("/gmail/callback", params={"state": params["state"][0], "code": "fake-code"}, follow_redirects=False)
    assert callback.status_code == 303
    with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
        stored = session.get(GmailAccount, 1).encrypted_refresh_token
        assert stored != "fake-refresh"
        assert cipher.decrypt(stored.encode()) == b"fake-refresh"
    assert state["send_calls"] == 0
    assert client.get("/gmail/status").json()["email"] == "creator@example.com"


def test_bad_state_and_wrong_origin_cannot_connect_or_send(setup):
    client, payload, state, _, _ = setup
    assert client.get("/gmail/callback?state=wrong&code=fake").status_code == 400
    assert state["token_calls"] == 0
    assert client.post("/gmail/connect", headers={"Origin": "https://untrusted.example"}).status_code == 403
    assert client.post("/outreach/email/approve", json=payload, headers={"Origin": "https://untrusted.example"}).status_code == 403
    assert state["send_calls"] == 0


def test_daily_approval_limit_is_enforced(setup, monkeypatch):
    client, payload, state, connection, _ = setup
    with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
        current = session.scalar(select(func.count(ApprovedEmail.id)).where(ApprovedEmail.approved_at >= datetime.now(timezone.utc) - timedelta(hours=24)))
    monkeypatch.setenv("GMAIL_DAILY_SEND_LIMIT", str(current + 1))
    assert client.post("/outreach/email/approve", json=payload).status_code == 201
    assert client.post("/outreach/email/approve", json=payload | {"google_place_id": f"other-{uuid4()}"}).status_code == 429
    assert state["send_calls"] == 0


def test_daily_send_limit_applies_to_previously_approved_drafts(setup, monkeypatch):
    client, payload, state, connection, _ = setup
    first = client.post("/outreach/email/approve", json=payload).json()["id"]
    second = client.post("/outreach/email/approve", json=payload | {"google_place_id": f"other-{uuid4()}"}).json()["id"]
    with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
        current = session.scalar(select(func.count(ApprovedEmail.id)).where(ApprovedEmail.attempted_at >= datetime.now(timezone.utc) - timedelta(hours=24)))
    monkeypatch.setenv("GMAIL_DAILY_SEND_LIMIT", str(current + 1))
    assert client.post(f"/outreach/{first}/email/send", json={"approved": True}).json()["status"] == "sent"
    assert client.post(f"/outreach/{second}/email/send", json={"approved": True}).status_code == 429
    assert state["send_calls"] == 1
