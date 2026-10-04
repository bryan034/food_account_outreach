from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base

class Restaurant(Base):
    # Base inheritance causes SQLAlchemy to register this table in Base.metadata.
    __tablename__ = "restaurants"

    id: Mapped[int] = mapped_column(primary_key=True)
    google_place_id: Mapped[str] = mapped_column(String(255), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    # Mapped[...] describes the Python type of an attribute managed by SQLAlchemy.
    # mapped_column() supplies column configuration such as keys and limits.
