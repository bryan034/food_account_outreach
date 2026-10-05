from typing import Annotated
from pydantic import BaseModel, Field, StringConstraints

SearchQuery = Annotated[ #attaches pydantic validation rules to that str
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=200,
    ),
]

class GoogleLocalizedText(BaseModel):
    text: str


class GooglePlace(BaseModel):
    id: str
    display_name: GoogleLocalizedText = Field(alias="displayName")
    formatted_address: str | None = Field(
        default=None,
        alias="formattedAddress",
    )
    primary_type: str | None = Field(
        default=None,
        alias="primaryType",
    )
    business_status: str | None = Field(
        default=None,
        alias="businessStatus",
    )

class GoogleTextSearchResponse(BaseModel):
    places: list[GooglePlace] = Field(default_factory=list)
    next_page_token: str | None = Field(
        default=None,
        alias="nextPageToken",
    )

class GoogleTextSearchRequest(BaseModel):
    text_query: SearchQuery