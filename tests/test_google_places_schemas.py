import pytest
from pydantic import ValidationError
from automate_food_places_outreach.schemas.google_places import (
    GoogleTextSearchResponse,
    GoogleTextSearchRequest,
)


def test_google_text_search_response_parses_places() -> None:
    raw_response = {
        "places": [
            {
                "id": "abc123",
                "displayName": {"text": "Example Café"},
                "formattedAddress": "1 Example Street, Singapore",
            },
        ],
        "nextPageToken": "page-two",
    }

    response = GoogleTextSearchResponse.model_validate(raw_response)

    assert response.places[0].id == "abc123"
    assert response.places[0].display_name.text == "Example Café"
    assert response.places[0].formatted_address == "1 Example Street, Singapore"
    assert response.next_page_token == "page-two"

def test_google_text_search_request_strips_whitespace() -> None:
    request = GoogleTextSearchRequest(
        text_query="  cafés in Singapore  ",
    )

    assert request.text_query == "cafés in Singapore"


def test_google_text_search_request_rejects_blank_query() -> None:
    with pytest.raises(ValidationError):
        GoogleTextSearchRequest(text_query="   ")