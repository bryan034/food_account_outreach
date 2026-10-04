from pydantic import BaseModel, ConfigDict, Field


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

class RestaurantUpdate(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=255,
    )