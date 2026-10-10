"""Single-user, local Gmail connection, public contacts, approval and sending."""
import os
from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import uuid4

import httpx2
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .dependencies import get_http_client, get_session, require_google_places_api_key
from .google_places import get_place_details
from .models.email import ApprovedEmail, Contact, GmailAccount
from .models.outreach import OutreachAttempt
from .models.restaurant import Restaurant
from .schemas.contacts import ContactCandidate
from .schemas.email import EmailApproval, EmailSendConfirmation, GmailStatus
from .schemas.outreach import OutreachRead
from .services import gmail
from .services.website_enrichment import extract_contacts
from .services.website_fetching import WebsiteFetchError, enrich_website, fetch_html, same_website, validate_website_url

router = APIRouter()
DB = Annotated[Session, Depends(get_session)]
HTTP = Annotated[httpx2.AsyncClient, Depends(get_http_client)]
KEY = Annotated[str, Depends(require_google_places_api_key)]


def local_browser(request: Request) -> None:
    allowed = os.environ.get("FRONTEND_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080,http://127.0.0.1:8080").split(",")
    if request.headers.get("origin") not in {value.strip() for value in allowed}:
        raise HTTPException(403, "Gmail actions require the configured local frontend origin.")


LOCAL = Depends(local_browser)


def daily_limit() -> int:
    try:
        limit = int(os.environ.get("GMAIL_DAILY_SEND_LIMIT", "5"))
        if limit < 1:
            raise ValueError
        return limit
    except ValueError as error:
        raise HTTPException(503, "GMAIL_DAILY_SEND_LIMIT must be a positive integer.") from error


def ensure_restaurant(session: Session, place_id: str, name: str = "Contacted business") -> Restaurant:
    identity = session.scalar(insert(Restaurant).values(google_place_id=place_id, name=name)
        .on_conflict_do_nothing(index_elements=[Restaurant.google_place_id]).returning(Restaurant.id))
    if identity is None:
        return session.scalar(select(Restaurant).where(Restaurant.google_place_id == place_id))
    return session.get(Restaurant, identity)


def retain_contact(session: Session, restaurant_id: int, candidate: ContactCandidate) -> Contact:
    values = {"restaurant_id": restaurant_id, **candidate.model_dump()}
    session.execute(insert(Contact).values(**values).on_conflict_do_nothing(constraint="uq_contact_source"))
    return session.scalar(select(Contact).where(
        Contact.restaurant_id == restaurant_id, Contact.contact_type == candidate.contact_type,
        Contact.value == candidate.value, Contact.source_url == candidate.source_url,
    ))


async def public_website(client: httpx2.AsyncClient, api_key: str, place_id: str) -> str | None:
    try:
        place = await get_place_details(client, api_key=api_key, place_id=place_id)
        return place.website_url
    except httpx2.HTTPStatusError as error:
        raise HTTPException(502, "Google Places refused website discovery.") from error
    except httpx2.RequestError as error:
        raise HTTPException(503, "Google Places is unavailable.") from error
    except ValueError as error:
        raise HTTPException(502, "Google Places returned invalid data.") from error


@router.post("/discovery/google-places/{place_id}/contacts", response_model=list[ContactCandidate], dependencies=[LOCAL])
async def discover_contacts(place_id: str, session: DB, client: HTTP, api_key: KEY):
    website = await public_website(client, api_key, place_id)
    if not website:
        return []
    try:
        result = await enrich_website(website)
    except WebsiteFetchError as error:
        raise HTTPException(502, "The public business website could not be read. You can supply a public source page manually.") from error
    restaurant = ensure_restaurant(session, place_id)
    for candidate in result.contacts:
        retain_contact(session, restaurant.id, candidate)
    session.commit()
    return result.contacts


@router.get("/gmail/status", response_model=GmailStatus)
def gmail_status(session: DB):
    try:
        gmail.configuration()
    except gmail.GmailError as error:
        return GmailStatus(configured=False, connected=False, detail=str(error))
    account = session.get(GmailAccount, 1)
    return GmailStatus(configured=True, connected=account is not None, email=account.email if account else None)


