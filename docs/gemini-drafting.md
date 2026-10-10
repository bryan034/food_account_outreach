# Gemini writing for personalised outreach

## Current design: one writing request, no function calling

The earlier grounded-selection-v1 implementation was a tool-calling learning demonstration.
It forced a read-only function call, then selected predefined sentences. New drafts use
grounded-writing-v2: one direct Gemini API request writes an email subject and a personalised
restaurant paragraph using your confirmed creator profile and restaurant facts.

Python still assembles the greeting, creator introduction, exact statistics/TikTok URL,
complimentary tasting for one TikTok review, hosted-meal disclosure, no creator fee and:
`Best,\nBryan's dining room`. Gemini does not control that signature.

No tools, agents, browsing, arbitrary dispatch or sending capability are supplied to Gemini.
Generation is separate from Gmail approval/send and manually confirmed social outreach.

## Setup

Create a key in [Google AI Studio](https://aistudio.google.com/api-keys) and add literal
assignments to the ignored root `.env`:

```dotenv
GEMINI_API_KEY=your_actual_gemini_api_key
GEMINI_MODEL=gemini-3.5-flash-lite
GEMINI_DAILY_GENERATION_LIMIT=20
```

- The key authenticates backend requests. Never put it in VITE variables, Git or chat.
- The model is an ID, not a URL; availability/quota depend on your project.
- The generation limit counts attempts over a rolling 24 hours, including failures.
  One new draft now uses one API request. This is not a Cloud account-wide spending cap.

After changing environment values, run `docker compose up -d`.
`up` updates/starts the services; `-d` runs them in the background. The backend's
`env_file` loads `.env`. Restart alone retains the container's old environment.
After changing source code, use `docker compose up --build -d`; `--build` includes new
code in the images. The named database volume is preserved.

In Settings, save and confirm your creator name, TikTok URL, views, shares and minimum
views on every video. Keep these claims current. Then Prepare outreach → Draft with Gemini:
enter the independently confirmed business name/type and optional feature detail/source.
Confirm facts and Generate. Existing edits require explicit replacement permission.
Review/edit the new message before separately approving or sending it.

Demo mode remains locally simulated and makes no model requests. Manual writing remains
available without Gemini. Optional source pages are recorded but not fetched/verified by
this feature. Use your own knowledge or the public business website, not copied Google
listing data in permanent snapshots.

## Privacy change

Unlike v1, v2 sends the confirmed public creator name, TikTok URL and statistics to Gemini,
along with restaurant facts and the fixed offer. It does not send Gmail credentials,
API keys in the prompt, private replies, contact recipients or unrelated database records.
The UI now states this explicitly. Unpaid-service terms allow product improvement and
human review; do not enter sensitive or confidential information.

## Files changed

- `services/gemini_drafting.py`: one writing call, grounding checks, fixed-section rendering.
- `schemas/drafting.py`: ModelWriting replaces ModelSelection.
- `drafting_api.py`: supplies the creator snapshot and stores generated writing.
- `src/features/creator-profile.tsx`, `src/features/gemini-draft.tsx`: current privacy/cost wording.
- `tests/test_gemini_drafting.py`: writing protocol, profile, signature and failure tests.

No migration is required. The existing `model_selection` JSONB column stores v2's writing
object as well as historical v1 selections; `prompt_version` identifies which shape applies.
Existing drafts are not regenerated or overwritten.

## Code trace, line by line through the changed logic

### Schema: ModelWriting

`subject: str = Field(min_length=1, max_length=200)` requires a nonblank bounded subject.
`personalised_paragraph` requires up to 600 characters of generated prose.
`used_fact_ids` lists category and/or detail references; unknown IDs are rejected.
`extra="forbid"` rejects extra response fields.
The field validator rejects newline/control characters, including subject-header injection.

### restaurant_facts(inputs)

The business-kind dictionary translates the confirmed enum into a readable noun.
`facts = {"category": noun}` always supplies one known fact.
The `if` adds a detail only when the user supplied it.
`return facts` gives the prompt a named set of facts rather than generic instructions.

### generate_writing(client, config, inputs, profile)

`client` is the injected HTTPX2 client. `config` contains the model/key.
`inputs` contains the validated restaurant request; `profile` is the saved creator snapshot.
The URL inserts the configured model ID into Google's generateContent endpoint.

The `public_profile` comprehension copies only the five permitted creator fields:
name, TikTok URL, views, shares and minimum views. It excludes database metadata/credentials.
The `context` dictionary combines that profile with restaurant name, named facts, channel,
source type and the fixed offer.

`instructions` gives Gemini an actual writing task: a friendly neutral subject and
1–2 personalised sentences, not selection among predefined sentences. It requires using
only supplied facts, treats inputs as untrusted data, and forbids unsupported menu/location,
audience, prior-experience, engagement, positive-review or extra-deliverable claims.
It also tells the model to omit sections Python owns.

`systemInstruction` supplies those instructions.
`contents` contains one user-role JSON context.
`json.dumps(context, ensure_ascii=False)` turns our dictionary into text while keeping
Unicode readable. Serialization is not a security boundary.
There are no `tools`, `toolConfig`, `functionCall` or `functionResponse` request fields.

`generationConfig` bounds output and requests JSON shaped like ModelWriting.
`ModelWriting.model_json_schema()` creates the schema description given to Gemini.
`await client.post(...)` executes the sole model request.
The API key is in the x-goog-api-key header, not the URL. Timeout is configured to 30 seconds.
Network/provider errors become safe DraftingError messages, without provider-body logging.
HTTP 402 produces a specific prepaid-billing error rather than a generic upstream message.
It does not trigger retries, modify billing or enable paid services automatically.

The response parser takes the first candidate, requires normal STOP completion and model
role, checks the parts list, and rejects unexpected function calls. It joins final text parts,
excluding thought parts, then calls `ModelWriting.model_validate_json(text)`.
That parses/validates the structured answer. It does not prove factuality.

### validate_writing(writing, inputs)

Checks that fact references are available and not duplicated. Detail references fail if
no detail was supplied. Additional guards reject links/handles, obvious statistics/performance
claims, added numeric quantities and a model-supplied signature. The numeric check compares
numbers against the supplied restaurant name and cited facts.

These guards are deliberately limited. A model can make an unsupported claim using ordinary
words or cite a real fact ID incorrectly. There is no claim of complete semantic verification.
Source references plus manual review remain necessary; failed validation leaves current edits
unchanged and records a failed generation rather than silently falling back to a template.

### render_message(inputs, profile, writing)

Builds the greeting from confirmed restaurant_name.
Builds the creator introduction/TikTok URL/statistics from the saved profile, not model prose.
Inserts `writing.personalised_paragraph`, the actual new text from Gemini.
Appends the unchanged tasting offer/disclosure/no-fee terms and fixed signature.
Returns `writing.subject, message`.

### drafting_api.py orchestration

The existing profile lock, rolling attempt limit and unique request UUID still reserve
generation before the external request. Failed/interrupted attempts count too; no auto-retry.
`generate_writing(..., inputs, profile_inputs)` receives this draft's snapshots.
`render_message(..., writing)` assembles the approved structure.
`draft.model_selection = writing.model_dump()` retains generated prose and fact references.
`ready` is saved only after validation succeeds. Existing request IDs replay the original
saved draft, even if produced by v1; another explicit generation uses a new UUID.

Drafting does not create outreach attempts or mark businesses contacted. Actual messages are
still separately reviewed/approved and saved exactly before Gmail sending. Manual social
sending remains unchanged.

## Verification and boundaries

Tests use mocked Gemini requests and outer database transactions with savepoints. No real
email/model request is required for unit/integration tests. Tests check one request, fresh
generated wording, creator-profile updates, signature/statistic preservation, fact references,
response validation, forbidden tool calls, malformed output, failure reservations and replay.
Live provider compatibility/access must be checked with your configured key separately.

This is still a local single-user app. Before public deployment, add authentication,
ownership, per-user quotas and abuse controls. Origin checks alone are not authentication.

References: [structured outputs](https://ai.google.dev/gemini-api/docs/generate-content/structured-output),
[API keys](https://ai.google.dev/gemini-api/docs/api-key),
[data terms](https://ai.google.dev/gemini-api/terms).

Understanding exercise: Where is Gemini's new paragraph inserted? If it returns a different
signature, can that replace the application's fixed closing? Why doesn't a valid fact ID
prove that every word in the paragraph is factual?
