# Gmail connection and approved email sending

For a code trace and instructions for reusing this design, see [Gmail code walkthrough](gmail-code-walkthrough.md).

The code is implemented, but a real Gmail account is not connected by installing it. You must create an OAuth client and personally sign in. No actual email was sent while implementing/testing this feature.

## One-time Google setup

1. Open your Google Cloud project (you can use the existing Places project).
2. Under APIs & Services → Library, enable **Gmail API**. Places API is a different API.
3. Open Google Auth platform → Branding and configure your local app's name/support/contact email.
4. For a personal Gmail account, choose **External**, leave the app in **Testing**, and add your own Gmail address under Audience → Test users.
5. Under Data Access, configure the minimum scopes: `https://www.googleapis.com/auth/gmail.send`, `openid`, and your Google email identity (`https://www.googleapis.com/auth/userinfo.email`). The application requests the equivalent short `email` identity scope. It does **not** request Gmail inbox-reading access.
6. Under Clients, create an OAuth client of type **Web application**. Name it `Food Outreach Local`.
7. Add this exact **Authorized redirect URI**:

```text
http://127.0.0.1:8000/gmail/callback
```

Match scheme, hostname, port and path exactly. If you changed `BACKEND_PORT`, use that port. No Google JavaScript sign-in SDK is used, so its JavaScript-origin registration is not needed by this flow.

8. Save the client ID and client secret directly into your ignored `.env`. Do not paste them into chat or commit a downloaded credentials JSON file. The Places API key cannot authorize Gmail.

