from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Tasting(Base):
    __tablename__ = "tastings"

    id: Mapped[int] = mapped_column(primary_key=True)
    outreach_id: Mapped[int] = mapped_column(ForeignKey("outreach_attempts.id", ondelete="RESTRICT"), unique=True)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    address: Mapped[str] = mapped_column(String(1000))
    notes: Mapped[str] = mapped_column(Text, default="")
