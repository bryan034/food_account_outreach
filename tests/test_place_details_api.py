import httpx2
import pytest
from fastapi.testclient import TestClient

from automate_food_places_outreach.api import app
from automate_food_places_outreach.dependencies import get_http_client, require_google_places_api_key


@pytest.fixture
def mock_google(monkeypatch):
    def configure(handler):
        async def override_client():
            async with httpx2.AsyncClient(transport=httpx2.MockTransport(handler)) as client:
                yield client

        monkeypatch.setitem(app.dependency_overrides, get_http_client, override_client)
        monkeypatch.setitem(app.dependency_overrides, require_google_places_api_key, lambda: "test-key")
    return configure


def test_details_endpoint_returns_python_field_names(mock_google):
    def google(request):
        assert request.headers["X-Goog-Api-Key"] == "test-key"
        return httpx2.Response(200, json={
            "id": "test-place", "displayName": {"text": "Test Café"},
            "regularOpeningHours": {"weekdayDescriptions": ["Monday: Closed"]},
        })

    mock_google(google)
    response = TestClient(app).get("/discovery/google-places/test-place/details")
    assert response.status_code == 200
    assert response.json()["regular_opening_hours"]["weekday_descriptions"] == ["Monday: Closed"]
    assert "regularOpeningHours" not in response.json()


def test_outreach_name_lookup_requests_only_name_and_identity(mock_google):
    def google(request):
        assert request.headers["X-Goog-FieldMask"] == "id,displayName"
        return httpx2.Response(200, json={"id": "test-place", "displayName": {"text": "Test Café"}})

    mock_google(google)
    response = TestClient(app).get("/discovery/google-places/test-place/details?name_only=true")
    assert response.status_code == 200
    assert response.json()["display_name"]["text"] == "Test Café"
    assert response.json()["regular_opening_hours"] is None


@pytest.mark.parametrize("kind,expected", [("http", 502), ("invalid_json", 502), ("invalid_model", 502), ("network", 503)])
def test_details_endpoint_translates_upstream_failures(mock_google, kind, expected):
    def google(request):
        if kind == "http":
            return httpx2.Response(403, json={"error": "denied"})
        if kind == "invalid_json":
            return httpx2.Response(200, text="not JSON")
        if kind == "invalid_model":
            return httpx2.Response(200, json={"id": "test-place"})
        raise httpx2.ConnectError("unreachable", request=request)

    mock_google(google)
    assert TestClient(app).get("/discovery/google-places/test-place/details").status_code == expected


def test_local_browser_origin_is_allowed_but_unknown_origin_is_not():
    client = TestClient(app)
    headers = {"Origin": "http://127.0.0.1:5173", "Access-Control-Request-Method": "PATCH", "Access-Control-Request-Headers": "content-type"}
    response = client.options("/outreach/1/status", headers=headers)
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == headers["Origin"]
    denied = client.options("/outreach/1/status", headers=headers | {"Origin": "https://untrusted.example"})
    assert denied.status_code == 400
    assert "access-control-allow-origin" not in denied.headers
