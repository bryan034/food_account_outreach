# Project details and skills evidence — Bryan's Foodfolio

Last reviewed: 10 October 2026.

## Purpose of this document

This document gives a portfolio-writing or assessment agent a grounded account of the project, technologies used, learning demonstrated and remaining limitations. It is based on the repository and Bryan's coaching discussions, not merely the original project proposal.

Do not interpret an installed dependency, working AI-assisted implementation or correct short answer as proof of independent mastery. Distinguish what the application implements from what Bryan has demonstrated personally. Reinspect the referenced files before making current technical claims; this document is a dated snapshot, not a test report.

## Project and contribution context

Foodfolio is a local-first application for discovering Singapore food businesses and managing collaboration outreach for Bryan's TikTok food account. It supports restaurant discovery, public contact extraction, reviewed message drafting, Gmail delivery, manual social outreach and tasting planning.

Bryan defined the product requirements, revised the workflow to fit his actual outreach needs, and worked through backend implementation and debugging with AI coaching. Early work was manually typed and explained; later, Bryan explicitly authorised the coding agent to implement changes. The frontend originated from Lovable and was subsequently connected to the Python backend. Present this as an AI-assisted project, not as an entirely unaided implementation.

The learning objective is to understand, build, debug, explain and modify the system independently—not just obtain working code.

## Actual technology stack

| Technology | Role in this repository | Evidence |
| --- | --- | --- |
| Python 3.13+ | Backend language | `pyproject.toml`, `src/automate_food_places_outreach/` |
| uv | Python dependency management, lockfile and execution environment | `pyproject.toml`, `uv.lock`, `Dockerfile.backend` |
| FastAPI and Uvicorn | HTTP routes, dependency injection and ASGI serving | `api.py`, `email_api.py`, `drafting_api.py` |
| Pydantic | Request/response models, provider response parsing and structured model-output validation | `schemas/` |
| PostgreSQL 17 | Persistent local relational database | `compose.yaml`, `models/` |
| SQLAlchemy 2-style APIs | ORM models, queries, relationships, transactions and row locks | `database.py`, `models/`, `crud/`, `services/` |
| Psycopg with binary distribution | PostgreSQL driver used by SQLAlchemy and the original connection check | `pyproject.toml`, `db_check.py` |
| Alembic | Ordered database schema migrations | `migrations/env.py`, `migrations/versions/` |
| HTTPX2 | Async HTTP requests and mocked HTTP transports | `google_places.py`, `services/gmail.py`, `services/gemini_drafting.py`, tests |
| Beautiful Soup 4 | HTML parsing for contact links and contact-page discovery | `services/website_enrichment.py`, `services/website_fetching.py` |
| cryptography / Fernet | Encryption of refresh tokens before database storage | `services/gmail.py` |
| email-validator | Email validation support for Pydantic email fields | `pyproject.toml`, `schemas/email.py` |
| Pytest | Backend unit and integration tests, fixtures and monkeypatching | `tests/` |
| React 19 and TypeScript | Browser dashboard and typed API contract | `package.json`, `src/features/`, `src/lib/api/` |
| TanStack Start / Router and Vite | Existing Lovable frontend framework, routing and development/build tooling | `package.json`, `src/routes/` |
| Tailwind CSS and Radix UI | Frontend styling and UI components | `package.json`, `src/components/` |
| Vitest, Testing Library and jsdom | Frontend tests and simulated DOM environment | `src/test/`, `package.json` |
| Docker and Docker Compose | Local database, backend and frontend services, health checks and persistent volume | `compose.yaml`, `Dockerfile.backend`, `Dockerfile.frontend` |
| Git, GitHub, VS Code and Lovable | Version control, repository collaboration, editing and frontend scaffolding | Project history and build discussions; not runtime dependencies |

Python standard-library tools also used include `asyncio`, `urllib.parse`, `ipaddress`, `socket`, `secrets`, `hashlib`, `base64`, `email.message`, `datetime` and `uuid`.

