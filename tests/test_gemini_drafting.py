"""No live Gemini calls: inspect grounded single-request writing with MockTransport."""
import json
from uuid import uuid4

import httpx2
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from automate_food_places_outreach.api import app
from automate_food_places_outreach.database import engine
from automate_food_places_outreach.dependencies import get_http_client, get_session
from automate_food_places_outreach.models.drafting import OutreachDraft
from automate_food_places_outreach.models.restaurant import Restaurant
from automate_food_places_outreach.models.outreach import OutreachAttempt


@pytest.fixture
def drafting(monkeypatch):
    connection = engine.connect()
    transaction = connection.begin()
    monkeypatch.setenv("GEMINI_API_KEY", "fake-gemini-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    monkeypatch.setenv("GEMINI_DAILY_GENERATION_LIMIT", "1000")
    state = {"requests": [], "writing": {
        "subject": "A TikTok collaboration with Confirmed Café",
        "personalised_paragraph": "I’d love to introduce your specialty coffee and brunch menu to people exploring food on TikTok.",
        "used_fact_ids": ["category", "detail"],
    }}

    def google(request):
        assert request.url.host == "generativelanguage.googleapis.com"
        assert request.headers["x-goog-api-key"] == "fake-gemini-key"
        assert "key=" not in str(request.url)
        payload = json.loads(request.content)
        state["requests"].append(payload)
        assert "tools" not in payload and "toolConfig" not in payload
        context = json.loads(payload["contents"][0]["parts"][0]["text"])
        assert "creator_profile" in context
        assert set(context["creator_profile"]) == {"creator_name", "tiktok_url", "views_over", "shares_over", "minimum_video_views"}
        assert "restaurant_facts" in context
        if state.get("timeout"):
            raise httpx2.ReadTimeout("fake timeout", request=request)
        if state.get("http_error"):
            return httpx2.Response(state["http_error"], json={"error": "secret provider detail"})
        content = state.get("tool_content", {"role": "model", "parts": [{"text": state.get("text", json.dumps(state["writing"]))}]})
        return httpx2.Response(200, json={"candidates": [{"finishReason": state.get("finish_reason", "STOP"), "content": content}]})

    async def http_client():
        async with httpx2.AsyncClient(transport=httpx2.MockTransport(google)) as client:
            yield client

    def database():
        with Session(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False) as session:
            yield session

    monkeypatch.setitem(app.dependency_overrides, get_session, database)
    monkeypatch.setitem(app.dependency_overrides, get_http_client, http_client)
    client = TestClient(app, headers={"Origin": "http://127.0.0.1:5173"})
    assert client.patch("/creator-profile", json={"statistics_confirmed": True}).status_code == 200
    inputs = {"request_id": str(uuid4()), "google_place_id": f"draft-test-{uuid4()}",
        "restaurant_name": "Confirmed Café", "business_kind": "cafe", "channel": "email",
        "feature_detail": "your specialty coffee and brunch menu", "source_url": "https://example.com/menu",
        "facts_confirmed": True}
    try:
        yield client, inputs, state, connection
    finally:
        client.close()
        transaction.rollback()
        connection.close()


def test_one_writing_request_uses_creator_profile_and_preserves_signature(drafting):
    client, inputs, state, connection = drafting
    response = client.post("/outreach/drafts/generate", json=inputs)
    assert response.status_code == 201, response.text
    body = response.json()
    assert len(state["requests"]) == 1
    assert state["requests"][0]["generationConfig"]["responseMimeType"] == "application/json"
    assert "personalised_paragraph" in state["requests"][0]["generationConfig"]["responseJsonSchema"]["properties"]
    assert body["subject"] == state["writing"]["subject"]
    assert state["writing"]["personalised_paragraph"] in body["message_text"]
    assert body["prompt_version"] == "grounded-writing-v2"
    assert body["message_text"].startswith("Hi Confirmed Café team,")
    assert "over 146,000 views and more than 600 shares" in body["message_text"]
    assert "every video receiving at least 1,000 views" in body["message_text"]
    assert "specialty coffee and brunch menu" in body["message_text"]
    assert "https://www.tiktok.com/@bbbrrr9" in body["message_text"]
    assert "hosted meal disclosed? No creator fee." in body["message_text"]
    assert body["message_text"].endswith("Best,\nBryan's dining room")
    assert client.get(f"/outreach/drafts/{body['id']}").json() == body
    with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
        draft = session.get(OutreachDraft, body["id"])
        assert draft.status == "ready"
        assert draft.factual_inputs["restaurant"]["source_url"] == inputs["source_url"]
        assert draft.factual_inputs["creator"]["views_over"] == 146000
        assert draft.model_selection == state["writing"]
        assert session.scalar(select(Restaurant).where(Restaurant.google_place_id == inputs["google_place_id"])) is None
    # Same request is replay-safe: no second paid generation.
    assert client.post("/outreach/drafts/generate", json=inputs).json() == body
    assert len(state["requests"]) == 1
    assert client.post("/outreach/drafts/generate", json={**inputs, "restaurant_name": "Changed"}).status_code == 409


def test_category_fallback_does_not_invent_menu_details(drafting):
    client, inputs, state, _ = drafting
    inputs["feature_detail"] = ""
    state["writing"]["used_fact_ids"] = ["category"]
    state["writing"]["personalised_paragraph"] = "I’d love to feature your café in a TikTok food review and introduce it to people exploring places to eat."
    response = client.post("/outreach/drafts/generate", json=inputs)
    assert response.status_code == 201
    assert "feature your café" in response.json()["message_text"]
    assert "brunch" not in response.json()["message_text"]


def test_updated_creator_profile_is_used_in_prompt_and_fixed_message(drafting):
    client, inputs, state, _ = drafting
    updated = {"creator_name": "Bryan", "tiktok_url": "https://www.tiktok.com/@bbbrrr9",
        "views_over": 200000, "shares_over": 900, "minimum_video_views": 1200, "statistics_confirmed": True}
    assert client.patch("/creator-profile", json=updated).status_code == 200
    response = client.post("/outreach/drafts/generate", json=inputs)
    assert response.status_code == 201
    context = json.loads(state["requests"][0]["contents"][0]["parts"][0]["text"])
    assert context["creator_profile"]["views_over"] == 200000
    assert "over 200,000 views and more than 900 shares" in response.json()["message_text"]
    assert "at least 1,200 views" in response.json()["message_text"]
    assert response.json()["message_text"].endswith("Best,\nBryan's dining room")


@pytest.mark.parametrize("paragraph", [
    "I’d love to feature your café and share it with my followers.",
    "I’d love to introduce your café to my TikTok audience.",
])
def test_ordinary_audience_wording_is_allowed(drafting, paragraph):
    client, inputs, state, _ = drafting
    state["writing"]["personalised_paragraph"] = paragraph
    state["writing"]["used_fact_ids"] = ["category"]
    response = client.post("/outreach/drafts/generate", json=inputs)
    assert response.status_code == 201, response.text
    assert paragraph in response.json()["message_text"]
    assert response.json()["message_text"].endswith("Best,\nBryan's dining room")


@pytest.mark.parametrize("paragraph", [
    "I’d love to feature your café for my 50,000 followers.",
    "I’d love to feature your café for my thousands of followers.",
    "I guarantee your café will get more customers.",
    "My videos generate a million views for businesses like your café.",
])
def test_statistics_and_guarantees_are_still_rejected(drafting, paragraph):
    client, inputs, state, _ = drafting
    state["writing"]["personalised_paragraph"] = paragraph
    state["writing"]["used_fact_ids"] = ["category"]
    assert client.post("/outreach/drafts/generate", json=inputs).status_code == 502


def test_no_provider_retry_and_no_template_selection_fallback(drafting):
    client, inputs, state, _ = drafting
    state["text"] = json.dumps({"sentence_id": "detail", "subject_style": "collaboration"})
    assert client.post("/outreach/drafts/generate", json=inputs).status_code == 502
    assert len(state["requests"]) == 1


@pytest.mark.parametrize("scenario", ["unexpected_tool", "malformed", "invented_fact_id", "unavailable_detail", "extra_number", "invented_stats", "extra_url", "subject_newline", "blank_paragraph", "blocked", "network", "quota", "billing"])
def test_unsafe_or_failed_generation_never_fills_or_sends(drafting, scenario):
    client, inputs, state, connection = drafting
    if scenario == "unexpected_tool":
        state["tool_content"] = {"role": "model", "parts": [{"functionCall": {
            "name": "send_email", "args": {"recipient": "someone@example.com"}}}]}
    if scenario == "malformed":
        state["text"] = "not-json"
    if scenario == "invented_fact_id":
        state["writing"]["used_fact_ids"] = ["invented_menu"]
    if scenario == "unavailable_detail":
        inputs["feature_detail"] = ""
    if scenario == "extra_number":
        state["writing"]["personalised_paragraph"] = "I’d love to feature your café with 3 videos."
    if scenario == "invented_stats":
        state["writing"]["personalised_paragraph"] = "I have 50,000 followers who will love your café."
    if scenario == "extra_url":
        state["writing"]["personalised_paragraph"] = "See my account at https://invented.example.com."
    if scenario == "subject_newline":
        state["writing"]["subject"] = "Hello\nBcc: other@example.com"
    if scenario == "blank_paragraph":
        state["writing"]["personalised_paragraph"] = "   "
    if scenario == "blocked":
        state["finish_reason"] = "SAFETY"
    if scenario == "network":
        state["timeout"] = True
    if scenario == "quota":
        state["http_error"] = 429
    if scenario == "billing":
        state["http_error"] = 402
    with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
        before = session.scalar(select(func.count(OutreachAttempt.id)))
    response = client.post("/outreach/drafts/generate", json=inputs)
    assert response.status_code in {429, 502, 503}
    assert "secret provider detail" not in response.text
    if scenario == "billing":
        assert "prepaid credit balance" in response.json()["detail"]
    with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
        draft = session.scalar(select(OutreachDraft).where(OutreachDraft.request_id == inputs["request_id"]))
        assert draft.status == "failed"
        assert draft.message_text is None
        assert session.scalar(select(func.count(OutreachAttempt.id))) == before
    count = len(state["requests"])
    assert client.post("/outreach/drafts/generate", json=inputs).status_code == 409
    assert len(state["requests"]) == count


def test_requires_confirmations_and_backend_key(drafting, monkeypatch):
    client, inputs, state, _ = drafting
    assert client.patch("/creator-profile", json={"statistics_confirmed": False}).status_code == 422
    assert client.patch("/creator-profile", json={"statistics_confirmed": True, "views_over": -1}).status_code == 422
    assert client.post("/outreach/drafts/generate", json={**inputs, "facts_confirmed": False}).status_code == 422
    monkeypatch.delenv("GEMINI_API_KEY")
    assert client.get("/gemini/status").json()["configured"] is False
    assert client.post("/outreach/drafts/generate", json=inputs).status_code == 503
    assert not state["requests"]


def test_failed_attempts_count_toward_generation_limit(drafting, monkeypatch):
    client, inputs, state, _ = drafting
    # Count real drafts without deleting them; this test's reservation uses one slot.
    from datetime import datetime, timedelta, timezone
    with Session(bind=drafting[3], join_transaction_mode="create_savepoint") as session:
        baseline = session.scalar(select(func.count(OutreachDraft.id)).where(
            OutreachDraft.created_at >= datetime.now(timezone.utc) - timedelta(hours=24)))
    monkeypatch.setenv("GEMINI_DAILY_GENERATION_LIMIT", str(baseline + 1))
    state["timeout"] = True
    assert client.post("/outreach/drafts/generate", json=inputs).status_code == 503
    assert client.post("/outreach/drafts/generate", json={**inputs, "request_id": str(uuid4())}).status_code == 429
    assert len(state["requests"]) == 1


def test_unknown_browser_origin_cannot_generate(drafting):
    client, inputs, state, _ = drafting
    response = client.post("/outreach/drafts/generate", json=inputs, headers={"Origin": "https://untrusted.example"})
    assert response.status_code == 403
    assert not state["requests"]
