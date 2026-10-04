import os


def get_google_places_api_key() -> str:
    api_key = os.environ.get("GOOGLE_PLACES_API_KEY")

    if not api_key:
        raise RuntimeError("GOOGLE_PLACES_API_KEY is not set")

    return api_key