Google references: [OAuth consent configuration](https://developers.google.com/workspace/guides/configure-oauth-consent), [web-server OAuth and redirect validation](https://developers.google.com/identity/protocols/oauth2/web-server), [Gmail scopes](https://developers.google.com/workspace/gmail/api/auth/scopes).

## Local configuration

Generate a token-encryption key **on your own terminal**:

```sh
docker compose exec -T backend python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

`exec` runs a command in the running backend container. `-T` disables an interactive terminal. `python -c` runs the quoted Python code. The import loads Fernet; `generate_key()` creates a random encryption key; `decode()` turns bytes into text; `print()` shows it so you can save it locally. **This output is a secret: put it in `.env`, not chat.** Generate it once, not on every container startup.

Fill these values in `.env`:

```dotenv
GOOGLE_OAUTH_CLIENT_ID=your_actual_client_id.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=your_actual_client_secret
GMAIL_TOKEN_ENCRYPTION_KEY=your_generated_fernet_key
GMAIL_DAILY_SEND_LIMIT=5
```

The first two identify/authenticate the application to Google's OAuth service. The Fernet key encrypts the account's long-lived refresh token in PostgreSQL. Keep the key stable and back it up securely: a database backup alone cannot decrypt stored Gmail credentials.

Compose already provides these local defaults:

```dotenv
GOOGLE_OAUTH_REDIRECT_URI=http://127.0.0.1:8000/gmail/callback
GMAIL_FRONTEND_URL=http://127.0.0.1:5173/settings
```

Rebuild/recreate after configuring credentials:

```sh
docker compose up --build -d
```

`up` starts the services, `--build` includes the current code, and `-d` keeps them in the background. Changed environment variables require container recreation, not merely restart. The backend reads literal API credential assignments directly from `.env` using its service-level `env_file`; same-named shell exports do not replace these credentials. Explicit Compose `environment` entries still take precedence for database/network settings. Never display the full resolved Compose environment when sharing diagnostics.

Open **http://127.0.0.1:5173**, choose Connected mode with API URL **http://127.0.0.1:8000**, then Settings → Gmail connection → **Connect Gmail**. You personally complete Google sign-in and consent. Successful authorization returns you to Settings and displays the connected sender address.

Use `127.0.0.1` consistently for both frontend and API: the OAuth-state cookie must belong to the same backend hostname used for Google's callback. A callback from `127.0.0.1` cannot read a cookie created on `localhost`. Pending connections expire after ten minutes and are discarded on backend restart; simply reconnect if that happens.

Google may require reconnecting when a grant expires or is revoked, particularly during OAuth testing. If consent is blocked, report the error text without secrets or authorization codes. Do not disable security restrictions to bypass it. Broader distribution/production verification is a separate task.

## Using email outreach

1. Discover a business → View details → Prepare outreach.
2. Select **Email** in Contact channel.
3. The backend obtains the official website URL through Google Places, then uses the existing bounded public-website fetcher and Beautiful Soup parser. It reads the homepage and at most two same-site contact/about pages. It retains each extracted contact's source.
4. If found, the first public email/source is filled in. Multiple results are selectable. No result leaves the address blank with **“Email address was not found”**. Website/network errors are shown separately; an error is not proof that the business has no email.
5. You can manually enter a full recipient address plus a public page on the business's website. The backend requires the address to actually appear there. A guessed address or a bare domain is not accepted.
6. Enter the subject and factual message. Review the public source and ensure it is a suitable business contact, not a privacy/legal/vendor address.
7. Click **Send email**. The review dialog shows sender, recipient, subject and body. Check the explicit verification/approval box, then **Approve and send email**.
8. The backend stores the exact approved fields, reserves initial outreach and sends via Gmail. Only a successful Gmail response with a message ID marks it Sent. Gmail acceptance is not proof the recipient received/read it.

TikTok and Instagram still use Copy/Open Profile/manual sending and **I sent this message**. Gmail is never sent through `mailto:`, SMTP passwords or browser automation. Demo mode only simulates email; it never contacts Google.

The local limit defaults to five approvals **and** five send attempts in a rolling 24-hour window. Send reservations are serialized, so old drafts cannot bypass the send limit. There are no automatic retries. A confirmed failed attempt is retained and cannot currently be retried through this interface; recovery/fallback requires a separate reviewed feature. Unknown delivery must be checked in Gmail before any further action.

## Request/control flow

| UI action | API | Responsibility |
| --- | --- | --- |
| Select Email | `POST /discovery/google-places/{id}/contacts` | Fetch official public site, parse and persist sourced candidates |
| Check connection | `GET /gmail/status` | Return configuration/connected sender only, never tokens |
| Connect Gmail | `POST /gmail/connect` → Google → `GET /gmail/callback` | State cookie + PKCE, sign-in/consent, encrypted refresh-token persistence |
| Approve exact email | `POST /outreach/email/approve` | Validate public source, manual approval and limits; store immutable message |
| Send approved email | `POST /outreach/{id}/email/send` | Refresh scoped access; reserve once, encode MIME, send and record outcome |

The review dialog deliberately makes two sequential requests: approval is persisted **before** sending. If sending never starts because permissions expire, the approved record remains in Outreach with a Review and send button. That button sends the stored content, not newly edited fields.

After reservation, status is `email_sending`. A timeout or uncertain upstream failure becomes `email_unknown`; a definite rejection becomes `email_failed`. Neither has a sent timestamp. A backend crash after reservation can leave `email_sending`: treat it as unknown, not as permission to retry. A successful send becomes `sent` and then uses the existing collaboration lifecycle. All reserved outreach states exclude the business from new-lead discovery and prevent another initial channel.

## New concepts and code, line by line

### `services/gmail.py`: OAuth and transport

- `base64` encodes the MIME message in the form Gmail requires; it is encoding, **not encryption**.
- `hashlib` hashes the PKCE verifier; `secrets` generates unpredictable state/verifier values; `time.monotonic()` measures expiration without wall-clock changes.
- `Fernet` encrypts/authenticates the persistent refresh token; `InvalidToken` reports a wrong encryption key or corrupted ciphertext.
- `GmailConfig` keeps backend-only settings together. `configuration()` checks required environment variables and local URLs before enabling connection.
- `authorization_url()` creates a random state and verifier. The challenge is a URL-safe SHA-256 hash of the verifier; only its hash goes in the authorization URL. A short-lived server record retains the verifier.
- `response.set_cookie(..., httponly=True, samesite="lax")` in the router binds the returned OAuth state to this browser without exposing the cookie to JavaScript.
- `consume_state()` compares the browser cookie to the callback state, rejects expiry/reuse, and retrieves the verifier. The lock protects this in-memory state across request threads.
- `exchange_code()` posts the one-use code, verifier and application credentials directly to Google. It checks the granted send scope and verified account identity, encrypts the refresh token, and stores no browser token.
- `access_token()` decrypts the refresh token only on the backend and obtains short-lived access. Revoked/expired authorization stops before an email send.
- `encode_email()` creates From/To/Subject/Message-ID headers. UTF-8 message bytes are MIME base64-encoded explicitly so approval text—including whitespace and final newline choices—is preserved. The whole MIME message is separately base64URL-encoded into Gmail's JSON `raw` field.
- `deliver()` makes exactly one POST to Gmail `messages.send`. It returns an outcome; it does not retry or log tokens/provider error bodies. A timeout/5xx/missing message ID cannot safely prove non-delivery.

The application requests `gmail.send` plus email identity—not inbox scopes. Consequently inbox replies, bounces and delivery tracking are not implemented. Reference: [Gmail message encoding and sending](https://developers.google.com/workspace/gmail/api/guides/sending).

### `email_api.py`: database and safety

- `APIRouter` groups these endpoints without putting the orchestration into frontend components. `app.include_router(...)` attaches them to FastAPI.
- `DB`, `HTTP` and `KEY` reuse the existing annotated dependencies: a database session, HTTP client and Places key.
- `local_browser()` checks the request Origin against configured frontend origins for contact/Gmail mutations. CORS now permits credentials for these explicit origins so the state cookie works. This blocks unwanted browser-origin actions; it does **not** replace user authentication for a public deployment.
- `ensure_restaurant()` inserts the provider ID or resolves its existing local row. No user record-creation form is required.
- `retain_contact()` saves type, value and source with a uniqueness constraint, so repeating enrichment does not duplicate the same evidence.
- `approve_email()` first blocks previously reserved/contacted businesses. It validates or fetches the public source and requires both approval booleans. Public evidence plus your review marks the contact verified; this is not an SMTP mailbox/deliverability test.
- The Gmail account's `with_for_update()` lock serializes daily-limit reservations. The unique outreach `restaurant_id` remains the final duplicate-channel protection.
- `session.flush()` allocates the outreach ID without committing. Its related ApprovedEmail stores recipient, sender, subject, source and Message-ID; the existing outreach message stores the exact approved body. One commit persists this approval together.
- `send_email()` refreshes access before marking sending. It verifies the saved sender, locks the record, checks that it is still approved, and checks the send limit.
- It writes `email_sending` and an attempted timestamp, then commits **before** the external Gmail request. A second caller cannot reserve the same send. The outcome is committed separately because a database transaction cannot roll back an email already accepted by Google.
- Only a Gmail acknowledgment writes `sent_at` and the Gmail message ID. Generic collaboration-status changes cannot forge these email-delivery states.

### Models, schemas and migration

- `models/email.py` defines three normalized tables. Contacts hold independently scraped source evidence; GmailAccount holds one encrypted account token; ApprovedEmail holds immutable approval metadata linked one-to-one to outreach. Keeping credentials separate prevents exposing tokens in outreach responses.
- `schemas/email.py` uses `EmailStr` for syntax, `Literal[True]` for explicit approvals, size/blank checks, and rejects subject line breaks to prevent header injection. `email-validator` supplies EmailStr's validation dependency.
- `schemas/outreach.py` adds the four honest pre-send/error states and optional read-only email details. Unsent records have `sent_at=None`.
- The migration creates the three tables, makes `sent_at` nullable, removes its unconditional database timestamp default and explicitly updates the status CHECK constraint (Alembic cannot infer that constraint edit automatically). Existing sent timestamps are retained; social confirmations now set theirs explicitly.
- The migration refuses downgrade while any new contact/credential/email data exists, rather than silently deleting it or calling unsent records sent.

### Frontend

- `types.ts` describes the new API contract; `client.ts` sends all requests centrally, includes cookies and handles a 204 disconnect response without trying to parse nonexistent JSON.
- `SocialWorkflow` branches on Email: recipient/source/subject replace the social-profile field. Its effect loads contacts/connection status; a request cache prevents repeated lookups when switching the dropdown within the same dialog.
- `markSent()` now branches: social channels record manual sending; Email first calls `approveEmail()`, stores the approved ID, then calls `sendEmail()`. Once approved, fields are locked to prevent sending content different from the review.
- `GmailConnection` in Settings navigates to Google's authorization URL on your explicit click; the callback returns to Settings. OAuth credentials never go into a VITE variable or browser storage.
- Outreach displays saved recipient/subject and honest delivery states. Its Review and send button requires another explicit confirmation for an approved-but-unattempted email.
- `demo.ts` implements the same methods entirely in memory; its simulated sender/recipient are labelled examples.

## Verification and remaining boundaries

Tests use a fake HTTP transport for **all** Google operations. Gmail integration tests wrap database work in an outer transaction and use `join_transaction_mode="create_savepoint"` for endpoint sessions. Thus endpoint commits release savepoints, and final rollback removes test data/restores any existing Gmail connection. No real email, cloud consent or persistent test token is produced.

Tests cover source discovery, manual approvals, exact MIME bodies, encryption/state checks, invalid source/recipient/subject, cross-origin rejection, duplicate channels, one-send reservation, expired permissions, daily limits, and unknown delivery. Frontend tests check the dropdown, missing-email placeholder and approval-before-send order.

Still future: generalized audit/suppression infrastructure, reply/bounce polling, follow-ups, email-to-social fallback, safe failed-send reconciliation/retry, AI drafting and public deployment authentication. This is a local single-user feature with one backend process; persistent OAuth state/multi-user account separation are separate architectural work. Uvicorn access logs are disabled in Compose so callback authorization codes are not recorded in request URLs.

Understanding check: Why must approval be committed before the Gmail POST, and why must a timeout not automatically return the email to an unsent/retryable state?
