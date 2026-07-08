# SmileyGPT — Architecture & Project State

This document is the single source of truth for what has been built, what
decisions were made (and why), and what remains. Update it after every
milestone rather than letting knowledge live only in chat history. See
also `PROJECT_STATUS.md` (milestone snapshot), `TODO.md` (actionable
backlog), and `CHANGELOG.md` (chronological history of changes).

## 1. Status summary

| Layer | Status | Notes |
|---|---|---|
| Backend (FastAPI) | ✅ Implemented, tested | 55/55 pytest passing |
| Auth (JWT) | ✅ Implemented, tested | register/login/refresh/logout, bcrypt hashing, Redis-backed jti revocation denylist, refresh-token rotation |
| Conversations CRUD + search | ✅ Implemented, tested | ILIKE search across titles + message content |
| Streaming chat (SSE) | ✅ Implemented, tested | Graceful no-op fallback when `LLM_API_KEY` unset |
| Multi-model routing | ✅ Implemented, tested | Explicit valid model choice always wins, even for image requests; vision-model fallback only when no valid model requested; retry-with-backoff on transient connection errors |
| Long-term memory (Chroma) | ✅ Implemented, tested, optional | Lazy-loaded; degrades to no-op if ML deps absent; all calls run via `asyncio.to_thread` so embedding computation never blocks the event loop; memory writes are genuine fire-and-forget background tasks |
| File uploads | ✅ Implemented, tested | Local disk storage; type/size validated |
| Image understanding | ✅ Implemented, tested, wired end-to-end | `attachment_ids` resolved to owned `UploadedFile` rows, base64-encoded into OpenAI-format `image_url` blocks, routed to `LLM_VISION_MODEL`. Owner-scoped (cross-user attachment IDs are silently ignored, not leaked). Frontend actually sends `attachment_ids` and shows an attachment chip with remove button. |
| Rate limiting | ✅ Implemented | Redis fixed-window, fails open if Redis is down |
| Logging | ✅ Implemented | loguru, rotating file + stdout; admin actions logged |
| Error handling | ✅ Implemented | Global handlers for HTTPException/validation/unhandled |
| Security headers | ✅ Implemented | `SecurityHeadersMiddleware`: nosniff, DENY framing, referrer policy, permissions policy |
| Admin dashboard (API) | ✅ Implemented, tested | stats, user list, toggle-active, role promotion/demotion, deletion — all with self-lockout protection |
| Admin dashboard (UI) | ✅ Implemented | `/admin` page: stats, user table, role toggle, activate/deactivate, delete (own row disabled) |
| DB schema/migrations | ✅ Implemented | Alembic, migrations `0001` (initial) + `0002` (composite indexes matching real query patterns) |
| Frontend (Next.js/TS/Tailwind) | ✅ Implemented, builds clean | `next build` and `tsc --noEmit` both pass; Next.js 15.5.20 / React 19.2.3 (patched, non-EOL) |
| Markdown + code highlighting | ✅ Implemented | react-markdown + remark-gfm + rehype-highlight |
| Dark/light mode | ✅ Implemented | CSS-var based theme, persisted to localStorage |
| Voice input/output | ✅ Implemented | Browser-native Web Speech API (no backend needed) |
| Docker deployment | ✅ Implemented | `docker-compose.yml` (dev, optional env files, localhost-bound infra ports, non-root containers) + `docker-compose.prod.yml` (multi-worker, resource limits, no exposed infra ports) |
| Documentation | ✅ Implemented | README.md, API.md, TESTING.md, PROJECT_STATUS.md, TODO.md, CHANGELOG.md, this file |
| Tests | ✅ Implemented (backend) | 55 tests across 12 files, see `TESTING.md`. Includes a dependency-CVE regression guard. Frontend has type/build verification but no component test suite yet (see TODO.md #1) |

## 2. Key architecture decisions (and why)

- **Auth: custom JWT, not Clerk/Auth.js.** The brief allowed either. A
  self-contained JWT flow (access + refresh tokens, bcrypt hashing) keeps
  the whole stack runnable offline with zero third-party signup, which
  matters for a project meant to be cloned and run via `docker compose up`.
  Swapping to Clerk/Auth.js later means replacing `app/core/security.py`
  and the `/auth` routes; the rest of the app only depends on
  `get_current_user`, so the blast radius is contained.
- **Memory: Chroma, not Qdrant.** Chroma runs embedded/persisted-to-disk,
  so there's one fewer container to run and configure. `memory_service.py`
  isolates all vector-store calls behind `MemoryService`, so swapping in a
  Qdrant client later is a localized change. Known tradeoff: SQLite-backed
  persistence can hit lock contention under multiple concurrent Uvicorn
  workers writing heavily — documented in `docker-compose.prod.yml` and
  `TODO.md` #4.
- **LLM access: OpenAI-compatible client, provider-agnostic.** Pointing
  `LLM_BASE_URL` at OpenAI, Groq, or a local Ollama OpenAI-compat shim all
  work without code changes. Model allow-list lives in `AVAILABLE_MODELS`.
  An explicit, valid model choice from the caller always wins over the
  vision-model default, including for image requests — the vision default
  is purely a fallback for when no valid model was requested.
- **Streaming: raw SSE over `StreamingResponse`, not WebSockets.** Simpler
  to reason about, works through standard reverse proxies, and one-way
  token streaming doesn't need full duplex.
- **IDs: `String(36)` UUIDs, not Postgres-native `UUID` type.** Keeps the
  same SQLAlchemy models portable across Postgres (production) and SQLite
  (fast in-memory-style tests), avoiding a second "test-only" schema to
  maintain.
- **Voice: Web Speech API in the browser, not a backend STT/TTS service.**
  Zero additional infra, zero added latency/cost, and it's a real, working
  feature today rather than a stub — tradeoff is Firefox lacks
  `SpeechRecognition` support, handled via a `supported` feature flag in
  `useVoice`.
- **Retry policy: only the pre-stream connection is retried.** Transient
  connection/timeout/rate-limit errors get up to 3 attempts with
  exponential backoff (`tenacity`) before the model starts streaming
  tokens. Once tokens have reached the client, failures are surfaced
  inline instead of retried — replaying a partial stream would duplicate
  content the client already rendered.
- **Docker: dev file has safe defaults, prod concerns live in an
  overlay.** `docker-compose.yml` alone is enough to `docker compose up`
  with zero configuration (backend `config.py` defaults match the
  compose network's service names/ports). `docker-compose.prod.yml`
  layers on multi-worker serving, resource limits, and removes
  host-exposed infra ports — kept separate so the dev file stays simple
  and the prod concerns are explicit and opt-in.
- **Token revocation: Redis denylist keyed by jti, not a stateful
  session store.** Every JWT gets a unique `jti`; logout/rotation add
  only that specific token's jti to Redis with a TTL matching its
  remaining natural lifetime, so the denylist self-cleans and never
  grows unbounded. This keeps auth mostly stateless (no session table)
  while still allowing real revocation on logout — the gap the initial
  JWT-only design left open.
- **Dependency pinning is defense-in-depth, not just style.** `fastapi`/
  `starlette` are pinned to versions confirmed (via test
  `test_dependency_security.py`) to be patched against CVE-2026-48710;
  `python-jose`/`python-multipart` similarly pinned past their known
  CVEs. Pin bumps that would regress below these floors should fail the
  test suite before they fail in production.

## 3. Known gaps / TODO

See `TODO.md` for the full, actively-maintained backlog in priority
order. Headline items: no frontend test suite yet, no automatic
refresh-token rotation on the frontend, local-disk file storage (fine
for one instance), and the Chroma multi-worker concurrency caveat above.

## 4. Directory map

```
smileygpt/
├── backend/                 # FastAPI service
│   ├── app/
│   │   ├── api/routes/       # auth, users, conversations, chat, files, admin
│   │   ├── api/deps.py       # get_current_user / require_admin
│   │   ├── core/             # config, security, logging
│   │   ├── db/session.py     # async engine/session
│   │   ├── middleware/       # Redis rate limiter
│   │   ├── models/models.py  # SQLAlchemy ORM models
│   │   ├── schemas/schemas.py# Pydantic request/response schemas
│   │   ├── services/         # llm_service.py, memory_service.py
│   │   └── main.py           # app factory, lifespan, middleware, exception handlers
│   ├── alembic/               # migrations
│   ├── tests/                 # pytest suite (SQLite-backed), 36 tests / 6 files
│   ├── Dockerfile             # non-root user, healthcheck
│   └── .dockerignore
├── frontend/                 # Next.js 15 / React 19 / TS / Tailwind
│   ├── src/
│   │   ├── app/               # login, register, chat, admin routes
│   │   ├── components/        # Sidebar, ChatWindow, Markdown, ThemeProvider
│   │   ├── hooks/useVoice.ts  # Web Speech API wrapper
│   │   └── lib/                # api.ts client, streamChat.ts SSE parser
│   ├── Dockerfile             # non-root user, healthcheck
│   └── .dockerignore
├── docker-compose.yml         # dev: safe defaults, optional .env, localhost-only infra ports
├── docker-compose.prod.yml    # prod overlay: multi-worker, resource limits, no exposed infra ports
├── README.md / API.md / TESTING.md
├── PROJECT_STATUS.md / TODO.md / CHANGELOG.md
└── ARCHITECTURE.md            # this file
```

## 5. How to resume work in a future session

1. Read this file first, then `PROJECT_STATUS.md` and `TODO.md`.
2. Run `cd backend && python -m pytest tests/ -v` — should be 36/36 green.
   If not, something regressed; fix before adding features.
3. Run `cd frontend && npx tsc --noEmit && npm run build` — must be clean.
4. Pick the next item from `TODO.md`, in priority order.
5. Follow the engineering loop for the item: Analyze → Design →
   Implement → Test → Review → Refactor → Optimize → Security Audit →
   Documentation.
6. Update `PROJECT_STATUS.md`, `TODO.md`, `CHANGELOG.md`, and this
   file's status table after finishing any item — don't let any of the
   four drift out of sync with the actual code.
