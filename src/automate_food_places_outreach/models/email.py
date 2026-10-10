from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Contact(Base):
    __tablename__ = "contacts"
    __table_args__ = (UniqueConstraint("restaurant_id", "contact_type", "value", "source_url", name="uq_contact_source"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    restaurant_id: Mapped[int] = mapped_column(ForeignKey("restaurants.id", ondelete="RESTRICT"))
    contact_type: Mapped[str] = mapped_column(String(20))
    value: Mapped[str] = mapped_column(String(320))
    source_url: Mapped[str] = mapped_column(String(2000))
    direct_url: Mapped[str] = mapped_column(Text)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    usable: Mapped[bool] = mapped_column(Boolean, default=False)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GmailAccount(Base):
    __tablename__ = "gmail_accounts"

    # This local, single-creator application supports one connected account.
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320))
    encrypted_refresh_token: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ApprovedEmail(Base):
    __tablename__ = "approved_emails"

    id: Mapped[int] = mapped_column(primary_key=True)
    outreach_id: Mapped[int] = mapped_column(ForeignKey("outreach_attempts.id", ondelete="RESTRICT"), unique=True)
    contact_id: Mapped[int] = mapped_column(ForeignKey("contacts.id", ondelete="RESTRICT"))
    recipient: Mapped[str] = mapped_column(String(320))
    sender: Mapped[str] = mapped_column(String(320))
    subject: Mapped[str] = mapped_column(String(200))
    source_url: Mapped[str] = mapped_column(String(2000))
    mime_message_id: Mapped[str] = mapped_column(String(255), unique=True)
    gmail_message_id: Mapped[str | None] = mapped_column(String(255))
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    attempted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
