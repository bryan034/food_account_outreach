## Overview

Foodfolio helps a food creator discover Singapore businesses and manage collaboration outreach. It combines sourced contact research, personalised Gemini drafts, approved Gmail delivery and manually confirmed social messages. Persistent outreach history and tasting planning keep preparation, sending and collaboration progress separate.

## My contribution & project context

I developed the application with AI coding assistance; Lovable provided the initial frontend design skeleton.

- Implemented restaurant discovery and sourced contact extraction using Google Places and business websites.
- Integrated Gemini drafting with confirmed creator facts, structured outputs, and reviewed message generation.
- Implemented Gmail OAuth, encrypted refresh tokens, approval checks, and duplicate-send safeguards.
- Connected the frontend to persistent outreach tracking and tasting planning.
- Developed backend and frontend tests and the local container setup.

## Technical approach

### Local data ownership

A typed frontend client separates connected and isolated demo modes. FastAPI owns persistent PostgreSQL records and workflow rules. Place IDs and database constraints handle business identity and duplicate outreach; Docker Compose retains database storage across container recreation. See the [architecture guide](../docs/frontend-backend-connection.md).

### Bounded AI drafting

Gemini generates structured wording from confirmed restaurant facts and creator profiles. Python validates outputs and inserts exact statistics, the offer and signature. This limits model control but cannot verify every factual claim, so review remains required. See the [drafting design](../docs/gemini-drafting.md).

### Reviewed email delivery

OAuth with PKCE connects Gmail; encrypted refresh tokens stay backend-side. Approval records preserve exact messages. A committed send reservation precedes delivery, and uncertain outcomes are not automatically retried. Avoiding duplicates takes priority over automatic recovery. See the [email implementation](../src/automate_food_places_outreach/email_api.py).

### Failure-focused testing

Backend tests use mocked provider responses and transaction isolation to exercise validation, quota errors and uncertain sends. Frontend tests cover explicit confirmation and demo isolation. These are implemented tests, not evidence of live delivery or a current passing suite. See the [Gmail tests](../tests/test_gmail.py).

## Further development

Reconcile ORM models with migrations and verify email relationships on a fresh database. Add recovery for uncertain sends, suppression records and clearer provider errors before introducing deterministic scoring, bounded follow-ups or calendar export.
