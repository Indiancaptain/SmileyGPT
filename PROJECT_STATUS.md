# PROJECT_STATUS.md

_Last updated: after Milestones 1–7 of the current work session (image
pipeline, vector memory, multi-model routing, admin backend, Docker
finalization, production deployment config, documentation)._

## Overall: 🟢 Production-ready core, with documented gaps

| Milestone | Status |
|---|---|
| 1. Multimodal image upload + vision pipeline | ✅ Complete, tested, frontend wired |
| 2. Vector memory integration | ✅ Complete, tested, async-safe (non-blocking) |
| 3. Multi-model routing | ✅ Complete, tested, retry/backoff added |
| 4. Admin backend | ✅ Complete, tested (role mgmt, deletion, self-lockout protection) |
| 5. Docker Compose finalized | ✅ Complete (optional env files, localhost-bound infra ports, non-root containers) |
| 6. Production deployment config | ✅ Complete (`docker-compose.prod.yml` overlay) |
| 7. Documentation | ✅ Complete (README, API.md, TESTING.md, ARCHITECTURE.md, this file) |
| 8. Full project audit | ✅ Complete (see below) |
| 9. Fix discovered issues | ✅ Complete (see CHANGELOG.md) |
| 10. Repeat review/refactor | 🔁 Ongoing — see TODO.md for what's left |

## Test suite

**55/55 backend tests passing.** Frontend has no component/e2e suite yet
(tracked in TODO.md); type-checking (`tsc --noEmit`) and production
build (`next build`) are both verified clean after every frontend change.

## What a fresh pair of eyes should know

- The backend is fully async, Postgres + Redis + (optional) Chroma, JWT
  auth, SSE streaming chat with real multimodal image support.
- The frontend is Next.js 15 / React 19 / TypeScript / Tailwind, builds
  clean, talks to the backend exclusively through a Next.js rewrite proxy
  (`/api/backend/*`) so the browser never sees the backend's real origin.
- Everything not marked complete above is listed, in priority order,
  in `TODO.md` — that file is the actionable backlog; this file is the
  snapshot.

## Milestone: Security headers middleware — Complete

