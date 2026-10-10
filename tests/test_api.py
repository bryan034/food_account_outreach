from uuid import uuid4

from fastapi import status
from fastapi.testclient import TestClient #provides synchronous client for tesing an ASGI app

from automate_food_places_outreach.api import app
from automate_food_places_outreach.crud.restaurants import (
    create_restaurant,
    delete_restaurant,
    get_restaurant_by_google_place_id,
    get_restaurant_by_id,
)
from automate_food_places_outreach.database import SessionFactory


client = TestClient(app) #wraps app wo starting a real server


def test_health_check() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_create_restaurant_endpoint() -> None:
    google_place_id = f"api-test-{uuid4()}"

    try:
        response = client.post(
            "/restaurants",
            json={
                "google_place_id": google_place_id,
                "name": "API Test Café",
            },
        )

        response_body = response.json()

        assert response.status_code == status.HTTP_201_CREATED
        assert isinstance(response_body["id"], int)
        assert response_body["google_place_id"] == google_place_id
        assert response_body["name"] == "API Test Café"
    finally:
        with SessionFactory.begin() as session: #.begin() creates a session and transaction
            restaurant = get_restaurant_by_google_place_id(
                session,
                google_place_id,
            )

            if restaurant is not None:
                delete_restaurant(
                    session,
                    restaurant.id,
                )

def test_create_restaurant_rejects_missing_google_place_id() -> None:
    response = client.post(
        "/restaurants",
        json={
            "name": "Invalid Test Café",
        },
    )

    response_body = response.json()

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response_body["detail"][0]["loc"] == [
        "body",
        "google_place_id",
    ] #in error response body, makes sure the error location is because google_place_id not there

def test_create_restaurant_rejects_duplicate_place_id() -> None:
    """this api test defers from lower level crud duplicate test
    CRUD test verifies postgresql rejects duplicate
    API test verifies app translates that rejection into useful http response"""

    google_place_id = f"duplicate-api-test-{uuid4()}"

    request_body = {
        "google_place_id": google_place_id,
        "name": "Duplicate API Test Café",
    }

    try:
        first_response = client.post(
            "/restaurants",
            json=request_body,
        )
        second_response = client.post(
            "/restaurants",
            json=request_body,
        )

        assert first_response.status_code == status.HTTP_201_CREATED
        assert second_response.status_code == status.HTTP_409_CONFLICT
        assert second_response.json() == {
            "detail": (
                "A restaurant with this Google Place ID "
                "already exists."
            )
        }
    finally:
        # deletes row created by 1st req even if an assertation fails
        with SessionFactory.begin() as session:
            restaurant = get_restaurant_by_google_place_id(
                session,
                google_place_id,
            )

            if restaurant is not None:
                delete_restaurant(
                    session,
                    restaurant.id,
                )

def test_read_restaurant_endpoint() -> None:
    google_place_id = f"read-api-test-{uuid4()}"

    with SessionFactory.begin() as session:
        restaurant = create_restaurant(
            session,
            google_place_id=google_place_id,
            name="Readable Test Café",
        )
        restaurant_id = restaurant.id

    try:
        response = client.get(
            f"/restaurants/{restaurant_id}"
        )

        response_body = response.json()

        assert response.status_code == status.HTTP_200_OK
        assert response_body == {
            "id": restaurant_id,
            "google_place_id": google_place_id,
            "name": "Readable Test Café",
            "category": None, "address": None, "area": None, "website_url": None,
        }
    finally:
        with SessionFactory.begin() as session:
            restaurant = get_restaurant_by_google_place_id(
                session,
                google_place_id,
            )

            if restaurant is not None:
                delete_restaurant(
                    session,
                    restaurant.id,
                )

def test_read_missing_restaurant_returns_404() -> None:
    response = client.get(
        "/restaurants/2147483647"
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {
        "detail": "Restaurant not found.",
    }

def test_update_restaurant_endpoint() -> None:
    google_place_id = f"patch-api-test-{uuid4()}"

    with SessionFactory.begin() as session:
        restaurant = create_restaurant(
            session,
            google_place_id=google_place_id,
            name="Old API Name",
        )
        restaurant_id = restaurant.id

    try:
        response = client.patch(
            f"/restaurants/{restaurant_id}",
            json={
                "name": "New API Name",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "id": restaurant_id,
            "google_place_id": google_place_id,
            "name": "New API Name",
            "category": None, "address": None, "area": None, "website_url": None,
        }

        with SessionFactory() as session:
            persisted_restaurant = get_restaurant_by_id(
                session,
                restaurant_id,
            )

            assert persisted_restaurant is not None
            assert persisted_restaurant.name == "New API Name"
    finally:
        with SessionFactory.begin() as session:
            restaurant = get_restaurant_by_google_place_id(
                session,
                google_place_id,
            )

            if restaurant is not None:
                delete_restaurant(
                    session,
                    restaurant.id,
                )

def test_update_missing_restaurant_returns_404() -> None:
    response = client.patch(
        "/restaurants/2147483647",
        json={
            "name": "New Name",
        },
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {
        "detail": "Restaurant not found.",
    }

def test_update_restaurant_rejects_empty_name() -> None:
    response = client.patch(
        "/restaurants/2147483647",
        json={
            "name": "",
        },
    )

    response_body = response.json()

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response_body["detail"][0]["loc"] == [
        "body",
        "name",
    ]

def test_delete_restaurant_endpoint() -> None:
    google_place_id = f"delete-api-test-{uuid4()}"

    with SessionFactory.begin() as session:
        restaurant = create_restaurant(
            session,
            google_place_id=google_place_id,
            name="Delete API Test Café",
        )
        restaurant_id = restaurant.id

    try:
        response = client.delete(
            f"/restaurants/{restaurant_id}"
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert response.content == b"" #confirms there is no response body
        # b"" represents empty bytes obj, as opposed to "" which represents empty str

        with SessionFactory() as session:
            deleted_restaurant = get_restaurant_by_id(
                session,
                restaurant_id,
            )

            assert deleted_restaurant is None
    finally:
        with SessionFactory.begin() as session:
            restaurant = get_restaurant_by_google_place_id(
                session,
                google_place_id,
            )

            if restaurant is not None:
                delete_restaurant(
                    session,
                    restaurant.id,
                )
