from collections.abc import Generator #descibes fn that pauses at yield and later resumes

from sqlalchemy.orm import Session

from automate_food_places_outreach.database import SessionFactory


def get_session() -> Generator[Session, None, None]: 
    #Session: value yielded to FastAPI
    # 1st none: fastapi doesnt send value back into generator 
    # 2nd none: generator doesnt return a final value
    with SessionFactory() as session:
        yield session #execution pauses and gives sess to route handler, after handler completes, fastapi resumes generator, exists with block and closes session