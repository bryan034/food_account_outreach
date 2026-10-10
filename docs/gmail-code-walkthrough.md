# How the Gmail integration works, and how to repeat it

This is a local, single-user integration, not a general production authentication system.
Google operations in tests are mocked; tests never send real emails.

## The important distinction

The Places API key identifies a Cloud project for discovery. It does not grant access to
Bryan's Gmail account. OAuth asks Bryan to grant this application a specific permission.
The application never asks for or stores Bryan's Google password.

There are two separate workflows: connecting an account once, and approving/sending each email.

## 1. Connecting an account

Start in `src/features/gmail-connection.tsx`. The Connect button calls the typed client's
`gmailConnect()` method in `src/lib/api/client.ts`, which posts to `/gmail/connect`.
That endpoint is registered in `src/automate_food_places_outreach/email_api.py`.

The meaningful lines in `connect_gmail()` are:

```python
url, state = gmail.authorization_url(gmail.configuration())
response.set_cookie("gmail_oauth_state", state, httponly=True, samesite="lax", max_age=600, path="/gmail/callback")
return {"authorization_url": url}
```

- First, `configuration()` reads backend environment variables and validates the encryption
  key and local callback URLs. `authorization_url()` returns the Google consent URL and a
  random state. Tuple unpacking assigns those two results to `url` and `state`.
- Second, `set_cookie()` stores state in this browser. `httponly` prevents JavaScript from
  reading it; `samesite="lax"` allows the top-level navigation back from Google;
  `max_age=600` expires it after ten minutes; `path` restricts where the cookie is sent.
- Third, FastAPI converts the dictionary to JSON. The frontend navigates to that URL;
  Google, not our application, handles the password/sign-in/consent screen.

In `services/gmail.py`, `authorization_url()`:

- Uses `secrets.token_urlsafe()` to generate unpredictable state and a PKCE verifier.
- Hashes the verifier with SHA-256 and URL-safe base64 to form the PKCE challenge.
  Only the challenge goes into the consent URL; the original verifier stays on the backend.
- Stores `(creation_time, verifier)` in `OAUTH_STATES[state]` under a thread lock.
- Requests `openid email` for verified account identity and `gmail.send` for sending only.
- Sets `response_type="code"` so Google returns a temporary code, not a browser-held token.
- Sets `access_type="offline"` to request a refresh token and `prompt="consent"` to obtain
  explicit consent. `urlencode()` safely constructs the query string.

Google returns to `/gmail/callback`. Line by line through its main operations:

- `gmail.configuration()` loads the same application credentials and callback URL.
- `gmail.consume_state(state, request.cookies.get("gmail_oauth_state"))` verifies that the
  callback belongs to this browser's pending connection. It removes the server-side state,
  checks expiration and returns the saved verifier; the callback cannot be reused.
- `gmail.exchange_code(client, config, code, verifier)` posts the one-use code,
  client credentials, exact redirect URI and verifier to Google's token endpoint.
- That helper checks the granted send scope and the presence of a refresh token, then
  requests Google's userinfo endpoint to establish the verified sender email.
- `config.cipher.encrypt(...)` encrypts the refresh token before it enters PostgreSQL.
- The `insert(GmailAccount)...on_conflict_do_update(...)` statement stores or replaces the
  single connected account, using ID 1. `session.commit()` makes that connection persistent.
- `RedirectResponse(..., status_code=303)` returns the browser to frontend Settings.
  `delete_cookie()` clears the temporary browser state cookie.

State ties the consent response to a browser; PKCE ties the code exchange to the original
request. Neither is a replacement for application user authentication in a public deployment.

## 2. Approving an email

In `src/features/social-workflow.tsx`, selecting Email loads sourced public contacts and
Gmail connection status. The review dialog shows sender, recipient, subject and body.

In `markSent()`, `await api.approveEmail(...)` completes before `api.sendEmail(...)` starts.
Saving approval and sending are deliberately two different API requests.

`EmailApproval` in `schemas/email.py` validates the request before the route runs:

- `EmailStr` checks address syntax, not whether that mailbox exists.
- `Literal[True]` requires affirmative approval and public-business-email verification.
- `Field(...)` bounds lengths. Validators reject blank text and subject header newlines.
- The message and subject are not stripped: their approved text must remain exact.

`approve_email()` checks whether this restaurant already has initial outreach. It checks
the email against retained public-source evidence or fetches the claimed source from the
business's website. A guessed address is not sufficient.

`ensure_restaurant()` inserts the Place ID and user's label, or reuses the restaurant with
that unique Place ID. Contact discovery can already have created this row. No second
manual "add business" action is required.

The account's `with_for_update()` lock serializes approval-limit checks. The unique
`outreach_attempts.restaurant_id` constraint is the final duplicate-outreach guard.

`session.flush()` obtains the outreach ID without committing. The route stores:

- Restaurant: business identity and your editable notes.
- Contact: address and the public source where it was found.
- OutreachAttempt: channel, exact body and `email_approved` status.
- ApprovedEmail: sender, recipient, subject, source and stable MIME Message-ID.

