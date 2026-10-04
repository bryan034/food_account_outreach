from pydantic import BaseModel, Field


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