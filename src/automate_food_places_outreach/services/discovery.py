from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from automate_food_places_outreach.crud.restaurants import (
    get_restaurant_by_google_place_id,
)
from automate_food_places_outreach.models.restaurant import Restaurant
from automate_food_places_outreach.schemas.google_places import GooglePlace
from automate_food_places_outreach.schemas.restaurants import (
    RestaurantDiscoveryData,
)


def map_google_place_to_restaurant(
    place: GooglePlace,
) -> RestaurantDiscoveryData:
    return RestaurantDiscoveryData(
        google_place_id=place.id,
        name=place.display_name.text,
        category=place.primary_type,
        address=place.formatted_address,
        business_status=place.business_status,
    )


def save_discovered_restaurant(
    session: Session,
    restaurant_data: RestaurantDiscoveryData,
) -> tuple[Restaurant, bool]:
    statement = (
        insert(Restaurant)
        .values(**restaurant_data.model_dump()) #converts object to dct, **unpacks dct entry into named arguments (dct keys r db columns, values supply what to insert)
        .on_conflict_do_nothing(index_elements=[Restaurant.google_place_id]) #skip insertion if google place id already exists
        .returning(Restaurant) #requests inserted row as a sqlalch object
    )
    restaurant = session.scalar(statement)
    if restaurant is not None:
        return restaurant, True

    existing_restaurant = get_restaurant_by_google_place_id(
        session,
        restaurant_data.google_place_id,
    )
    if existing_restaurant is None:
        raise RuntimeError("Conflicting restaurant disappeared during import")

    existing_restaurant.name = restaurant_data.name

    if restaurant_data.category is not None:
        existing_restaurant.category = restaurant_data.category

    if restaurant_data.address is not None:
        existing_restaurant.address = restaurant_data.address

    if restaurant_data.business_status is not None:
        existing_restaurant.business_status = (
            restaurant_data.business_status
        )

    session.flush()

    return existing_restaurant, False
