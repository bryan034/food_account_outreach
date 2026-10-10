from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from automate_food_places_outreach.api import app
from automate_food_places_outreach.database import SessionFactory
from automate_food_places_outreach.models.outreach import OutreachAttempt
from automate_food_places_outreach.models.restaurant import Restaurant
from automate_food_places_outreach.models.tasting import Tasting


client = TestClient(app)


def tasting_plan(**changes):
    plan = {"scheduled_at": "2026-11-01T19:00:00+08:00", "address": "42 Test Road, Singapore", "notes": "Vegetarian tasting"}
    return plan | changes


@pytest.fixture #defines reusable setup and teardown code, dependency injection, and state management for tests in pytest
def restaurant_id():
    with SessionFactory.begin() as session:
        restaurant = Restaurant(google_place_id=f"outreach-test-{uuid4()}", name="My café record")
        session.add(restaurant)
        session.flush()
        identity = restaurant.id
    try:
        yield identity
    finally:
        with SessionFactory.begin() as session:
            session.execute(delete(Tasting).where(Tasting.outreach_id.in_(
                select(OutreachAttempt.id).where(OutreachAttempt.restaurant_id == identity)
            )))
            session.execute(delete(OutreachAttempt).where(OutreachAttempt.restaurant_id == identity))
            session.execute(delete(Restaurant).where(Restaurant.id == identity))


def mark_sent(restaurant_id, **changes):
    payload = dict(restaurant_id=restaurant_id, channel="tiktok", message_text="Hi!\nExact sent message.", confirmed_sent=True)
    payload.update(changes)
    return client.post("/outreach/mark-sent", json=payload)


def test_outreach_lifecycle_and_duplicate_protection(restaurant_id):
    response = mark_sent(restaurant_id)
    assert response.status_code == 201
    attempt_id = response.json()["id"]
    assert response.json()["message_text"] == "Hi!\nExact sent message."
    assert response.json()["sent_at"]
    assert mark_sent(restaurant_id, channel="instagram").status_code == 409
    assert client.delete(f"/restaurants/{restaurant_id}").status_code == 409
    assert client.patch(f"/outreach/{attempt_id}/status", json={"status": "completed"}).status_code == 409
    for new_status in ("scheduling", "tasting", "completed"):
        payload = {"status": new_status}
        if new_status == "tasting":
            payload["tasting"] = tasting_plan()
        response = client.patch(f"/outreach/{attempt_id}/status", json=payload)
        assert response.status_code == 200
        assert response.json()["status"] == new_status
        assert response.json()["message_text"] == "Hi!\nExact sent message."
    assert client.patch(f"/outreach/{attempt_id}/status", json={"status": "sent"}).status_code == 409
    response = client.get("/outreach?limit=100")
    assert response.status_code == 200
    # Retrieve the particular record even if older history spans multiple pages.
    with SessionFactory() as session:
        assert session.get(OutreachAttempt, attempt_id).status == "completed"


def test_mark_sent_requires_manual_confirmation(restaurant_id):
    assert mark_sent(restaurant_id, confirmed_sent=False).status_code == 422
    assert mark_sent(restaurant_id, channel="email").status_code == 422
    assert mark_sent(restaurant_id, message_text="   ").status_code == 422
    assert mark_sent(restaurant_id).status_code == 201


def test_rejected_outreach_can_be_corrected_without_duplicate_outreach(restaurant_id):
    attempt_id = mark_sent(restaurant_id).json()["id"]
    assert client.patch(f"/outreach/{attempt_id}/status", json={"status": "rejected"}).status_code == 200
    assert client.patch(f"/outreach/{attempt_id}/status", json={"status": "scheduling"}).status_code == 200
    assert mark_sent(restaurant_id).status_code == 409

def test_tasting_without_plan_does_not_change_status(restaurant_id):
    response = mark_sent(restaurant_id)
    assert response.status_code == 201

    outreach_id = response.json()["id"]
    rejected_response = client.patch(
        f"/outreach/{outreach_id}/status",
        json={"status":"rejected"},
    )

    assert rejected_response.status_code == 200

    tasting_response = client.patch(
        f"outreach/{outreach_id}/status",
        json={"status":"tasting"},
    )
    assert tasting_response.status_code == 422

    with SessionFactory() as session: 
        saved_attempt = session.get(OutreachAttempt, outreach_id)
        assert saved_attempt is not None
        assert saved_attempt.status == "rejected"


def test_tasting_persists_and_backward_corrections_preserve_history(restaurant_id):
    attempt_id = mark_sent(restaurant_id).json()["id"]
    endpoint = f"/outreach/{attempt_id}/status"
    assert client.patch(endpoint, json={"status": "scheduling"}).status_code == 200
    assert client.patch(endpoint, json={"status": "tasting", "tasting": tasting_plan(scheduled_at="2026-11-01T19:00:00")}).status_code == 422
    response = client.patch(endpoint, json={"status": "tasting", "tasting": tasting_plan()})
    assert response.status_code == 200
    assert response.json()["tasting"]["address"] == "42 Test Road, Singapore"
    with SessionFactory() as session:
        attempt = session.get(OutreachAttempt, attempt_id)
        assert attempt.tasting.scheduled_at.hour == 11  # PostgreSQL stores the same instant in UTC.
        assert attempt.tasting.notes == "Vegetarian tasting"
    for new_status in ("completed", "tasting", "scheduling", "sent"):
        response = client.patch(endpoint, json={"status": new_status})
        assert response.status_code == 200
        assert response.json()["message_text"] == "Hi!\nExact sent message."
        assert response.json()["tasting"]["notes"] == "Vegetarian tasting"
    assert mark_sent(restaurant_id).status_code == 409


def test_discovered_business_is_recorded_atomically_after_manual_send():
    place_id = f"auto-outreach-test-{uuid4()}"
    payload = {"google_place_id": place_id, "name": "My own notes label", "channel": "tiktok", "message_text": "Exact sent text", "confirmed_sent": True}
    try:
        assert client.post("/outreach/from-place/mark-sent", json=payload | {"confirmed_sent": False}).status_code == 422
        with SessionFactory() as session:
            assert session.scalar(select(Restaurant).where(Restaurant.google_place_id == place_id)) is None
        response = client.post("/outreach/from-place/mark-sent", json=payload)
        assert response.status_code == 201
        assert response.json()["message_text"] == "Exact sent text"
        restaurant_id = response.json()["restaurant_id"]
        assert client.get(f"/restaurants/{restaurant_id}").json()["name"] == "My own notes label"
        assert client.post("/outreach/from-place/mark-sent", json=payload | {"channel": "instagram"}).status_code == 409
        with SessionFactory() as session:
            assert len(session.scalars(select(Restaurant).where(Restaurant.google_place_id == place_id)).all()) == 1
            assert len(session.scalars(select(OutreachAttempt).where(OutreachAttempt.restaurant_id == restaurant_id)).all()) == 1
    finally:
        with SessionFactory.begin() as session:
            ids = select(Restaurant.id).where(Restaurant.google_place_id == place_id)
            session.execute(delete(OutreachAttempt).where(OutreachAttempt.restaurant_id.in_(ids)))
            session.execute(delete(Restaurant).where(Restaurant.google_place_id == place_id))
