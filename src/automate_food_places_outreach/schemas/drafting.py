"""Inputs, structured outreach writing and public draft responses."""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class CreatorProfileWrite(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, validate_default=True)
    creator_name: str = Field(default="Bryan", min_length=1, max_length=100)
    tiktok_url: HttpUrl = Field(default="https://www.tiktok.com/@bbbrrr9", max_length=2000)
    views_over: int = Field(default=146000, ge=0, le=100000000000)
    shares_over: int = Field(default=600, ge=0, le=100000000000)
    minimum_video_views: int = Field(default=1000, ge=0, le=100000000000)
    statistics_confirmed: Literal[True]

    @field_validator("tiktok_url")
    @classmethod
    def creator_profile_url(cls, value: HttpUrl) -> HttpUrl:
        if value.scheme != "https" or value.host not in {"tiktok.com", "www.tiktok.com"} or not (value.path or "").startswith("/@") or len(value.path or "") <= 2 or value.username or value.password or value.query or value.fragment:
            raise ValueError("Use your direct HTTPS TikTok profile URL")
        return value


class CreatorProfileRead(CreatorProfileWrite):
    model_config = ConfigDict(from_attributes=True)
    statistics_confirmed: bool = True
    confirmed_at: datetime


class DraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    request_id: UUID
    google_place_id: str = Field(min_length=1, max_length=255, pattern=r"^[A-Za-z0-9_-]+$")
    restaurant_name: str = Field(min_length=1, max_length=255)
    business_kind: Literal["cafe", "restaurant", "bakery", "food_business"]
    channel: Literal["email", "tiktok", "instagram"]
    # A short independently confirmed fact, not scraped instructions or guessed dishes.
    feature_detail: str = Field(default="", max_length=400)
    source_url: HttpUrl | None = None
    facts_confirmed: Literal[True]

    @field_validator("restaurant_name", "feature_detail")
    @classmethod
    def single_line(cls, value: str) -> str:
        if "\r" in value or "\n" in value:
            raise ValueError("Use a single line of factual text")
        return value

    @field_validator("source_url")
    @classmethod
    def public_source(cls, value: HttpUrl | None) -> HttpUrl | None:
        if value and (value.username or value.password or value.query or value.fragment):
            raise ValueError("Use a public source URL without credentials, query parameters or a fragment")
        return value


class ModelWriting(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    subject: str = Field(min_length=1, max_length=200)
    personalised_paragraph: str = Field(min_length=1, max_length=600)
    used_fact_ids: list[Literal["category", "detail"]] = Field(min_length=1, max_length=2)

    @field_validator("subject", "personalised_paragraph")
    @classmethod
    def single_paragraph(cls, value: str) -> str:
        if "\r" in value or "\n" in value or any(ord(character) < 32 for character in value): #ord(" ") whitespace is 32, so doesnt accpet any chrs below this
            # ord() stands for ordinal, takes single text chr as an argument and returns its unicode code point integer (for standard english letters and keyboard num, maps to ASCII table value): ord('A') returns 65
            raise ValueError("Return a single line without control characters")
        return value


class DraftRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    channel: str
    subject: str
    message_text: str
    model: str
    prompt_version: str
    created_at: datetime


class GeminiStatus(BaseModel):
    configured: bool
    model: str
