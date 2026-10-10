# Frontend/backend connection and tasting workflow

## What is connected

The existing Lovable frontend is React/TypeScript with TanStack routing, not Next.js. We kept that working frontend rather than replacing it. It calls FastAPI over HTTP; FastAPI validates requests, runs Python rules and persists records in local PostgreSQL.

Implemented here: opening hours in business details, automatic business-record creation when manual outreach is confirmed, backward status corrections, persistent tasting plans and directions, and hidden IDs in the interface. Approved Gmail sending and sourced contacts were subsequently added; see [Gmail setup](gmail-setup.md). This is not the entire original roadmap: deterministic scoring, grounded AI drafts, suppression/audit infrastructure, reply/bounce polling, follow-ups and Apple Calendar still need dedicated implementation.

## Run locally

You can now start all services with `docker compose up --build -d`; see the [Compose guide](docker-compose.md) for the setup and line-by-line explanations. The commands below are the separate-process alternative.

Run these commands from the repository root. Do not commit `.env` or `.env.local`.

```sh
docker compose up -d db
uv run --env-file .env alembic upgrade head
uv run --env-file .env uvicorn automate_food_places_outreach.api:app --host 127.0.0.1 --port 8000
```

- `docker compose` reads the Compose configuration. `up` starts the service. `-d` runs it in the background. `db` selects PostgreSQL; its named volume preserves data.
- `uv run` runs within uv's project environment. `--env-file .env` loads backend credentials without putting them in code. `alembic upgrade head` applies outstanding migrations, including the new `tastings` table. The migration was already applied during implementation; rerunning is harmless.
- `uvicorn` serves the ASGI app. `automate_food_places_outreach.api:app` names its Python module and `app` object. `--host 127.0.0.1` binds only to this computer, not the public network. `--port 8000` selects the backend port. Keep this terminal running.

In another terminal, from the same repository root:

```sh
npm run dev -- --host 127.0.0.1 --port 5173
```

`npm run dev` runs the package's Vite development script. `--` forwards the following flags to Vite. `--host` keeps it local; `--port` selects the frontend port.

Open `http://127.0.0.1:5173`, go to **Settings**, choose **Connected** mode, set the API URL to `http://127.0.0.1:8000`, apply settings and check backend health. Demo mode remains isolated, ephemeral and explicitly labelled.

`VITE_API_BASE_URL` is an optional public default; Settings overrides it in that browser. `FRONTEND_ORIGINS` controls FastAPI's exact permitted browser origins. The default includes both `localhost` and `127.0.0.1` on ports 5173 and 8080. Never put secrets in `VITE_` variables: these are public frontend configuration. CORS is a browser access rule, not authentication. Do not expose this unauthenticated local backend publicly.

A hosted HTTPS Lovable preview is not the same environment as a local frontend. It may be unable to reach your computer's HTTP API due to network/browser restrictions. Validate using the local frontend; deployment/authentication is a separate task.

## How a request moves through the code

### Restaurant details

1. `src/features/discover.tsx`: clicking **View details** calls `openDetails(place)`.
2. `src/lib/api/client.ts`: `api.placeDetails(place.id)` performs `GET /discovery/google-places/{place_id}/details`.
3. `src/automate_food_places_outreach/api.py`: FastAPI injects its HTTP client and backend-only Google API key.
4. `google_places.py`: `get_place_details()` requests a limited Google field mask including `regularOpeningHours.weekdayDescriptions`.
5. `schemas/google_places.py`: Pydantic validates Google's JSON and translates aliases into Python names.
6. FastAPI responds with `regular_opening_hours.weekday_descriptions`. React displays those strings, or a missing-hours/error message. IDs remain internal.

