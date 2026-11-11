---
name: nba-security-review
description: Perform a focused defensive source-code review of this NBA simulator. Use for requests to review FastAPI and Next.js authentication, authorization, account recovery, data ownership, or secret handling.
---

# NBA security review

Inspect the requested paths and relevant existing tests in read-only mode. Use static source review. Do not run the app or tests, send requests, or create exploit code. Apply fixes only in a separate implementation task requested by the user.

- Start with `backend/api.py` and the corresponding calls in `web_client/`. For a route that handles user data, trace how it identifies the session, selects records, checks ownership, and returns or updates data. Treat request-provided identifiers as untrusted inputs and look for the server-side checks that bind them to the session owner.
- For account and recovery reviews, follow the relevant code in `backend/db/auth.py`, `backend/db/recovery.py`, and `backend/email_delivery.py`. Check how sessions and recovery codes are issued, stored, expired, and invalidated. Never include credential values or recovery codes in the review.
- When configuration matters, distinguish the local SQLite setup from hosted behavior. Use `.env.example` and configuration code to establish expected settings. Treat actual deployment values as unknown unless independently provided.
- Read the existing tests covering the affected path. A missing test or an optional hardening measure is not by itself proof of a vulnerability.

Report source-supported findings in priority order. For each one, give the file and line, affected user or data, impact, and a targeted fix. Separately label observations that depend on unverified configuration or runtime behavior and explain what fact is missing. State the paths reviewed when there are no findings.
