from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from automate_food_places_outreach.crud.restaurants import (
    create_restaurant,
    delete_restaurant,
    get_restaurant_by_google_place_id,
    update_restaurant_name,
)
from automate_food_places_outreach.database import SessionFactory


# pytest discovers functions whose names start with test_
def test_create_restaurant() -> None:
    google_place_id = f"test-place-{uuid4()}"

    with SessionFactory() as session:
        restaurant = create_restaurant(
            session,
            google_place_id=google_place_id,
            name="Test Café",
        )

        assert restaurant.id is not None
        assert restaurant.google_place_id == google_place_id
        assert restaurant.name == "Test Café"

        found_restaurant = get_restaurant_by_google_place_id(
            session,
            google_place_id,
        )

        assert found_restaurant is not None
        assert found_restaurant.id == restaurant.id
        assert found_restaurant.name == "Test Café"

        session.rollback()


def test_duplicate_google_place_id_is_rejected() -> None:
    google_place_id = f"duplicate-test-{uuid4()}"

    with SessionFactory() as session:
        create_restaurant(
            session,
            google_place_id=google_place_id,
            name="First Restaurant",
        )

        with pytest.raises(IntegrityError):
            create_restaurant(
                session,
                google_place_id=google_place_id,
                name="Duplicate Restaurant",
            )
        # 1. PostgreSQL checks UNIQUE (google_place_id).
        # 2. PostgreSQL rejects the second insert.
        # 3. Psycopg reports the database error.
        # 4. SQLAlchemy converts it into IntegrityError.
        # 5. pytest.raises(...) confirms this error was expected.
        session.rollback()


def test_update_restaurant_name() -> None:
    google_place_id = f"update-test-{uuid4()}"

    with SessionFactory() as session:
        restaurant = create_restaurant(
            session,
            google_place_id=google_place_id,
            name="Old Name",
        )

        updated_restaurant = update_restaurant_name(
            session,
            restaurant.id,
            name="New Name",
        )

        assert updated_restaurant is not None
        assert updated_restaurant.id == restaurant.id
        assert updated_restaurant.name == "New Name"

        session.rollback()


def test_delete_restaurant() -> None:
    google_place_id = f"delete-test-{uuid4()}"

    with SessionFactory() as session:
        restaurant = create_restaurant(
            session,
            google_place_id=google_place_id,
            name="Restaurant to Delete",
        )

        was_deleted = delete_restaurant(
            session,
            restaurant.id,
        )

        found_restaurant = get_restaurant_by_google_place_id(
            session,
            google_place_id,
        )

        assert was_deleted is True
        assert found_restaurant is None

        session.rollback()
