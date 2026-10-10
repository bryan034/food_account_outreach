from typing import Annotated
from datetime import datetime, timezone
import os

import httpx2

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from automate_food_places_outreach.crud.restaurants import (
    create_restaurant as create_restaurant_record,
    delete_restaurant as delete_restaurant_record, 
    get_restaurant_by_id,
    
)
from automate_food_places_outreach.dependencies import (
    get_http_client, 
    get_session,
    require_google_places_api_key,
)
from automate_food_places_outreach.models.restaurant import Restaurant
from automate_food_places_outreach.models.outreach import OutreachAttempt
from automate_food_places_outreach.models.tasting import Tasting
from automate_food_places_outreach.models.email import Contact, GmailAccount, ApprovedEmail
from automate_food_places_outreach.schemas.outreach import (
    OutreachFromPlace, OutreachRead, OutreachSentCreate, OutreachStatus, OutreachStatusUpdate,
)
from automate_food_places_outreach.services.outreach import (
    change_outreach_status, contacted_place_ids,
)
from automate_food_places_outreach.schemas.restaurants import (
    RestaurantCreate,
    RestaurantRead,
    RestaurantUpdate,
)

from automate_food_places_outreach.google_places import get_place_details, search_places
from automate_food_places_outreach.schemas.google_places import (
    GoogleTextSearchRequest,
    GoogleTextSearchResponse,
    GooglePlace,
)


app = FastAPI(
    title="Food Places Outreach API",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.environ.get(
        "FRONTEND_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080,http://127.0.0.1:8080",
    ).split(",") if origin.strip()],
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type"],
    allow_credentials=True,
)


@app.get("/discovery/google-places/{place_id}/details", response_model=GooglePlace, response_model_by_alias=False)
async def place_details(
    place_id: str,
    client: Annotated[httpx2.AsyncClient, Depends(get_http_client)],
    api_key: Annotated[str, Depends(require_google_places_api_key)],
    name_only: bool = False,
) -> GooglePlace:
    try:
        return await get_place_details(client, api_key=api_key, place_id=place_id, name_only=name_only)
    except httpx2.HTTPStatusError as error:
        raise HTTPException(status_code=502, detail="Google Places returned an error.") from error
    except httpx2.RequestError as error:
        raise HTTPException(status_code=503, detail="Google Places is unavailable.") from error
    except ValueError as error:
        raise HTTPException(status_code=502, detail="Google Places returned invalid data.") from error


@app.post("/outreach/from-place/mark-sent", response_model=OutreachRead, status_code=201)
def mark_place_outreach_sent(
    payload: OutreachFromPlace,
    session: Annotated[Session, Depends(get_session)],
) -> OutreachAttempt:
    # Persist the provider ID and user's optional label, never a discovery snapshot.
    try:
        restaurant_id = session.scalar(
            insert(Restaurant).values(google_place_id=payload.google_place_id, name=payload.name)
            .on_conflict_do_nothing(index_elements=[Restaurant.google_place_id])
            .returning(Restaurant.id)
        )
        if restaurant_id is None:
            restaurant_id = session.scalar(select(Restaurant.id).where(Restaurant.google_place_id == payload.google_place_id))
        attempt = OutreachAttempt(
            restaurant_id=restaurant_id, channel=payload.channel,
            status="sent", message_text=payload.message_text,
            sent_at=datetime.now(timezone.utc),
        )
        session.add(attempt)
        session.commit()
        session.refresh(attempt)
        return attempt
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="Business already has initial outreach.") from error


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}

@app.post(
    "/restaurants",
    response_model=RestaurantRead, #validates and serialises the returned orm obj. auto by fastapi
    status_code=status.HTTP_201_CREATED,
)
def create_restaurant_endpoint(
    payload: RestaurantCreate, #tells fastapi to parse and validate req body before running the route. Auto by fastapi
    session: Annotated[Session, Depends(get_session)], #tells fastapi to call get_session() and inject yielded session
) -> Restaurant:
    try:
        restaurant = create_restaurant_record(
            session,
            google_place_id=payload.google_place_id,
            name=payload.name,
        )
        session.commit()
    except IntegrityError as error: #catches db uniqueness violation
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A restaurant with this Google Place ID already exists.",
        ) from error

    return restaurant

@app.get(
    "/restaurants/{restaurant_id}",
    response_model=RestaurantRead,
)
def read_restaurant_endpoint(
    restaurant_id: int,
    session: Annotated[Session, Depends(get_session)],
) -> Restaurant:
    restaurant = get_restaurant_by_id(
        session,
        restaurant_id,
    )

    if restaurant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant not found.",
        )

    return restaurant

@app.patch( #PATCH represents partial update, PUT commonly represents replacing the complete resource
    "/restaurants/{restaurant_id}",
    response_model=RestaurantRead,
)
def update_restaurant_endpoint(
    restaurant_id: int,
    payload: RestaurantUpdate,
    session: Annotated[Session, Depends(get_session)],
) -> Restaurant:
    restaurant = get_restaurant_by_id(session, restaurant_id)

    if restaurant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant not found.",
        )

    # Only validated business-note fields can change; outreach history stays intact.
    for field, value in payload.model_dump(exclude_unset=True, mode="json").items():
        setattr(restaurant, field, value)
    session.commit()

    return restaurant

