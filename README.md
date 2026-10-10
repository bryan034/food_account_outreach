# Foodfolio — Bryan’s food collaboration workspace

React 19 + TypeScript + TanStack Router + Tailwind CSS connected to the Python FastAPI backend and local PostgreSQL in this repository. FastAPI owns persistent records and business rules; the isolated demo makes no backend calls.

See [frontend/backend connection guide](docs/frontend-backend-connection.md) for startup commands, request traces and new concepts.

Email outreach supports Gmail OAuth, sourced business emails, explicit review/approval, persistent exact messages and duplicate-safe sending. Configure your account using the [Gmail setup and code explanation](docs/gmail-setup.md). Until configured, real email sending is disabled; Demo only simulates it.

Gemini writes an outreach subject and personalised paragraph in one structured-output API request using your confirmed creator profile and restaurant facts. Python inserts your exact statistics, offer and signature. See [Gemini setup and code walkthrough](docs/gemini-drafting.md). Generation never approves or sends outreach.

## Local development

Start the entire local stack (database, backend and frontend) with:

```sh
docker compose up --build -d
```

Open `http://127.0.0.1:5173`, switch Settings to Connected, and use API URL `http://127.0.0.1:8000`. Existing PostgreSQL data is retained. See [Compose setup and line-by-line explanation](docs/docker-compose.md). Stop separate local Vite/Uvicorn processes first to avoid port conflicts. The commands below remain an alternative for running the frontend directly on your Mac.

```sh
bun install
# or npm install
```
Create `.env.local`:
```dotenv
VITE_API_BASE_URL=http://localhost:8000
```
Then run:
```sh
bun run dev --host 127.0.0.1 --port 8080
# or npm run dev -- --host 127.0.0.1 --port 8080
```
Start your existing FastAPI backend separately. Open `http://127.0.0.1:8080`, go to Settings, choose Connected mode and Apply settings, then check backend health. The Settings URL overrides the environment default in that browser. Only mode and public URL are stored in browser storage; no business records are stored there.

A hosted Lovable preview cannot reliably access FastAPI running on your computer. Default Demo Mode is entirely in-memory, uses the same `ApiClient` interface and makes zero live API calls. Sample restaurants and messages are fictional. Changes reset when the demo client/session is recreated. No social messages are sent by the app in either mode.

## FastAPI CORS

The backend already configures CORS. Set `FRONTEND_ORIGINS` to a comma-separated list of exact allowed origins if needed. Defaults include localhost and 127.0.0.1 on ports 5173 and 8080. The equivalent configuration is:
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8080", "http://localhost:8080"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Content-Type"],
)
```
Origin includes scheme, hostname and port. Use explicit deployed origins for production, never a production wildcard. These endpoints currently specify no authentication; if your backend adds auth, extend the central client appropriately. Google Places, OpenAI and Gmail secrets remain exclusively in FastAPI, never in VITE variables.

## Contract and safety

- Central typed client: `src/lib/api/types.ts`, `client.ts`, and `demo.ts`.
- Only pressing Search triggers discovery. No retries, polling, automatic refresh or automatic pagination. Returned `next_page_token` is retained in discovery state but never submitted.
- Backend handles previously contacted business exclusion; frontend does not duplicate this filter.
- Place IDs link discovery to outreach internally; neither provider IDs nor local IDs are shown in business/outreach details. Confirming manual outreach creates or reuses the restaurant and saves the exact message in one transaction. No separate record-creation form is needed. An optional user-written business label is stored; without it, history shows “Contacted business”.
- Outreach pagination uses offset and limit (10 per page), without a made-up total count. A full page enables Next; the following page may be empty. Status filtering is explicitly page-local because the API accepts no status filter.
- Restaurant identity lookups are cached by local ID; failed lookups are shown individually and can be retried with explicit outreach refresh.
- Status changes use outreach ID. UI offers permitted transitions only; backend 409 remains authoritative. Exact original messages are read-only. No delete controls.
- Backward corrections preserve the original outreach record. Moving to tasting opens a planner; saving persists the plan and status together. Dates are entered/displayed in SGT. Cancelling makes no write. Google Maps handles directions from the user's location; GPS is not stored.
- Opening hours use an on-demand Google Place Details request; missing hours and upstream errors are shown explicitly. This field incurs the Google Enterprise SKU, rather than making every discovery search request it.
- Social profile links are optional, manually supplied and unverified; they open a new tab. Copying/opening does not record sent outreach. Recording requires a separate confirmation of the exact message, with an additional explicit checkbox.
- No automatic retry of write operations. Readable backend errors are surfaced for 404, 409, 422, 502, 503 and network failures.

## Integration gaps

- No full restaurant-list endpoint. Confirmed outreach resolves business identity automatically from its Place ID.
- No discovery pagination input. Next-page tokens are not consumed.
- No outreach total-count field or server status filter.
- Public contacts can be discovered from business websites and retained with sources. Email uses an explicit source-review/approval step; extraction does not prove mailbox deliverability.
- Gmail sends only approved messages through OAuth. Automatic Email → TikTok → Instagram routing, AI-generated messages, creator statistics and reply/bounce polling remain future capabilities.
- No TikTok/Instagram OAuth, automated DMs, browser automation, or WhatsApp.

## Checks

```sh
bun run test
```
Safety tests cover transitions, pagination bounds, exact sent messages, confirmation payload, demo isolation, cache behavior, IDs, preserved tokens and no automatic retries. The connected client must be validated against your own running FastAPI; the hosted preview only exercises the demo interface.
