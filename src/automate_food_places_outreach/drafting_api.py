"""Local creator settings and bounded, persisted Gemini drafting orchestration."""
import os
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError

from .email_api import DB, HTTP, LOCAL
from .models.drafting import CreatorProfile, OutreachDraft
from .models.outreach import OutreachAttempt
from .models.restaurant import Restaurant
from .schemas.drafting import CreatorProfileRead, CreatorProfileWrite, DraftRead, DraftRequest, GeminiStatus
from .services import gemini_drafting as gemini

router = APIRouter(dependencies=[LOCAL])
logger = logging.getLogger(__name__)


@router.get("/creator-profile", response_model=CreatorProfileRead | None)
def read_creator_profile(session: DB):
    return session.get(CreatorProfile, 1)


@router.patch("/creator-profile", response_model=CreatorProfileRead)
def save_creator_profile(payload: CreatorProfileWrite, session: DB):
    values = payload.model_dump(mode="json", exclude={"statistics_confirmed"})
    values["confirmed_at"] = datetime.now(timezone.utc)
    session.execute(insert(CreatorProfile).values(id=1, **values)
        .on_conflict_do_update(index_elements=[CreatorProfile.id], set_=values))
    session.commit()
    return session.get(CreatorProfile, 1)


@router.get("/gemini/status", response_model=GeminiStatus)
def gemini_status():
    try:
        config = gemini.configuration()
        return GeminiStatus(configured=True, model=config.model)
    except gemini.DraftingError:
        return GeminiStatus(configured=False, model=os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite"))


@router.post("/outreach/drafts/generate", response_model=DraftRead, status_code=201)
async def generate_draft(payload: DraftRequest, session: DB, client: HTTP):
    try:
        config = gemini.configuration()
    except gemini.DraftingError as error:
        raise HTTPException(error.status_code, str(error)) from error
    inputs = payload.model_dump(mode="json")
    # Serialize cost reservations, just as Gmail serializes send reservations.
    profile = session.scalar(select(CreatorProfile).where(CreatorProfile.id == 1).with_for_update())
    if profile is None:
        raise HTTPException(409, "Save and confirm your creator statistics in Settings first.")
    previous = session.scalar(select(OutreachDraft).where(OutreachDraft.request_id == str(payload.request_id)))
    if previous:
        if previous.factual_inputs["restaurant"] != inputs:
            raise HTTPException(409, "This generation request ID already belongs to different inputs.")
        if previous.status == "ready":
            return previous
        raise HTTPException(409, "This generation was already attempted. Start a new explicit generation if needed.")
    contacted = session.scalar(select(OutreachAttempt.id).join(Restaurant)
        .where(Restaurant.google_place_id == payload.google_place_id))
    if contacted:
        raise HTTPException(409, "This business already has initial outreach; do not generate another cold-contact message.")
    try:
        limit = int(os.environ.get("GEMINI_DAILY_GENERATION_LIMIT", "20"))
        if not 1 <= limit <= 1000:
            raise ValueError
    except ValueError as error:
        raise HTTPException(503, "GEMINI_DAILY_GENERATION_LIMIT must be between 1 and 1000.") from error
    count = session.scalar(select(func.count(OutreachDraft.id)).where(
        OutreachDraft.created_at >= datetime.now(timezone.utc) - timedelta(hours=24)))
    if count >= limit:
        raise HTTPException(429, "The local rolling 24-hour draft generation limit has been reached.")
    profile_inputs = CreatorProfileRead.model_validate(profile).model_dump(mode="json")
    draft = OutreachDraft(request_id=str(payload.request_id), creator_profile_id=1,
        google_place_id=payload.google_place_id, channel=payload.channel, status="generating",
        factual_inputs={"restaurant": inputs, "creator": profile_inputs},
        model=config.model, prompt_version=gemini.PROMPT_VERSION)
    session.add(draft)
    try:
        session.commit()  # Count failed/interrupted requests too; never auto-retry paid calls.
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(409, "This generation request was already reserved.") from error
    logger.info("Draft generation reserved: draft_id=%s model=%s", draft.id, config.model)
    try:
        writing = await gemini.generate_writing(client, config, inputs, profile_inputs)
        draft.subject, draft.message_text = gemini.render_message(inputs, profile_inputs, writing)
        # Keep the existing JSONB column; the prompt version identifies its v2 shape.
        draft.model_selection = writing.model_dump()
        draft.status = "ready"
        session.commit()
        session.refresh(draft)
        logger.info("Draft generation completed: draft_id=%s", draft.id)
        return draft
    except gemini.DraftingError as error:
        draft.status = "failed"
        draft.error_code = error.code  # Never save provider bodies or API keys.
        session.commit()
        logger.warning("Draft generation failed: draft_id=%s code=%s", draft.id, error.code)
        raise HTTPException(error.status_code, str(error)) from error


@router.get("/outreach/drafts/{draft_id}", response_model=DraftRead)
def read_draft(draft_id: int, session: DB):
    draft = session.get(OutreachDraft, draft_id)
    if draft is None:
        raise HTTPException(404, "Draft not found.")
    if draft.status != "ready":
        raise HTTPException(409, "This draft is not ready. Generation may have failed or been interrupted.")
    return draft
