from sqlalchemy import select
from sqlalchemy.orm import Session

from automate_food_places_outreach.models.outreach import OutreachAttempt
from automate_food_places_outreach.models.restaurant import Restaurant
from automate_food_places_outreach.schemas.outreach import OutreachStatus


ALLOWED_TRANSITIONS = {
    OutreachStatus.SENT: {OutreachStatus.SCHEDULING, OutreachStatus.REJECTED},
    OutreachStatus.SCHEDULING: {OutreachStatus.SENT, OutreachStatus.TASTING, OutreachStatus.REJECTED},
    OutreachStatus.TASTING: {OutreachStatus.SCHEDULING, OutreachStatus.COMPLETED, OutreachStatus.REJECTED},
    OutreachStatus.REJECTED: {OutreachStatus.SENT, OutreachStatus.SCHEDULING, OutreachStatus.TASTING},
    OutreachStatus.COMPLETED: {OutreachStatus.TASTING},
    OutreachStatus.EMAIL_APPROVED: set(),
    OutreachStatus.EMAIL_SENDING: set(),
    OutreachStatus.EMAIL_FAILED: set(),
    OutreachStatus.EMAIL_UNKNOWN: set(),
}


def change_outreach_status(attempt: OutreachAttempt, new_status: OutreachStatus) -> None:
    current_status = OutreachStatus(attempt.status)
    if new_status == current_status:
        return
    if new_status not in ALLOWED_TRANSITIONS[current_status]:
        raise ValueError(f"Cannot change outreach from {current_status} to {new_status}")
    attempt.status = new_status.value


def contacted_place_ids(session: Session, candidate_ids: list[str]) -> set[str]:
    if not candidate_ids:
        return set()
    statement = (
        select(Restaurant.google_place_id)
        .join(OutreachAttempt, OutreachAttempt.restaurant_id == Restaurant.id)
        .where(Restaurant.google_place_id.in_(candidate_ids))
    )
    return set(session.scalars(statement))
