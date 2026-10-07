from uuid import uuid4

import httpx2
import pytest
from sqlalchemy import delete, func, select
from fastapi import status
from fastapi.testclient import TestClient

from automate_food_places_outreach.api import app
from automate_food_places_outreach.database import SessionFactory
from automate_food_places_outreach.models.restaurant import Restaurant
from automate_food_places_outreach.models.outreach import OutreachAttempt
from automate_food_places_outreach.dependencies import (
    get_http_client,
    require_google_places_api_key,
)


client = TestClient(app)


@pytest.fixture
def fake_google_search(monkeypatch: pytest.MonkeyPatch):
    place_ids = [f"import-test-{uuid4()}", f"import-test-{uuid4()}"]
    places = [
        {"id": place_ids[0], "displayName": {"text": "First Café"}},
        {"id": place_ids[1], "displayName": {"text": "Second Café"}},
    ]

    def fake_google(_request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={"places": places})

    async def override_http_client():
        async with httpx2.AsyncClient(
            transport=httpx2.MockTransport(fake_google),
        ) as fake_client:
            yield fake_client

    def override_api_key() -> str:
        return "test-api-key"

    monkeypatch.setitem(
        app.dependency_overrides, get_http_client, override_http_client,
    )
    monkeypatch.setitem(
        app.dependency_overrides,
        require_google_places_api_key,
        override_api_key,
    )
    try:
        yield place_ids, places
    finally:
        with SessionFactory.begin() as session:
            session.execute(
                delete(OutreachAttempt).where(
                    OutreachAttempt.restaurant_id.in_(
                        select(Restaurant.id).where(Restaurant.google_place_id.in_(place_ids))
                    )
                )
            )
            session.execute(
                delete(Restaurant).where(Restaurant.google_place_id.in_(place_ids))
            )


@pytest.mark.parametrize("history_status", ["sent", "scheduling", "rejected", "tasting", "completed"])
def test_new_leads_excludes_contacted_but_keeps_uncontacted(fake_google_search, history_status) -> None:
    place_ids, _places = fake_google_search
    with SessionFactory.begin() as session:
        restaurants = [Restaurant(google_place_id=place_id, name="User-entered name") for place_id in place_ids]
        session.add_all(restaurants)
        session.flush()
        session.add(OutreachAttempt(
            restaurant_id=restaurants[0].id, channel="tiktok",
            status=history_status, message_text="Exact historical message",
        ))
    response = client.post(
        "/discovery/google-places/new-leads",
        json={"text_query": "cafés in Singapore"},
    )
    assert response.status_code == 200
    assert [place["id"] for place in response.json()["places"]] == [place_ids[1]]
    with SessionFactory() as session:
        count = session.scalar(
            select(func.count()).select_from(Restaurant).where(
                Restaurant.google_place_id.in_(place_ids)
            )
        )
    assert count == 2
    assert client.post("/discovery/google-places/import", json={"text_query": "cafés"}).status_code == 404


def test_preview_google_places() -> None:
    def fake_google(_request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            status.HTTP_200_OK,
            json={
                "places": [
                    {
                        "id": "place-123",
                        "displayName": {
                            "text": "Example Café",
                        },
                    }
                ]
            },
        )

    async def override_http_client():
        transport = httpx2.MockTransport(fake_google)

        async with httpx2.AsyncClient(
            transport=transport,
        ) as fake_client:
            yield fake_client

    def override_api_key() -> str:
        return "test-api-key"

    app.dependency_overrides[get_http_client] = (
        override_http_client
    ) 
    app.dependency_overrides[require_google_places_api_key] = (
        override_api_key
    )
    # during test, FastAPI subs client with fake client and api key 
    # app.dependency_overrides is a dictionary owned by FastAPI application
    try:
        response = client.post(
            "/discovery/google-places/preview",
            json={
                "text_query": "cafés in Singapore",
            },
        )
    finally:
        app.dependency_overrides.pop(get_http_client, None)
        # removes get_http_client key and returns its value
        # None is the fallback value if key is already absent
        app.dependency_overrides.pop(
            require_google_places_api_key,
            None,
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["places"][0]["id"] == "place-123"
    assert (
        response.json()["places"][0]["display_name"]["text"]
        == "Example Café"
    )


def test_preview_google_places_translates_google_http_error() -> None:
    def fake_google(_request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            status.HTTP_403_FORBIDDEN,
            json={
                "error": {
                    "message": "Invalid API key",
                }
            },
        )

    async def override_http_client():
        transport = httpx2.MockTransport(fake_google)

        async with httpx2.AsyncClient(
            transport=transport,
        ) as fake_client:
            yield fake_client

    def override_api_key() -> str:
        return "invalid-test-key"

    app.dependency_overrides[get_http_client] = (
        override_http_client
    )
    app.dependency_overrides[require_google_places_api_key] = (
        override_api_key
    )

    try:
        response = client.post(
            "/discovery/google-places/preview",
            json={
                "text_query": "cafés in Singapore",
            },
        )
    finally:
        app.dependency_overrides.pop(get_http_client, None)
        app.dependency_overrides.pop(
            require_google_places_api_key,
            None,
        )

    assert response.status_code == status.HTTP_502_BAD_GATEWAY
    assert response.json() == {
        "detail": "Google Places returned an error.",
    }


def test_preview_google_places_translates_connection_error() -> None:
    def unreachable_google(
        request: httpx2.Request,
    ) -> httpx2.Response:
        raise httpx2.ConnectError(
            "Connection failed",
            request=request, #records which request failed
        )

    async def override_http_client():
        transport = httpx2.MockTransport(unreachable_google)

        async with httpx2.AsyncClient(
            transport=transport,
        ) as fake_client:
            yield fake_client

    def override_api_key() -> str:
        return "test-api-key"

    app.dependency_overrides[get_http_client] = (
        override_http_client
    )
    app.dependency_overrides[require_google_places_api_key] = (
        override_api_key
    )

    try:
        response = client.post(
            "/discovery/google-places/preview",
            json={
                "text_query": "cafés in Singapore",
            },
        )
    finally:
        app.dependency_overrides.pop(get_http_client, None)
        app.dependency_overrides.pop(
            require_google_places_api_key,
            None,
        )

    assert (
        response.status_code
        == status.HTTP_503_SERVICE_UNAVAILABLE
    )
    assert response.json() == {
        "detail": "Google Places is unavailable.",
    }
