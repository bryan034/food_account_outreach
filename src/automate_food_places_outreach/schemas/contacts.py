from typing import Literal

from pydantic import BaseModel


class ContactCandidate(BaseModel):
    contact_type: Literal["email", "tiktok", "instagram"]
    value: str
    direct_url: str
    source_url: str
    verified: bool = False
    usable: bool = False
