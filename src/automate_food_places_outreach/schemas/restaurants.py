from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class RestaurantCreate(BaseModel):
    google_place_id: str = Field(
        min_length=1,
        max_length=255,
    )
    name: str = Field(
        min_length=1,
        max_length=255,
    )


class RestaurantRead(RestaurantCreate): #response schema inherits google_place_id and name from RestaurantCreate
    model_config = ConfigDict(
        from_attributes=True,
    ) 
    # allows pydantic to construct response from sqlalc object attributes
    # restaurant.id
    # restaurant.google_place_id
    # restaurant.name

    # wo from_attributes = True, pydantic expects dict style inputs like id
    id: int
    category: str | None = None
    address: str | None = None
    area: str | None = None
    website_url: str | None = None

class RestaurantUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(
        min_length=1,
        max_length=255,
    )
    category: str | None = Field(default=None, max_length=100)
    address: str | None = Field(default=None, max_length=2000)
    area: str | None = Field(default=None, max_length=100)
    website_url: HttpUrl | None = None

    @field_validator("name")
    @classmethod
    def meaningful_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Business name must contain text")
        return value.strip()


class RestaurantDiscoveryData(BaseModel):
    google_place_id: str = Field(min_length=1, max_length=255)
    name: str = Field(min_length=1, max_length=255)
    category: str | None = Field(default=None, max_length=100)
    address: str | None = None
    business_status: str | None = Field(default=None, max_length=50)
