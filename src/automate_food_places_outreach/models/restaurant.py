from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
# from automate_food_places_outreach.models.base import Base



class Restaurant(Base):
    __tablename__ = "restaurants"

    id: Mapped[int] = mapped_column(primary_key=True)
    google_place_id: Mapped[str] = mapped_column(String(255), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    # Mapped[...] describes python type of a model attr managed by sqlalch
    # mapped_column() supplies db column config, like primary keys, max len, uniqueness etc