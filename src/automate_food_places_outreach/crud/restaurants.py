from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.restaurant import Restaurant


def create_restaurant(
    session: Session,
    *,
    google_place_id: str,
    name: str,
) -> Restaurant:
    restaurant = Restaurant(
        google_place_id=google_place_id,
        name=name,
    )

    session.add(restaurant)
    session.flush()  # Sends INSERT inside the current transaction without committing.

    return restaurant


def get_restaurant_by_google_place_id(
    session: Session,
    google_place_id: str,
) -> Restaurant | None:
    statement = select(Restaurant).where(
        Restaurant.google_place_id == google_place_id
    )

    return session.scalar(statement)


def update_restaurant_name(
    session: Session,
    restaurant_id: int,
    *,
    name: str,
) -> Restaurant | None:
    restaurant = session.get(Restaurant, restaurant_id)

    if restaurant is None:
        return None

    restaurant.name = name
    session.flush()

    return restaurant


def delete_restaurant(
    session: Session,
    restaurant_id: int,
) -> bool:
    restaurant = session.get(Restaurant, restaurant_id)

    if restaurant is None:
        return False

    session.delete(restaurant)
    session.flush()

    return True
