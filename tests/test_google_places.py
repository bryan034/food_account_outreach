import asyncio #lib for writing concurrent code using async/await syntax

import httpx2
import json
import pytest
from automate_food_places_outreach.google_places import search_places


def test_search_places_parses_successful_response() -> None:
    # when client.post() creates req, MockTransport does this internally: response = fake_google(request)
    # argument will be added when calling the callback function, need to put a param to act as placeholder else TypeError will surface
    # def fake_google(_request: httpx2.Request) -> httpx2.Response:  
    #     # _request leading underscore means argument required by MockTransport, but function does not currently use it
    #     # just a naming convention, no special behaviour
    #     # if param removed, def fake_google(): test wld fail as MockTransport calls function with 1 request argument
    #     return httpx2.Response(
    #         200,
    #         json={
    #             "places": [
    #                 {
    #                     "id": "place-123",
    #                     "displayName": {"text": "Example Café"},
    #                 }
    #             ]
    #         },
    #     )
    def fake_google(request: httpx2.Request) -> httpx2.Response:
        assert request.method == "POST"
        assert str(request.url) == (
            "https://places.googleapis.com/v1/places:searchText"
        )
        assert request.headers["X-Goog-Api-Key"] == "test-api-key"
        assert json.loads(request.content) == {
            "textQuery": "cafés in Singapore"
        }

        return httpx2.Response(
            200,
            json={
                "places": [
                    {
                        "id": "place-123",
                        "displayName": {"text": "Example Café"},
                    }
                ]
            },
        )

    async def run_search():
        transport = httpx2.MockTransport(fake_google) #MockTransport redirects http req to fake_google()

        async with httpx2.AsyncClient(transport=transport) as client:
            # transport=transport tells client to use MockTransport to handle reqyests instead of normal internet transport
            # left transport: AsyncClient param name
            # right: local variable holding MockTransport
            return await search_places(
                client,
                api_key="test-api-key",
                text_query="cafés in Singapore",
            )
            
        # pydantic validates fake JSON returned

    result = asyncio.run(run_search())  
    # asyncio.run(): tldr lets async function run like a normal function
    # 1. Creates an event loop.
    # 2. Runs the run_search() coroutine.
    # 3. Lets it pause at each await.
    # 4. Continues until it finishes.
    # 5. Closes the event loop.
    # 6. Returns the value returned by run_search().

    assert result.places[0].id == "place-123"
    assert result.places[0].display_name.text == "Example Café"

def test_search_places_raises_for_http_error() -> None:
    def fake_google(_request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            403,
            json={
                "error": {
                    "message": "Invalid API key",
                }
            },
        )

    async def run_search():
        transport = httpx2.MockTransport(fake_google)

        async with httpx2.AsyncClient(transport=transport) as client:
            return await search_places(
                client,
                api_key="invalid-test-key",
                text_query="cafés in Singapore",
            )

    with pytest.raises(httpx2.HTTPStatusError) as error: #must raise HTTPStatusError. if no exception occurs, test fails
        asyncio.run(run_search())

    assert error.value.response.status_code == 403