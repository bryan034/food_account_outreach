from pytest import MonkeyPatch 
# MonkeyPatch pytest tool that temporarily changes sth during 1 test and automatically restores it afterward
import pytest

from automate_food_places_outreach.config import (
    get_google_places_api_key,
)


def test_get_google_places_api_key(monkeypatch: MonkeyPatch) -> None:
    # monkeypatch is a param that doesnt need to be supplied ourselves. Pytest recognises name and injects ready to use object before running the test 
    # method is called a pytest fixture
    monkeypatch.setenv( #temporarily sets env variable for this test, does not edit .env file
        "GOOGLE_PLACES_API_KEY",
        "test-api-key",
    )
    # during the test: GOOGLE_PLACES_API_KEY = test-api-key

    result = get_google_places_api_key()

    assert result == "test-api-key"

def test_get_google_places_api_key_rejects_missing_value(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.delenv(
        "GOOGLE_PLACES_API_KEY",
        raising=False, #do not raise error if it was already missing
    )

    with pytest.raises(
        RuntimeError,
        match="GOOGLE_PLACES_API_KEY is not set", #verifies error contains this message
    ):
        get_google_places_api_key()