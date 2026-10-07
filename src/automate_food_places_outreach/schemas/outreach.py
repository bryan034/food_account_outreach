from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OutreachStatus(StrEnum):
    SENT = "sent"
    SCHEDULING = "scheduling"
    REJECTED = "rejected"
    TASTING = "tasting"
    COMPLETED = "completed"


class OutreachSentCreate(BaseModel):
    restaurant_id: int = Field(gt=0)
    channel: Literal["tiktok", "instagram"]
    message_text: str = Field(min_length=1, max_length=10000)
    confirmed_sent: Literal[True]

    @field_validator("message_text")
    @classmethod
    def reject_blank_message(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Sent message must contain text")
        return value


class OutreachStatusUpdate(BaseModel):
    status: OutreachStatus


class OutreachRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    restaurant_id: int
    channel: Literal["email", "tiktok", "instagram"]
    status: OutreachStatus
    message_text: str
    sent_at: datetime
    updated_at: datetime