The actual frontend is not Next.js, although Next.js appeared in the original plan. Installed scaffold libraries should not all be presented as technologies Bryan independently implemented or mastered. Dependency ranges are not exact installed versions; consult lockfiles for those.

## Architecture and boundaries

The frontend communicates with FastAPI through the central typed `ApiClient`. FastAPI owns validation, business rules, provider communication and database writes. SQLAlchemy accesses PostgreSQL through Psycopg. API credentials and encrypted Gmail tokens remain backend-side.

The frontend has two implementations of the same client contract:

- Connected mode calls the real backend.
- Demo mode simulates operations using isolated, ephemeral in-memory data and makes no live provider requests.

PostgreSQL uses the persistent Docker named volume `food_outreach_postgres_data`. Ports are bound to the local loopback interface. Backend and frontend images contain copied source code, so source changes require rebuilding the relevant image. This is a local development setup, not evidence of a hardened production deployment.

## Implemented workflows and technical skills represented

### Restaurant discovery and deduplication

- Calls Google Places API (New) for discovery and on-demand details such as opening hours.
- Parses provider responses into Pydantic models and maps provider fields into application data.
- Uses Google Place IDs as stable identity keys rather than assuming restaurant names are unique.
- Uses a database uniqueness constraint and PostgreSQL conflict handling to prevent duplicate restaurant rows.
- Excludes previously contacted businesses using database queries linking restaurants to outreach records.
- Keeps provider mapping logic separate from persistence and HTTP route orchestration.

Evidence: `google_places.py`, `services/discovery.py`, `crud/restaurants.py`, `services/outreach.py`, `tests/test_discovery.py`, `tests/test_google_places_api.py`.

### Website fetching and sourced contact extraction

- Fetches a restaurant website and a bounded number of contact pages, then parses HTML for public emails and social links.
- Resolves relative links with `urljoin` and retains source URLs with extracted contacts.
- Separates fetching HTML from parsing already-provided HTML.
- Applies limits for response size, deadlines and redirects.
- Checks public network addresses and same-website navigation, with safeguards against requests to private/local addresses.
- Does not treat an extracted email as proof that the mailbox exists or that delivery will succeed.

Evidence: `services/website_fetching.py`, `services/website_enrichment.py`, `schemas/contacts.py`, `tests/test_website_fetching.py`, `tests/test_website_enrichment.py`.

### Outreach persistence and workflow rules

- Stores restaurant records separately from outreach, contacts, approved emails, creator profiles, drafts and tasting plans.
- Uses primary keys, foreign keys, uniqueness constraints and database checks rather than one giant table.
- Keeps one initial outreach record per restaurant to avoid contacting it through multiple channels.
- Enforces status transitions in backend logic; permits selected backward transitions for correcting mistakes.
- Provides manual TikTok/Instagram profile opening and message copying. A separate user confirmation records social outreach as sent.
- Stores exact messages, supports business-note editing without rewriting the original sent message, and records tasting plans with Singapore-time display and UTC persistence.

Evidence: `models/`, `schemas/outreach.py`, `services/outreach.py`, `features/social-workflow.tsx`, `features/business-notes.tsx`, `features/tasting.tsx`, `tests/test_outreach.py`.

### Gmail OAuth and email sending

This integration demonstrates user-authorised API access, not an API key that grants arbitrary access to Gmail.

Connection flow:

1. Frontend calls `/gmail/connect`.
2. Backend creates random state and a PKCE verifier, hashes the verifier into a challenge, saves pending state and sets a browser cookie.
3. Browser visits the constructed Google authorization URL; the user grants the requested permissions.
4. Google redirects the browser to the backend callback with an authorization code and state. The browser separately attaches the backend's state cookie.
5. Backend checks state and exchanges the code and saved verifier with Google using its OAuth client credentials.
6. Backend checks Gmail send permission and verified email identity, encrypts the refresh token with Fernet, and upserts the single connected account.

Email workflow:

