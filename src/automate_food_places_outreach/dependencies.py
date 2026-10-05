from collections.abc import Generator #descibes fn that pauses at yield and later resumes
from collections.abc import AsyncIterator
import httpx2
from fastapi import HTTPException, status

from sqlalchemy.orm import Session

from automate_food_places_outreach.config import get_google_places_api_key
from automate_food_places_outreach.database import SessionFactory


def get_session() -> Generator[Session, None, None]: 
    #Session: value yielded to FastAPI
    # 1st none: fastapi doesnt send value back into generator 
    # 2nd none: generator doesnt return a final value
    with SessionFactory() as session:
        yield session #execution pauses and gives sess to route handler, after handler completes, fastapi resumes generator, exists with block and closes session

async def get_http_client() -> AsyncIterator[httpx2.AsyncClient]: #dependcy asynchronoysly yields AsyncClient objects
    async with httpx2.AsyncClient(timeout=10.0) as client:
        yield client


def require_google_places_api_key() -> str:
    try:
        return get_google_places_api_key()
    except RuntimeError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google Places is not configured.",
        ) from error