- Added `SecurityHeadersMiddleware` (`app/middleware/security_headers.py`):
  sets `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
  `Referrer-Policy: strict-origin-when-cross-origin`,
  `Permissions-Policy` (denies geolocation/camera/microphone),
  `X-XSS-Protection: 0`.
- Registered after `RateLimitMiddleware` in `main.py`; applies to all
  responses including error responses.
- 2 new tests (`test_security_headers.py`), verified on both success and
  401 paths. Full suite: 51/51 passing.

## Milestone: Final production engineering audit — Complete

Full-repository audit against: security, auth/authz, dependency CVEs,
Docker practices, performance, memory leaks, async blocking, SQL
performance/indexing, API validation, logging, error handling, dead
code, duplication, config, scalability, maintainability.

**Real issues found and fixed (12):**
1. **Critical — CVE-2026-48710 "BadHost"**: transitively-resolved
   Starlette was 0.38.6, far below the 1.0.1 patch for a Host-header
   auth-bypass vulnerability. Upgraded `fastapi` 0.115.0→0.136.1 and
   pinned `starlette==1.3.1` explicitly. Added a regression test
   (`test_dependency_security.py`) that fails the suite if this ever
   regresses below 1.0.1.
2. **High — CVE-2024-33663**: `python-jose==3.3.0` algorithm-confusion
   vulnerability. Upgraded to `3.4.0`. (Low real exploitability here
   since we only ever use HS256 with an explicit algorithm allow-list,
   but the fix is free and correct.)
3. **High — CVE-2024-53981 / CVE-2026-42561**: `python-multipart==0.0.9`
   had two DoS vulnerabilities directly reachable via `/files/upload`.
   Upgraded to `0.0.27`.
4. **High — no production-secret guard**: nothing prevented deploying
   with `ENV=production` while `SECRET_KEY` was still the public
   placeholder value (allows forging any JWT, including admin). Added
   a hard startup failure in `main.py`'s `lifespan`.
5. **Medium — async-blocking disk I/O**: `files.py`'s upload write,
   `chat.py`'s image read+base64-encode, and the Pillow content
   verification all ran synchronously inside `async def` handlers,
   blocking the event loop for every concurrent request during that
   I/O. Wrapped all three in `asyncio.to_thread`.
6. **Medium — own error handler could crash**: `RequestValidationError`
   handler passed `exc.errors()` straight into `JSONResponse`, which
   can contain non-JSON-serializable objects (e.g. raw exceptions in
   Pydantic's `ctx`), turning a clean 422 into an unhandled 500. Fixed
   with a `json.dumps(..., default=str)` round-trip.
7. **Medium — missing composite DB indexes**: `conversations`/`messages`
   had single-column indexes that didn't match the actual query
   patterns (always "for this user/conversation, ordered by
   updated_at/created_at"). Replaced with composite indexes via
   migration `0002`.
8. **Medium — no upload content verification**: client-supplied
   `Content-Type` was trusted without checking actual file bytes.
   Added Pillow-based image verification and PDF magic-byte checking
   (also closed: `Pillow` and `tenacity` were both declared dependencies
   that were never actually used anywhere in the code).
9. **Medium — no token revocation**: there was no logout endpoint at
   all; a captured token stayed valid until natural expiry. Added
   Redis-backed jti denylist, `POST /auth/logout`, and refresh-token
   rotation (a used refresh token is immediately revoked).
10. **Low — dead dependency**: `slowapi` was declared in
    `requirements.txt` but never imported (the app uses its own Redis
    rate limiter). Removed.
11. **Low — missing security headers**: added
    `SecurityHeadersMiddleware` (nosniff, DENY framing, referrer
    policy, permissions policy).
12. **Low — frontend memory/resource leak**: `useVoice.ts` never
    stopped an active `SpeechRecognition` session or cancelled queued
    `speechSynthesis` on component unmount, leaving the mic active or
    audio queued with nothing observing the result. Added unmount
    cleanup.

**Also verified, no issue found (left unchanged):** bcrypt truncation
behavior at the schema's `max_length=128` boundary; SQL N+1 patterns in
conversation/message listing; Redis client concurrency safety; frontend
`npm audit` residual (2 moderate, transitive-only inside Next.js's
bundled `postcss`, not reachable at runtime, no non-breaking fix
available — already at latest 15.5.x patch).

Full suite: **55/55 passing.**

During this session's audit pass, the following real defects were found
and corrected (see `CHANGELOG.md` for details):

1. Duplicate `from typing import List` import in `memory_service.py`.
2. `memory_service` calls were synchronous and blocking the event loop.
3. `LLMService.resolve_model` silently overrode an explicit, valid user
   model choice whenever images were attached.
4. `tenacity` was a declared dependency but never actually used —
   no retry logic existed for transient LLM API failures.
5. `admin.toggle_active` returned `None` (not a 404) for an unknown user id.
6. `admin` routes had no protection against an admin locking themselves
   out (deactivating, demoting, or deleting their own account).
7. `UserOut` schema was missing the `is_active` field entirely, so the
   admin UI couldn't actually render active/inactive status.
8. The frontend uploaded files but never sent `attachment_ids` to
   `/chat/stream` — the vision pipeline was unreachable from the UI.
9. `docker-compose.yml` referenced `.env` files that don't exist by
   default, and `env_file` was not marked optional, so a first-time
   `docker compose up` would fail outright.
10. Postgres/Redis ports were published on all interfaces instead of
    localhost-only.
11. Both Dockerfiles ran their process as root.
12. Next.js/React were pinned to a version line (14.2.15 / React 18)
    that is EOL with multiple critical/high CVEs; upgraded to a current
    patched release.
13. FastAPI app used the deprecated `@app.on_event("startup")` pattern.
14. Pydantic schemas used the deprecated `class Config` style instead of
    `ConfigDict`.
15. bcrypt/passlib version mismatch caused password hashing to raise at
    runtime (`bcrypt==4.1+` removed an attribute `passlib==1.7.4` reads).

None of these are hypothetical — each was caught by an actual failing
test, a build/audit tool, or a targeted manual review, not by inspection
alone.