1. Verify the recipient against retained public-source evidence or a bounded website fetch, and save the user's exact approved message.
2. Decrypt the saved refresh token and exchange it for a temporary access token.
3. Lock account/outreach rows, check approval, sender identity, duplicates and rolling 24-hour limits.
4. Construct a MIME email, encode the body and Base64URL-encode the complete message for Gmail.
5. Commit `email_sending` before the external send to reserve the operation.
6. Call Gmail with `Authorization: Bearer <access token>` and record the outcome.

Important distinctions learned: state is not a permission token; the browser does not send the verifier; hashing, encoding and encryption are different operations; ordinary refresh-token exchanges do not repeat browser consent or PKCE.

Reliability: a timeout can leave delivery uncertain, so sending is not automatically retried. `sent` means Gmail accepted the request, not that the recipient read it. A crash after the reservation can leave `email_sending`; that unresolved record must not be blindly resent. This is duplicate-risk mitigation, not a guarantee of exactly-once external delivery.

Evidence: `services/gmail.py`, `email_api.py`, `models/email.py`, `schemas/email.py`, `tests/test_gmail.py`, `docs/gmail-code-walkthrough.md`.

### Gemini integration, structured writing and tool calling

The current implementation makes one direct Gemini REST request using user-confirmed restaurant facts and a saved creator-profile snapshot. It requests a structured subject, personalised paragraph and used fact IDs. Pydantic validates the output shape; Python performs limited content checks and assembles the complete message with exact creator statistics, offer and signature.

Generation never approves a message or sends outreach. Draft inputs, model identity, prompt version, status and output are persisted. A unique request ID prevents repeated successful requests from triggering another generation; failed/interrupted attempts count towards the local rolling generation limit.

An earlier version was a custom tool-calling exercise: Gemini requested the read-only `get_outreach_context` function; Python validated and executed it, then returned its result to the model. Bryan challenged the value of forcing a known function call, and the implementation was changed to direct writing. The current version has no function dispatch or sending tools.

Learning represented:

- A model requests a custom tool call; application code performs the actual execution.
- Direct generation is simpler when the application already knows the required operation.
- Structured JSON is not factual verification. Valid fact IDs do not prove that every generated claim follows from those facts.
- HTTP 200 does not guarantee a usable model output.
- AI Studio, Google Cloud projects, API credentials, model access, quotas and billing are related but distinct concepts.

Evidence: `services/gemini_drafting.py`, `drafting_api.py`, `schemas/drafting.py`, `models/drafting.py`, `features/gemini-draft.tsx`, `tests/test_gemini_drafting.py`.

## Debugging and testing experience

Concrete issues explored during development:

- `localhost` versus a Compose service hostname: host-run Python reaches the published local port; container-run Python reaches PostgreSQL using `db` on the Compose network.
- Shell environment values shadowing `.env` values during Compose interpolation; backend secrets were moved to `env_file` without redundant interpolated overrides. Container recreation reloads environment changes; restarting alone does not.
- Frontend/backend hostname mismatch affecting local OAuth cookies.
- Upstream provider errors being converted into generic backend 502 responses: the frontend stack location was where the request surfaced, not necessarily the cause.
- Google rejected `gemini-2.5-flash-lite` generation for this new-user account with 404 and recommended a newer model. A successful model-metadata lookup did not prove generation availability.
- A complete Gemini response failed an overly broad validation rule that banned any mention of followers. The rule was narrowed and regression tests were added for ordinary audience wording, unsupported counts and guarantees.
- Duplicate-outreach correctness requires database uniqueness as well as application checks and row locking; a status dictionary alone cannot enforce concurrent uniqueness.
- `session.refresh()` reloads database state into an ORM object; it does not reset the record or prepare a future session.

Backend testing uses Pytest, `TestClient`, dependency overrides, `monkeypatch`, HTTPX2 `MockTransport` and transaction/savepoint isolation. Frontend testing uses Vitest and Testing Library. Tests cover CRUD, provider parsing and failures, outreach transitions, Gmail approval/send outcomes, drafting validation and demo isolation.

The latest targeted drafting verification in this coaching session passed 26 mocked tests. This document does not certify the whole current worktree, all live integrations or production readiness. Mocked providers cannot establish live key validity, current model access, factual model accuracy or actual email delivery.

