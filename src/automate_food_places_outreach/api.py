from typing import Annotated

import httpx2

from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from automate_food_places_outreach.crud.restaurants import (
    create_restaurant as create_restaurant_record,
    delete_restaurant as delete_restaurant_record, 
    get_restaurant_by_id,
    update_restaurant_name as update_restaurant_name_record,
    
)
from automate_food_places_outreach.dependencies import (
    get_http_client, 
    get_session,
    require_google_places_api_key,
)
from automate_food_places_outreach.models.restaurant import Restaurant
from automate_food_places_outreach.models.outreach import OutreachAttempt
from automate_food_places_outreach.schemas.outreach import (
    OutreachRead, OutreachSentCreate, OutreachStatus, OutreachStatusUpdate,
)
from automate_food_places_outreach.services.outreach import (
    change_outreach_status, contacted_place_ids,
)
from automate_food_places_outreach.schemas.restaurants import (
    RestaurantCreate,
    RestaurantRead,
    RestaurantUpdate,
)

from automate_food_places_outreach.google_places import search_places
from automate_food_places_outreach.schemas.google_places import (
    GoogleTextSearchRequest,
    GoogleTextSearchResponse,
)


app = FastAPI(
    title="Food Places Outreach API",
)


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
    restaurant = update_restaurant_name_record(
        session,
        restaurant_id,
        name=payload.name,
    )

    if restaurant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant not found.",
        )

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
    )
    session.add(attempt)
    try:
        session.commit()
        session.refresh(attempt)
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="Restaurant already has initial outreach.") from error
    return attempt


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
    session.commit()
    session.refresh(attempt)
    return attempt
