"""Creator assertions and draft history; neither table records a send."""
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class CreatorProfile(Base):
    __tablename__ = "creator_profiles"
    __table_args__ = (CheckConstraint("id = 1", name="ck_single_creator"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    creator_name: Mapped[str] = mapped_column(String(100))
    tiktok_url: Mapped[str] = mapped_column(String(2000))
    views_over: Mapped[int] = mapped_column(BigInteger)
    shares_over: Mapped[int] = mapped_column(BigInteger)
    minimum_video_views: Mapped[int] = mapped_column(BigInteger)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OutreachDraft(Base):
    __tablename__ = "outreach_drafts"
    __table_args__ = (
        CheckConstraint("status IN ('generating', 'ready', 'failed')", name="ck_draft_status"),
        CheckConstraint("channel IN ('email', 'tiktok', 'instagram')", name="ck_draft_channel"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[str] = mapped_column(String(36), unique=True)
    creator_profile_id: Mapped[int] = mapped_column(ForeignKey("creator_profiles.id", ondelete="RESTRICT"))
    google_place_id: Mapped[str] = mapped_column(String(255), index=True)
    channel: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20))
    # Snapshot only user-confirmed inputs, not Google discovery responses or credentials.
    factual_inputs: Mapped[dict] = mapped_column(JSONB)
    model_selection: Mapped[dict | None] = mapped_column(JSONB)
    model: Mapped[str] = mapped_column(String(100))
    prompt_version: Mapped[str] = mapped_column(String(100))
    subject: Mapped[str | None] = mapped_column(String(200))
    message_text: Mapped[str | None] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
