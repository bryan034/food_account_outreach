from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class EmailApproval(BaseModel):
    google_place_id: str = Field(min_length=1, max_length=255, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(default="Contacted business", min_length=1, max_length=255)
    recipient: EmailStr
    source_url: str = Field(min_length=1, max_length=2000)
    subject: str = Field(min_length=1, max_length=200)
    message_text: str = Field(min_length=1, max_length=10000)
    approved: Literal[True]
    verified_public_business_email: Literal[True]

    @field_validator("name", "subject", "message_text")
    @classmethod
    def reject_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Field must contain text")
        return value  # Preserve exact approved subject and message.

    @field_validator("subject")
    @classmethod
    def reject_header_newlines(cls, value: str) -> str:
        if "\r" in value or "\n" in value:
            raise ValueError("Subject cannot contain line breaks")
        return value


class EmailSendConfirmation(BaseModel):
    approved: Literal[True]


class ApprovedEmailRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    recipient: str
    sender: str
    subject: str
    source_url: str
    gmail_message_id: str | None
    approved_at: datetime


class GmailStatus(BaseModel):
    configured: bool
    connected: bool
    email: str | None = None
    detail: str | None = None
