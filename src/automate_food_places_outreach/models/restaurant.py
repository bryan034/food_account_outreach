from datetime import datetime

from sqlalchemy import String, DateTime, Float, Text, func
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
    category: Mapped[str | None] = mapped_column(
        String(100),
    )
    address: Mapped[str | None] = mapped_column(Text)
    area: Mapped[str | None] = mapped_column(
        String(100),
    )
    website_url: Mapped[str | None] = mapped_column(Text)
    rating: Mapped[float | None] = mapped_column(Float)
    review_count: Mapped[int | None]
    price_level: Mapped[str | None] = mapped_column(
        String(50),
    )
    business_status: Mapped[str | None] = mapped_column(
        String(50),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )