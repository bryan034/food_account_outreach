from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class OutreachAttempt(Base):
    __tablename__ = "outreach_attempts"
    __table_args__ = ( #special attribute in sqlalc declarative models to pass table level options
        CheckConstraint("channel IN ('email', 'tiktok', 'instagram')", name="ck_outreach_channel"),
        CheckConstraint(
            "status IN ('sent', 'scheduling', 'rejected', 'tasting', 'completed')",
            name="ck_outreach_status", 
        ),
        # generates db level CHECK constraint, ensures INSERT or UPDATE operation fails at db engine lvl if column values dont match allowed str literals 
        # name attribute explicitly names sql constraint in db schema. impt for alembic db migrations as drop/alter operations require constraint name
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    restaurant_id: Mapped[int] = mapped_column(
        ForeignKey("restaurants.id", ondelete="RESTRICT"), unique=True, #ondelete=RESTRICT prevents deleting a restaurant w outreach history
    )
    channel: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20))
    message_text: Mapped[str] = mapped_column(Text)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
    )
