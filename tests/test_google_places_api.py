import httpx2
import pytest
from fastapi import status
from fastapi.testclient import TestClient

from automate_food_places_outreach.api import app
from automate_food_places_outreach.dependencies import (
    get_http_client,
    require_google_places_api_key,
)


client = TestClient(app)


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
            request=request,
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


def test_preview_google_places_rejects_missing_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(
        "GOOGLE_PLACES_API_KEY",
        raising=False,
    )

    response = client.post(
        "/discovery/google-places/preview",
        json={
            "text_query": "cafés in Singapore",
        },
    )

    assert (
        response.status_code
        == status.HTTP_503_SERVICE_UNAVAILABLE
    )
    assert response.json() == {
        "detail": "Google Places is not configured.",
    }