Hours are fetched only when details are opened, not for every discovery card. Google's regular opening hours require the [Place Details Enterprise SKU](https://developers.google.com/maps/documentation/places/web-service/place-details). No live paid Google request was needed by the automated tests. Hours are not permanently stored in our database; [Google's Places policies](https://developers.google.com/maps/documentation/places/web-service/policies) restrict caching and exempt Place IDs.

The request counter in `openDetails` prevents a slow response from an old dialog overwriting a newer selection. `++detailsRequest.current` increments the counter; saving it in `request` identifies this call; `request === detailsRequest.current` permits updates only while it is still the latest call. Closing the dialog invalidates the old request. It does not cancel a Google request already in progress.

### Recording outreach without adding a business manually

1. **Prepare outreach** passes the chosen `Place` to `src/features/social-workflow.tsx`. No record is saved yet.
2. You type the exact message, optionally copy it and open a manually supplied social profile. These actions do not send anything or write outreach history.
3. After manually sending, you check the confirmation box and click **Confirm and record**.
4. `api.markPlaceSent()` sends `POST /outreach/from-place/mark-sent` with the Place ID, selected channel, exact message and `confirmed_sent: true`.
5. Pydantic rejects a blank message or missing/false confirmation.
6. FastAPI creates or reuses the restaurant by its unique Google Place ID, then inserts the outreach row in the same database transaction.
7. A single `commit()` saves both. PostgreSQL's unique `restaurant_id` constraint prevents two initial outreach records, including attempts through different channels. A conflict rolls back and returns HTTP 409.
8. React displays success; the contacted business disappears from these discovery results. Future searches are filtered by backend outreach history, regardless of corrected status.

There is no separate create-business form and no ID entry. The optional name is your own notes label, not an automatically saved Google data snapshot. If omitted, the stored name is “Contacted business”. Existing locally stored restaurant names are retained when a record is reused. Permanent storage policies for external discovery content need a separate provider-compliance decision.

Core database lines, in execution order:

- `insert(Restaurant)` creates a PostgreSQL INSERT statement for the restaurant table.
- `.values(...)` supplies the provider ID and optional user-written label.
- `.on_conflict_do_nothing(index_elements=[Restaurant.google_place_id])` reuses identity rather than creating a duplicate; it does not overwrite an existing name.
- `.returning(Restaurant.id)` asks PostgreSQL to return a new row's ID.
- `session.scalar(statement)` executes the statement and retrieves that single value.
- If no row was inserted, a `SELECT` retrieves the existing restaurant ID.
- `OutreachAttempt(...)` constructs the exact-message history object.
- `session.add(attempt)` places it in the unit of work; it does not commit by itself.
- `session.commit()` persists the restaurant and outreach together.
- `session.refresh(attempt)` reloads generated timestamps and related state before the response.
- `except IntegrityError` catches database uniqueness failures; `session.rollback()` undoes this transaction, then FastAPI returns HTTP 409.

### Status correction and tasting

Forward actions remain Sent → Scheduling → Tasting → Completed, with rejection available along the way. **Back to…** allows Scheduling → Sent, Tasting → Scheduling and Completed → Tasting. Rejected can be corrected to Sent, Scheduling or Tasting. Illegal jumps still return 409. This corrects the existing record; it does not erase the sent message or permit contacting the business again.

1. `src/features/outreach.tsx`: clicking **Move to tasting** opens `TastingDialog`; it does not submit a status change yet.
2. `src/features/tasting.tsx`: you enter the agreed date/time in Singapore time, address and optional notes. Cancel makes no write.
3. `planToApi()` converts, for example, `2026-11-01T19:00` SGT to `2026-11-01T11:00:00.000Z`, the same instant in UTC.
4. `api.changeStatus(outreachId, "tasting", plan)` performs `PATCH /outreach/{outreach_id}/status`, including both status and tasting data in the JSON body.
5. Pydantic requires a timezone-aware datetime and nonblank address.
6. FastAPI locks the outreach row, checks the transition, creates or updates its related tasting and commits both together. Entering tasting without a new or existing plan returns 422 and leaves the status unchanged.
7. The response includes the saved plan. React updates the list and detail view only after success. Failure leaves the planner open with an error.
8. `GET /outreach` includes the related tasting, so refreshing the page retains it. Editing updates that same plan. Correcting backward retains the plan for a later return to tasting.

The additive migration `migrations/versions/fe71f5002a69_add_persistent_tasting_plans.py` creates a separate `tastings` table. Its `outreach_id` foreign key links to an outreach attempt; uniqueness permits at most one current plan per attempt. `RESTRICT` prevents deleting the parent while the plan exists. A timezone-aware column stores an instant, not a timezone label; the UI explicitly displays Singapore time. Existing tasting records without a date remain unplanned until you edit them—we do not invent dates or silently migrate old browser-only plans.

New SQLAlchemy lines:

- `Mapped["Tasting | None"]` describes an optional related Python object, not a scalar table column.
- `relationship(lazy="selectin")` loads associated plans using a separate SELECT; FastAPI can serialise them without a fetch per individual row.
- `AwareDatetime` requires the input to identify its timezone; a bare local datetime is ambiguous and is rejected.
- `.with_for_update()` locks the outreach row for the transaction, serialising concurrent status/plan edits.
- `payload.tasting.model_dump()` turns validated fields into a dictionary for the model constructor or updates.
- Assigning `attempt.tasting = Tasting(...)` attaches the new plan; editing uses `setattr()` for each validated field.
- `session.commit()` persists the plan and status atomically. Closing an uncommitted session on validation failure rolls back its changes.

### Directions

`directionsUrl()` builds a Google Maps URL with `URLSearchParams`. It uses the agreed tasting address as the destination, not an ID that could accidentally point to a different venue. `travelmode=transit` selects public transport. No `origin` is supplied: Maps uses your current location if available, asks permission or lets you select a starting point. The application itself neither requests nor stores GPS coordinates. Maps is an external link; this does not use our paid Places API key.

## Files and checks

Backend changes: `api.py`, `google_places.py`, Google/outreach Pydantic schemas, outreach rules, outreach/tasting models, Alembic environment and the additive tasting migration.

Frontend changes: Discover, Outreach, SocialWorkflow, TastingDialog, Settings; the typed API contract, connected HTTP client and isolated demo. `.env.example` documents the public frontend URL and backend CORS settings.

Tests cover opening-hours parsing, atomic outreach creation, duplicate protection, manual confirmation, persistent tasting plans, invalid/naive dates, backward corrections, planner cancellation, error handling, SGT conversion, direction URL construction and frontend API payloads.

```sh
uv run --env-file .env pytest -q
npm test
npx tsc --noEmit
npm run build
```

`pytest -q` runs backend tests with quiet output; PostgreSQL must be running. Tests create identifiable test records and clean up those records. `npm test` runs the frontend Vitest suite. `npx tsc --noEmit` checks TypeScript without writing compiled files. `npm run build` verifies the production frontend build. None of these sends a real social message.

## Check your understanding

Trace what happens if you cancel the tasting dialog, if two channels confirm outreach simultaneously, and if PostgreSQL rejects the tasting transaction. Explain why dates carry an offset and why CORS does not replace authentication. Implementation and passing tests are established; independent competence is still **Learning** until you can explain and modify this workflow yourself.