@app.delete(
    "/restaurants/{restaurant_id}",
    status_code=status.HTTP_204_NO_CONTENT, #status code 204 means operation succeeded but there is no response body
)
def delete_restaurant_endpoint(
    restaurant_id: int,
    session: Annotated[Session, Depends(get_session)],
) -> None:
    try:
        was_deleted = delete_restaurant_record(session, restaurant_id)
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(
            status_code=409, detail="Restaurant has history and cannot be deleted.",
        ) from error

    if not was_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant not found.",
        )

    session.commit()

@app.post(
    "/discovery/google-places/preview",
    response_model=GoogleTextSearchResponse,
    response_model_by_alias=False, #makes our API return Python-style names such as display_name, rather than Google’s displayName
)
async def preview_google_places(
    payload: GoogleTextSearchRequest,
    client: Annotated[
        httpx2.AsyncClient, #ensures non-blocking async performance within an async web framework. and acts as type hint for dependency injection
        Depends(get_http_client),
    ],
    # Annotated[BaseType, Metadata1, Metadata2, ...] accepts min 2 params
    api_key: Annotated[
        str,
        Depends(require_google_places_api_key),
    ],
) -> GoogleTextSearchResponse:
    try:
        return await search_places(
            client,
            api_key=api_key,
            text_query=payload.text_query,
        )
    except httpx2.HTTPStatusError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Google Places returned an error.",
        ) from error
    except httpx2.RequestError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google Places is unavailable.",
        ) from error


@app.post(
    "/discovery/google-places/new-leads",
    response_model=GoogleTextSearchResponse,
    response_model_by_alias=False,
)
async def discover_new_leads(
    payload: GoogleTextSearchRequest,
    client: Annotated[
        httpx2.AsyncClient,
        Depends(get_http_client),
    ],
    api_key: Annotated[
        str,
        Depends(require_google_places_api_key),
    ],
    session: Annotated[Session, Depends(get_session)],
) -> GoogleTextSearchResponse:
    try:
        search_response = await search_places(
            client,
            api_key=api_key,
            text_query=payload.text_query,
        )
    except httpx2.HTTPStatusError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Google Places returned an error.",
        ) from error
    except httpx2.RequestError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google Places is unavailable.",
        ) from error

    contacted = contacted_place_ids(session, [place.id for place in search_response.places])
    return GoogleTextSearchResponse(
        places=[place for place in search_response.places if place.id not in contacted],
        next_page_token=search_response.next_page_token,
    )


@app.post("/outreach/mark-sent", response_model=OutreachRead, status_code=201)
def mark_outreach_sent(
    payload: OutreachSentCreate,
    session: Annotated[Session, Depends(get_session)],
) -> OutreachAttempt:
    if session.get(Restaurant, payload.restaurant_id) is None:
        raise HTTPException(status_code=404, detail="Restaurant not found.")
    attempt = OutreachAttempt(
        restaurant_id=payload.restaurant_id,
        channel=payload.channel,
        status=OutreachStatus.SENT.value,
        message_text=payload.message_text,
        sent_at=datetime.now(timezone.utc),
    )
    session.add(attempt)
    try:
        session.commit()
        session.refresh(attempt)
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="Restaurant already has initial outreach.") from error
    return attempt


# Keep OAuth/approved delivery separate from manual social outreach routes.
from automate_food_places_outreach.email_api import router as email_router
app.include_router(email_router)

from automate_food_places_outreach.drafting_api import router as drafting_router
app.include_router(drafting_router)


@app.get("/outreach", response_model=list[OutreachRead])
def list_outreach(
    session: Annotated[Session, Depends(get_session)],
    offset: int = 0,
    limit: int = 50,
) -> list[OutreachAttempt]:
    if offset < 0 or not 1 <= limit <= 100:
        raise HTTPException(status_code=422, detail="Offset must be non-negative; limit must be 1–100.")
    return list(session.scalars(select(OutreachAttempt).order_by(OutreachAttempt.id).offset(offset).limit(limit)))


@app.patch("/outreach/{outreach_id}/status", response_model=OutreachRead)
def update_outreach_status(
    outreach_id: int,
    payload: OutreachStatusUpdate,
    session: Annotated[Session, Depends(get_session)],
) -> OutreachAttempt:
    attempt = session.scalar(
        select(OutreachAttempt).where(OutreachAttempt.id == outreach_id).with_for_update()
    )
    if attempt is None:
        raise HTTPException(status_code=404, detail="Outreach not found.")
    try:
        change_outreach_status(attempt, payload.status)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    if payload.tasting is not None:
        if payload.status != OutreachStatus.TASTING:
            raise HTTPException(status_code=422, detail="A tasting plan requires tasting status.")
        if attempt.tasting is None:
            attempt.tasting = Tasting(outreach_id=attempt.id, **payload.tasting.model_dump())
            session.add(attempt.tasting)
        else:
            for key, value in payload.tasting.model_dump().items():
                setattr(attempt.tasting, key, value)
    if payload.status == OutreachStatus.TASTING and attempt.tasting is None:
        raise HTTPException(status_code=422, detail="Schedule a tasting date, time, and address first.")
    session.commit()
    session.refresh(attempt)
    return attempt