## Bryan's competence assessment

Use only: **Not Yet**, **Learning**, **Can Build Independently**.

| Area | Current evidence-based level | Evidence and remaining gate |
| --- | --- | --- |
| Python and backend control/data flow | Learning | Has traced functions, inputs, outputs and exceptions with coaching; needs an unaided related implementation. |
| SQLAlchemy and relational persistence | Learning | Understands identity, relationships, duplicate constraints and commits; has needed corrections on SELECT versus upsert and refresh semantics. |
| FastAPI validation and dependencies | Learning | Can describe injected sessions and response validation; needed correction on 422 before handler execution versus 409 inside the handler. |
| External HTTP APIs and provider schemas | Learning | Has explained provider parsing and traced actual errors; needs independent implementation/debugging evidence. |
| OAuth, tokens and email integration | Learning | Can explain state, PKCE, code exchange, refresh tokens and uncertain sends after corrections; still completing the full handler walkthrough. |
| Structured model output and grounding | Learning | Correctly distinguishes schema/content checks from factual verification and identified the limits of fact IDs; needs independent extension and tests. |
| Testing and mocking | Learning | Worked through TestClient, fake callbacks, dependency overrides, monkeypatch and cleanup; needs an independently authored test/debugging exercise. |
| Docker, configuration and networking | Learning | Has explained host/container addressing and participated in env-variable debugging; independent reproduction remains to be demonstrated. |
| Frontend integration and UI engineering | Learning | Project contains typed client and connected workflows, but Lovable/agent assistance means unaided frontend competence is not established. |
| Production security, deployment and operations | Not Yet | Local-only implementation; public authentication, operational hardening and recovery are not demonstrated. |

No area is labelled Can Build Independently solely because code exists. Promote an area only after Bryan can explain it rigorously, reproduce an important portion, make a related change without copying and diagnose relevant errors.

## Honest portfolio positioning

Suggested summary:

> Built an AI-assisted, local-first food collaboration workspace with a Python/FastAPI backend, PostgreSQL persistence and a React/TypeScript dashboard. Integrated Google Places discovery, sourced website contact extraction, structured Gemini drafting and user-approved Gmail sending with OAuth/PKCE, encrypted refresh tokens and duplicate-send safeguards. Developed tests for provider failures, workflow rules and message validation while learning to trace and debug the system.

Use this as a starting point, not a claim that every component was written independently. Support interview answers with concrete code paths, tests, bugs investigated and trade-offs. Do not invent user adoption, time saved, revenue, scale or benchmark results.

## Not implemented or not established

- Deterministic lead scoring and stored score breakdowns are not implemented.
- Automatic email → TikTok → Instagram routing and bounced-email fallback are not implemented.
- No Gmail inbox reading, response classification or automatic bounce tracking.
- No automatic follow-up scheduler, APScheduler, Redis or Celery integration.
- No completed Apple Calendar/EventKit integration; tasting planning and Google Maps navigation are different features.
- No complete permanent suppression/audit system from the original proposal.
- No TikTok/Instagram OAuth, automatic creator-stat synchronisation or automated social DMs. WhatsApp is excluded.
- No OpenAI API or Agents SDK implementation; the implemented model provider is Gemini.
- No demonstrated public deployment, multi-user authentication, production-grade access controls or exact-once email delivery.
- Website source retention and simple model guards do not amount to comprehensive factual verification.

## Guidance for an agent using this document

Inspect the repository rather than treating an older README or this snapshot as authoritative. Separate implemented functionality, demonstrated explanations and unaided competence. Ask Bryan to trace actual requests and transactions, predict failures, and make small changes with tests before upgrading competence levels. Preserve the distinction between AI-assisted development and independent work when drafting a portfolio, CV or interview narrative.

Useful next evidence would be an independently written provider-error test, an unaided small backend endpoint with validation, and a recorded explanation of the approval/reservation/send flow. These are suggested assessment exercises, not completed achievements.