@router.post("/gmail/connect", dependencies=[LOCAL])
def connect_gmail(response: Response):
    try:
        url, state = gmail.authorization_url(gmail.configuration()) 
        # gmail.configuration() reads OAuth client credentials, callback URL and encryption key from env vars
        # gmail.autorization_url() creates google consent url and a random state value
    except gmail.GmailError as error: #integration error
        raise HTTPException(error.status_code, str(error)) from error
    response.set_cookie("gmail_oauth_state", state, httponly=True, samesite="lax", max_age=600, path="/gmail/callback")
    return {"authorization_url": url}


@router.get("/gmail/callback")
async def gmail_callback(request: Request, session: DB, client: HTTP, state: str = "", code: str = "", error: str = ""):
    try:
        config = gmail.configuration()
        verifier = gmail.consume_state(state, request.cookies.get("gmail_oauth_state"))
        if error or not code:
            raise gmail.GmailError("Gmail connection was cancelled.", 400)
        email, encrypted = await gmail.exchange_code(client, config, code, verifier)
        # google email address and encrypted refresh token
        session.execute(insert(GmailAccount).values(id=1, email=email, encrypted_refresh_token=encrypted)
            .on_conflict_do_update(index_elements=[GmailAccount.id], set_={"email": email, "encrypted_refresh_token": encrypted, "updated_at": datetime.now(timezone.utc)}))
        # if insertion conflicts with existing row, update that row instead
        # index_elem identifies pri key conflict to handle
        # this is an upsert, insert if absent, update if present
        session.commit()
    except gmail.GmailError as failure:
        # Keep codes, tokens and provider error bodies out of the browser URL.
        raise HTTPException(failure.status_code, str(failure)) from failure
    response = RedirectResponse(config.frontend_url + "?gmail=connected", status_code=303)
    # RedirectResponse tells browser to navigate to FE settings url , 303 instructs browser to retrieve destination with GET
    response.delete_cookie("gmail_oauth_state", path="/gmail/callback") #removes temp cookie state from browser, matches path used when creating cookie
    return response


@router.delete("/gmail/connection", status_code=204, dependencies=[LOCAL])
def disconnect_gmail(session: DB):
    account = session.get(GmailAccount, 1)
    if account:
        session.delete(account)
        session.commit()
    # Disconnect locally. Google account permissions can also be revoked there.


@router.post("/outreach/email/approve", response_model=OutreachRead, status_code=201, dependencies=[LOCAL])
async def approve_email(payload: EmailApproval, session: DB, client: HTTP, api_key: KEY):
    restaurant = session.scalar(select(Restaurant).where(Restaurant.google_place_id == payload.google_place_id))
    if restaurant and session.scalar(select(OutreachAttempt.id).where(OutreachAttempt.restaurant_id == restaurant.id)):
        raise HTTPException(409, "This business already has an initial outreach record. Do not contact it through another channel.")
    try:
        source = validate_website_url(payload.source_url)
    except WebsiteFetchError as error:
        raise HTTPException(422, "Source must be a public business website URL.") from error
    contact = session.scalar(select(Contact).where(
        Contact.restaurant_id == restaurant.id, Contact.contact_type == "email",
        func.lower(Contact.value) == str(payload.recipient).lower(), Contact.source_url == source,
    )) if restaurant else None
    if contact is None:
        # A typed address is not proof. Read its claimed source on the business website.
        website = await public_website(client, api_key, payload.google_place_id)
        if not website or not same_website(website, source):
            raise HTTPException(422, "Source must be a page on this business's public website.")
        try:
            page = await fetch_html(source, website_url=website)
        except WebsiteFetchError as error:
            raise HTTPException(422, "Could not verify the email on its public source page.") from error
        candidate = next((entry for entry in extract_contacts(page.html, page.url)
            if entry.contact_type == "email" and entry.value.lower() == str(payload.recipient).lower()), None)
        if candidate is None:
            raise HTTPException(422, "This email address was not found on the public source page.")
        restaurant = restaurant or ensure_restaurant(session, payload.google_place_id, payload.name.strip())
        contact = retain_contact(session, restaurant.id, candidate)
    # Serialize daily-limit reservations for this single connected Gmail account.
    account = session.scalar(select(GmailAccount).where(GmailAccount.id == 1).with_for_update())
    if account is None:
        raise HTTPException(409, "Connect Gmail in Settings before approving an email.")
    limit = daily_limit()
    count = session.scalar(select(func.count(ApprovedEmail.id)).where(ApprovedEmail.approved_at >= datetime.now(timezone.utc) - timedelta(hours=24)))
    if count >= limit:
        raise HTTPException(429, "The local rolling 24-hour email approval limit has been reached.")
    if restaurant.name == "Contacted business" and payload.name != "Contacted business":
        restaurant.name = payload.name.strip()
    contact.verified = True  # Public-source evidence plus the user's explicit review.
    contact.usable = True   # Does not prove delivery or that the mailbox exists.
    attempt = OutreachAttempt(restaurant_id=restaurant.id, channel="email", status="email_approved", message_text=payload.message_text)
    session.add(attempt)
    try:
        session.flush()
        attempt.email = ApprovedEmail(
            outreach_id=attempt.id, contact_id=contact.id, recipient=str(payload.recipient), sender=account.email,
            subject=payload.subject, source_url=contact.source_url,
            mime_message_id=f"<food-outreach-{uuid4()}@{account.email.rsplit('@', 1)[1]}>",
        )
        session.commit()
        session.refresh(attempt)
        return attempt
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(409, "This business already has initial outreach. Nothing was sent.") from error


