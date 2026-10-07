from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class OutreachAttempt(Base):
    __tablename__ = "outreach_attempts"
    __table_args__ = (
        CheckConstraint("channel IN ('email', 'tiktok', 'instagram')", name="ck_outreach_channel"),
        CheckConstraint(
            "status IN ('sent', 'scheduling', 'rejected', 'tasting', 'completed')",
            name="ck_outreach_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    restaurant_id: Mapped[int] = mapped_column(
        ForeignKey("restaurants.id", ondelete="RESTRICT"), unique=True,
    )
    channel: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20))
    message_text: Mapped[str] = mapped_column(Text)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
    )
