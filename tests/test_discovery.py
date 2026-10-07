from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from sqlalchemy import delete, func, select

from automate_food_places_outreach.database import SessionFactory
from automate_food_places_outreach.models.restaurant import Restaurant
from automate_food_places_outreach.schemas.google_places import GooglePlace
from automate_food_places_outreach.schemas.restaurants import (
    RestaurantDiscoveryData,
)
from automate_food_places_outreach.services.discovery import (
    map_google_place_to_restaurant,
    save_discovered_restaurant,
)


def test_map_google_place_to_restaurant() -> None:
    google_place = GooglePlace.model_validate(
        {
            "id": "place-123",
            "displayName": {
                "text": "Example Café",
            },
            "formattedAddress": "1 Example Street, Singapore",
            "primaryType": "cafe",
            "businessStatus": "OPERATIONAL",
        }
    )

    restaurant_data = map_google_place_to_restaurant(google_place)

    assert restaurant_data.google_place_id == "place-123"
    assert restaurant_data.name == "Example Café"
    assert restaurant_data.category == "cafe"
    assert restaurant_data.address == "1 Example Street, Singapore"
    assert restaurant_data.business_status == "OPERATIONAL"


def test_concurrent_discovery_creates_one_restaurant() -> None:
    google_place_id = f"concurrent-test-{uuid4()}"
    restaurant_data = RestaurantDiscoveryData(
        google_place_id=google_place_id,
        name="Concurrent Test Café",
    )
    start = Barrier(2)

    def save_in_separate_session() -> tuple[int, bool]:
        with SessionFactory.begin() as session:
            start.wait(timeout=10)
            restaurant, created = save_discovered_restaurant(
                session, restaurant_data,
            )
            return restaurant.id, created

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(save_in_separate_session) for _ in range(2)]
            results = [future.result(timeout=20) for future in futures]
        assert results[0][0] == results[1][0]
        assert sorted(created for _id, created in results) == [False, True]
        with SessionFactory() as session:
            count = session.scalar(
                select(func.count()).select_from(Restaurant).where(
                    Restaurant.google_place_id == google_place_id
                )
            )
        assert count == 1
    finally:
        with SessionFactory.begin() as session:
            session.execute(
                delete(Restaurant).where(Restaurant.google_place_id == google_place_id)
            )


def test_save_discovered_restaurant_deduplicates_place_id() -> None:
    google_place_id = f"discovery-test-{uuid4()}"

    first_data = RestaurantDiscoveryData(
        google_place_id=google_place_id,
        name="Original Café",
        category="cafe",
        address="1 Original Street, Singapore",
        business_status="OPERATIONAL",
    )
    updated_data = RestaurantDiscoveryData(
        google_place_id=google_place_id,
        name="Updated Café",
        category=None,
        address="2 Updated Street, Singapore",
        business_status="CLOSED_TEMPORARILY",
    )

    with SessionFactory() as session:
        first_restaurant, was_created = save_discovered_restaurant(
            session,
            first_data,
        )
        first_restaurant_id = first_restaurant.id

        updated_restaurant, was_created_again = (
            save_discovered_restaurant(
                session,
                updated_data,
            )
        )

        restaurant_count = session.scalar(
            select(func.count())
            .select_from(Restaurant)
            .where(Restaurant.google_place_id == google_place_id)
        )

        assert was_created is True
        assert was_created_again is False
        assert updated_restaurant.id == first_restaurant_id
        assert updated_restaurant.name == "Updated Café"
        assert updated_restaurant.category == "cafe"
        assert updated_restaurant.address == "2 Updated Street, Singapore"
        assert (
            updated_restaurant.business_status
            == "CLOSED_TEMPORARILY"
        )
        assert restaurant_count == 1

        session.rollback()
