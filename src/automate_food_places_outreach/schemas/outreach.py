from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator
from .email import ApprovedEmailRead


class OutreachStatus(StrEnum):
    SENT = "sent"
    SCHEDULING = "scheduling"
    REJECTED = "rejected"
    TASTING = "tasting"
    COMPLETED = "completed"
    EMAIL_APPROVED = "email_approved"
    EMAIL_SENDING = "email_sending"
    EMAIL_FAILED = "email_failed"
    EMAIL_UNKNOWN = "email_unknown"


class ManualOutreachInput(BaseModel):
    channel: Literal["tiktok", "instagram"]
    message_text: str = Field(min_length=1, max_length=10000)
    confirmed_sent: Literal[True]

    @field_validator("message_text")
    @classmethod
    def reject_blank_message(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Sent message must contain text")
        return value


class OutreachSentCreate(ManualOutreachInput):
    restaurant_id: int = Field(gt=0)


class TastingInput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    scheduled_at: AwareDatetime
    address: str = Field(min_length=1, max_length=1000)
    notes: str = Field(default="", max_length=10000)

    @field_validator("address")
    @classmethod
    def clean_address(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Tasting address is required")
        return value.strip()


class OutreachStatusUpdate(BaseModel):
    status: OutreachStatus
    tasting: TastingInput | None = None


class OutreachFromPlace(ManualOutreachInput):
    google_place_id: str = Field(min_length=1, max_length=255, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(default="Contacted business", min_length=1, max_length=255)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Business label must contain text")
        return value.strip()


class OutreachRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    restaurant_id: int
    channel: Literal["email", "tiktok", "instagram"]
    status: OutreachStatus
    message_text: str
    sent_at: datetime | None
    updated_at: datetime
    tasting: TastingInput | None = None
    email: ApprovedEmailRead | None = None
