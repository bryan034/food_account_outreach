import httpx2 #provides async http client, replaces requests

from automate_food_places_outreach.schemas.google_places import (
    GoogleTextSearchResponse,
)


TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"

# lists the fields we want returned into 1 comma separated string
# wo field mask, google doesnt know which parts of each place we need
# narrow mask avoids downloading unnecessary data and helps control api cost
FIELD_MASK = ",".join(
    [
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.primaryType",
        "places.businessStatus",
        "nextPageToken",
    ]
)


# fn pauses while waiting for google
async def search_places(
    client: httpx2.AsyncClient,
    *,
    api_key: str,
    text_query: str,
) -> GoogleTextSearchResponse:
    response = await client.post(
        TEXT_SEARCH_URL,
        headers={
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": FIELD_MASK,
        },
        json={"textQuery": text_query},
    )

    response.raise_for_status()

    return GoogleTextSearchResponse.model_validate(response.json())