@router.post("/outreach/{outreach_id}/email/send", response_model=OutreachRead, dependencies=[LOCAL])
async def send_email(outreach_id: int, payload: EmailSendConfirmation, session: DB, client: HTTP):
    account = session.get(GmailAccount, 1)
    if account is None:
        raise HTTPException(409, "Connect Gmail in Settings first.")
    try:
        token = await gmail.access_token(client, account.encrypted_refresh_token)
    except gmail.GmailError as error:
        raise HTTPException(error.status_code, str(error)) from error
    # Hold the same account lock for all send reservations, including old drafts.
    account = session.scalar(select(GmailAccount).where(GmailAccount.id == 1).with_for_update().execution_options(populate_existing=True))
    # executes query and extracts GmailAccount ORM object directly, returns None of .id==1 doesnt exist
    # with_for_update acts as concurrency guard inside db transaction (if another process tries to update/lock this exact same gmail acc record at the same time, makes it queue until ur current db session finish and commit)
    # execution_options(populate_existing=True): by default, if sqlalc alr looked up this gmail acc record earlier in same web req, will save it in a memory cache and reuse instead of asking the db again
    # populate=True tells sqlalc to ignore memory cache and retrieve obj from live db, overwriting exisitng memory
    if account is None:
        raise HTTPException(409, "Gmail was disconnected before sending.")
    attempt = session.scalar(select(OutreachAttempt).where(OutreachAttempt.id == outreach_id).with_for_update())
    if attempt is None or attempt.channel != "email" or attempt.email is None:
        raise HTTPException(404, "Approved email not found.")
    if attempt.status != "email_approved":
        raise HTTPException(409, "Email already attempted. Check its status; it will not be resent automatically.")
    if attempt.email.sender != account.email:
        raise HTTPException(409, "Reconnect the Gmail account that approved this message.")
    attempts_today = session.scalar(select(func.count(ApprovedEmail.id)).where(ApprovedEmail.attempted_at >= datetime.now(timezone.utc) - timedelta(hours=24)))
    if attempts_today >= daily_limit():
        raise HTTPException(429, "The local rolling 24-hour email sending limit has been reached.")
    raw = gmail.encode_email(account.email, attempt.email.recipient, attempt.email.subject, attempt.message_text, attempt.email.mime_message_id)
    attempt.status = "email_sending"
    attempt.email.attempted_at = datetime.now(timezone.utc)
    session.commit()  # Reserve the one permitted send before contacting Gmail.
    outcome, provider_id = await gmail.deliver(client, token, raw)
    attempt.status = "sent" if outcome == "sent" else f"email_{outcome}"
    if outcome == "sent":
        attempt.sent_at = datetime.now(timezone.utc)
        attempt.email.gmail_message_id = provider_id
    session.commit()
    session.refresh(attempt)
    return attempt
