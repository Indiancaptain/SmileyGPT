# CHANGELOG.md

All notable changes to SmileyGPT. This project is early-stage and
doesn't yet follow strict semver releases — entries are grouped by
development session/milestone instead of version number.

## Unreleased — Final production engineering audit

### Security
- **Critical**: upgraded `fastapi` 0.115.0→0.136.1 and pinned
  `starlette==1.3.1` — the previously-resolved Starlette (0.38.6) was
  vulnerable to CVE-2026-48710 ("BadHost"), a Host-header parsing flaw
  that can desync `request.url.path` from the actually-routed path.
- **High**: upgraded `python-jose` 3.3.0→3.4.0 (CVE-2024-33663,
  algorithm confusion).
- **High**: upgraded `python-multipart` 0.0.9→0.0.27 (CVE-2024-53981,
  CVE-2026-42561 — both DoS, directly reachable via `/files/upload`).
- **High**: added a hard startup failure if `ENV=production` with the
  default placeholder `SECRET_KEY` — previously nothing prevented
  deploying with a publicly-known JWT signing secret.
- Added Redis-backed token revocation: `POST /auth/logout`, refresh
  token rotation (single-use), and revocation checks in
  `get_current_user`/`/auth/refresh`.
- Added `SecurityHeadersMiddleware`.
- Added upload content verification (Pillow image validation, PDF
  magic-byte check) instead of trusting client-supplied `Content-Type`.

### Performance
- Fixed three instances of blocking synchronous disk I/O inside async
  route handlers (`files.py` upload write + Pillow verification,
  `chat.py` image read/base64-encode) by moving them to
  `asyncio.to_thread`.
- Replaced single-column indexes on `conversations.user_id` and
  `messages.conversation_id` with composite indexes matching the
  actual query patterns (migration `0002`).

### Fixed
- `RequestValidationError` handler could itself crash (500) on error
  payloads containing non-JSON-serializable values.
- `useVoice.ts`: added unmount cleanup so an active mic session or
  queued speech synthesis doesn't keep running after the component
  using it unmounts.

### Removed
- `slowapi` — declared dependency, never imported.

## Unreleased — Security headers middleware

### Added
- `SecurityHeadersMiddleware`: `X-Content-Type-Options`, `X-Frame-Options`,
  `Referrer-Policy`, `Permissions-Policy`, `X-XSS-Protection` on every response.
- `test_security_headers.py` (2 tests).

## Unreleased — Milestones 1–9 (multimodal, memory, admin, Docker, docs, audit)

### Added
- Multimodal image pipeline: uploaded images are resolved by owner,
  base64-encoded, and injected as OpenAI-format `image_url` content
  blocks into the chat request; routed automatically to `LLM_VISION_MODEL`.
  Wired end-to-end into the frontend (`ChatWindow.tsx` now actually sends
  `attachment_ids`, with a visible attached-file chip and remove button).
- Retry-with-exponential-backoff (via `tenacity`) around the initial LLM
  connection, for transient connection/timeout/rate-limit errors only —
  never retried once tokens have started streaming to the client.
- Admin backend: role promotion/demotion (`PATCH
  /admin/users/{id}/role`), user deletion (`DELETE
  /admin/users/{id}`), and self-lockout protection (an admin can't
  deactivate, demote, or delete their own account).
- Admin frontend: role toggle, activate/deactivate, and delete actions
  wired into the `/admin` user table, with confirmation on delete and
  disabled state on one's own row.
- `docker-compose.prod.yml` production overlay: multi-worker backend,
  no host-exposed Postgres/Redis ports, resource limits, `DEBUG=false`.
- `.dockerignore` for both services.
- 23 new backend tests: `test_vision.py`, `test_memory_service.py`,
  `test_llm_service.py`, `test_admin.py` (36 total, up from 9).
- `README.md`, `API.md`, `TESTING.md`, `PROJECT_STATUS.md`, `TODO.md`,
  this changelog.

### Changed
- `memory_service.py`: all Chroma calls now run through
  `asyncio.to_thread` so embedding computation never blocks the event
  loop; memory writes from `chat.py` are now genuinely fire-and-forget
  via `asyncio.create_task` instead of (previously, silently) blocking
  the stream's `done` event.
- `LLMService.resolve_model` now takes `has_images` as a parameter and
  only falls back to `LLM_VISION_MODEL` when no valid model was
  explicitly requested — an explicit, valid user model choice is no
  longer silently overridden just because the request has images.
- Upgraded Next.js `14.2.15` → `15.5.20` and React `18.3.1` → `19.2.3`
  (14.x is EOL with multiple critical/high-severity RSC CVEs disclosed
  Dec 2025; see the Next.js security advisory). Bumped `postcss` to
  `8.5.10` to clear a separate XSS advisory.
- `docker-compose.yml`: `env_file` entries marked `required: false` so
  a missing `.env` doesn't block `docker compose up`; Postgres/Redis
  ports now bind to `127.0.0.1` only instead of all interfaces.
- Both Dockerfiles now run their process as a dedicated non-root user.
- FastAPI app switched from the deprecated `@app.on_event("startup")`
  to a `lifespan` context manager.
- Pydantic schemas switched from the deprecated `class Config` style to
  `ConfigDict(from_attributes=True)`.

### Fixed
- Duplicate `from typing import List` import in `memory_service.py`.
- `bcrypt==4.1+` / `passlib==1.7.4` incompatibility that raised
  `ValueError: password cannot be longer than 72 bytes` on every
  password hash — pinned `bcrypt==4.0.1`.
- `admin.toggle_active` returned `None` instead of a `404` for an
  unknown user id.
- `UserOut` schema was missing `is_active` entirely, so the admin UI's
  active/inactive column silently rendered nothing — added the field.
- `pydantic.EmailStr` requires `email-validator`, which wasn't declared
  as a dependency; added it.
- pytest-asyncio loop-scope mismatch between the session-scoped DB
  fixture and function-scoped default, causing every test to error.

## Milestone 0 — Initial build

- FastAPI backend: JWT auth, Postgres via async SQLAlchemy + Alembic,
  Redis-backed rate limiting, structured logging (loguru), global error
  handlers, conversation CRUD + search, SSE streaming chat endpoint,
  file upload with type/size validation, Chroma-backed long-term memory
  (lazy-loaded, degrades gracefully if unavailable), admin stats/user-list.
- Next.js 14 frontend (later upgraded — see above): login/register,
  chat UI with markdown + syntax highlighting, dark/light mode, browser
  Web Speech API for voice input/output, sidebar with search, admin
  dashboard page.
- `docker-compose.yml`, both Dockerfiles, Alembic initial migration.
- Initial backend test suite (`test_auth.py`, `test_conversations.py`, 9 tests).
- `ARCHITECTURE.md` established as the persistent project-state document.
