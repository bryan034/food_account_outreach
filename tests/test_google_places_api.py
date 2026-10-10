from uuid import uuid4

import httpx2
import pytest
from sqlalchemy import delete, func, select
from fastapi import status
from fastapi.testclient import TestClient

from automate_food_places_outreach.api import app
from automate_food_places_outreach.database import SessionFactory
from automate_food_places_outreach.models.restaurant import Restaurant
from automate_food_places_outreach.dependencies import (
    get_http_client,
    require_google_places_api_key,
)


client = TestClient(app)


@pytest.fixture # registers reusable test setup. Pytest reuns it when test requests fake_import_google param
def fake_import_google(monkeypatch: pytest.MonkeyPatch):
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

    monkeypatch.setitem( #temp inserts dependency overrides into fastapi dct
        app.dependency_overrides, get_http_client, override_http_client,
    )
    monkeypatch.setitem(
        app.dependency_overrides,
        require_google_places_api_key,
        override_api_key,
    )
    try:
        yield place_ids, places #gives fake data to test and pauses the fixture 
    finally:
        with SessionFactory.begin() as session:
            session.execute(
                delete(Restaurant).where(Restaurant.google_place_id.in_(place_ids))
            )


def test_import_google_places_deduplicates_results(fake_import_google) -> None:
    place_ids, _places = fake_import_google
    first = client.post(
        "/discovery/google-places/import",
        json={"text_query": "cafés in Singapore"},
    )
    second = client.post(
        "/discovery/google-places/import",
        json={"text_query": "cafés in Singapore"},
    )
    assert first.status_code == second.status_code == 200
    assert first.json()["created_count"] == 2
    assert first.json()["updated_count"] == 0
    assert second.json()["created_count"] == 0
    assert second.json()["updated_count"] == 2
    assert first.json()["restaurant_ids"] == second.json()["restaurant_ids"]
    with SessionFactory() as session:
        count = session.scalar(
            select(func.count()).select_from(Restaurant).where(
                Restaurant.google_place_id.in_(place_ids)
            )
        )
    assert count == 2


def test_import_google_places_rolls_back_failed_batch(fake_import_google) -> None:
    place_ids, places = fake_import_google
    places[1]["displayName"]["text"] = "x" * 256
    response = client.post(
        "/discovery/google-places/import",
        json={"text_query": "cafés in Singapore"},
    )
    assert response.status_code == 502
    with SessionFactory() as session:
        count = session.scalar(
            select(func.count()).select_from(Restaurant).where(
                Restaurant.google_place_id.in_(place_ids)
            )
        )
    assert count == 0


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