`session.commit()` saves the approval before any external send. `sent_at` remains null.

## 3. Sending the exact stored email

In `send_email()`:

- `gmail.access_token()` decrypts the refresh token and exchanges it for a short-lived
  access token. That token is used on backend-to-Google requests, not sent to the frontend.
- The account and outreach row are locked. The route requires `email_approved`, the same
  sender account and an available rolling 24-hour send slot.
- `gmail.encode_email(...)` builds MIME from the stored sender, recipient, subject,
  body and Message-ID. It does not take replacement message text from the send request.
- The body is UTF-8/base64 encoded to preserve exact approved whitespace and Unicode.
  The whole MIME message is then base64url encoded for Gmail's `raw` field.
  Encoding is not encryption.

The critical boundary is:

```python
attempt.status = "email_sending"
attempt.email.attempted_at = datetime.now(timezone.utc)
session.commit()
outcome, provider_id = await gmail.deliver(client, token, raw)
```

- First line reserves this outreach: later callers cannot send an approved email again.
- Second line records the attempted time in UTC for limit checks and traceability.
- Third line persists that reservation before contacting Gmail.
- Fourth line makes one authenticated Gmail send request and waits for its result.

`deliver()` posts `{ "raw": ... }` to `users/me/messages/send` with a Bearer access token.
A successful response with a Gmail message ID produces `sent`. A definite rejection
produces `email_failed`; a timeout, ambiguous server error or missing acknowledgment
produces `email_unknown`. There is no automatic retry. A process crash after reservation
can leave `email_sending`, which must also be treated as uncertain.

Only `sent` writes `sent_at` and the Gmail message ID. Gmail acceptance is not proof of
delivery, reading or a reply. A PostgreSQL rollback cannot undo an email accepted by Gmail;
this is why holding one transaction around the entire send would not solve reliability.

## 4. Showing and editing contacted businesses

Outreach loads `/outreach`, then resolves each `restaurant_id` through `/restaurants/{id}`.
Successful emails use the same list as manually confirmed social outreach; no duplicate
"contacted businesses" table is necessary.

`src/features/business-notes.tsx` edits your business label, category, area, address and
website. The typed `updateRestaurant()` sends a PATCH and updates the frontend's restaurant
cache. The backend validates the allowed fields and uses:

```python
for field, value in payload.model_dump(exclude_unset=True, mode="json").items():
    setattr(restaurant, field, value)
session.commit()
```

- `model_dump()` converts the already validated Pydantic payload to a dictionary.
- `exclude_unset=True` leaves omitted fields unchanged. An explicitly supplied null clears
  an optional field. These are different operations.
- `mode="json"` converts validated URL objects into plain strings suitable for columns.
- `.items()` yields each field name and its value.
- `setattr()` assigns those allowed fields to the SQLAlchemy restaurant object.
- `commit()` persists the changes. The schema forbids extra fields, so this loop cannot
  change IDs, email delivery status, approved subject or sent message.

With no own label, the database retains the generic sentinel. Outreach looks up the current
Google name using `?name_only=true` and displays it as the name-input placeholder, not saved
text. The narrower field mask requests only ID/name, not opening hours. This is a Google API
lookup per unnamed business when the list loads/refreshes and may cost money. If it fails,
the saved outreach stays visible with "Restaurant name unavailable". A personal label avoids
that lookup. Google results are not permanently copied into CRM notes.

## 5. Repeating this in another application

1. Create a Google Cloud OAuth client for that app, enable Gmail API, configure consent/test
   users and register its exact callback URL. Do not reuse a Places API key as Gmail consent.
2. Choose minimum scopes. Use send-only unless inbox access is genuinely required.
3. Keep client secret and a stable encryption key on the backend; keep them out of VITE
   variables, browser storage, logs and Git.
4. Implement connect, state/PKCE and callback routes. Store encrypted refresh tokens against
   the authenticated application user. This app's fixed ID 1 is only for a local single user.
5. Keep token exchange, refresh, MIME encoding and send transport in a narrow service module.
6. Implement stored approvals, database uniqueness/locking, pre-send reservation and honest
   failure/unknown states in the application layer. Never blindly retry ambiguous sends.
7. Make the frontend approve exact content and submit only the approved record ID to send.
8. Test with fake Google HTTP responses and isolated database transactions first. Test
   duplicate clicks, wrong state, revoked consent, timeout and Unicode/whitespace preservation.
9. For production, add real user authentication/authorization, HTTPS/secure cookies, per-user
   account ownership and limits, shared OAuth state for multiple workers, secret management,
   audit/suppression and reviewed unknown-send reconciliation. Broader distribution may
   require Google's verification. Do not simply remove this app's local-URL guard.

Official references: [Google web-server OAuth](https://developers.google.com/identity/protocols/oauth2/web-server),
[Gmail sending format](https://developers.google.com/workspace/gmail/api/guides/sending),
[Gmail scopes](https://developers.google.com/workspace/gmail/api/auth/scopes),
[Places storage policies](https://developers.google.com/maps/documentation/places/web-service/policies).
