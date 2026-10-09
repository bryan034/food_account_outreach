# Foodfolio — Bryan’s food collaboration workspace

Frontend-only React 19 + TypeScript + TanStack Router + Tailwind CSS. Your existing Python FastAPI backend and local PostgreSQL remain the sole owners of application logic and persistent records. No additional backend service or database is included.

## Local development

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

Configure your existing FastAPI app with exact frontend origins:
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
- Google IDs are Place IDs, not local IDs. Own-name restaurant creation is explicit. A 409 never triggers ID guessing; enter an existing local ID and load it.
- Outreach pagination uses offset and limit (10 per page), without a made-up total count. A full page enables Next; the following page may be empty. Status filtering is explicitly page-local because the API accepts no status filter.
- Restaurant identity lookups are cached by local ID; failed lookups are shown individually and can be retried with explicit outreach refresh.
- Status changes use outreach ID. UI offers permitted transitions only; backend 409 remains authoritative. Exact original messages are read-only. No delete controls.
- Social profile links are optional, manually supplied and unverified; they open a new tab. Copying/opening does not record sent outreach. Recording requires a separate confirmation of the exact message, with an additional explicit checkbox.
- No automatic retry of write operations. Readable backend errors are surfaced for 404, 409, 422, 502, 503 and network failures.

## Integration gaps

- No restaurant-list or Place-ID lookup endpoint. Existing IDs must be supplied manually.
- No discovery pagination input. Next-page tokens are not consumed.
- No outreach total-count field or server status filter.
- Contact storage and website enrichment are not connected. Reusable `ContactCard` defines type/value, profile URL, source URL, separate verified/usable flags and enrichment errors. It is not populated with fabricated extracted contacts.
- Email → TikTok → Instagram is the future contact priority. Email sending, AI-generated messages and creator statistics are future capabilities, not operational.
- No TikTok/Instagram OAuth, automated DMs, browser automation, or WhatsApp.

## Checks

```sh
bun run test
```
Safety tests cover transitions, pagination bounds, exact sent messages, confirmation payload, demo isolation, cache behavior, IDs, preserved tokens and no automatic retries. The connected client must be validated against your own running FastAPI; the hosted preview only exercises the demo interface.
