import os

from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker


def build_database_url() -> URL:
    return URL.create(
        drivername="postgresql+psycopg",
        username=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        host=os.environ["POSTGRES_HOST"],
        port=int(os.environ["POSTGRES_PORT"]),
        database=os.environ["POSTGRES_DB"],
    )

# The engine manages database connectivity and a pool of reusable connections.
engine = create_engine(
    build_database_url(),
    pool_pre_ping=True,
)

# This factory creates sessions bound to the PostgreSQL engine.
SessionFactory = sessionmaker(
    bind=engine,
    expire_on_commit=False,
)
