# Testing Guide

## Backend

The backend test suite runs against SQLite in-memory-style (a real
`test.db` file, dropped after the session) rather than Postgres, so it
needs no Docker services running — just the Python dependencies.

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate   # if not already set up
pip install -r requirements.txt -r requirements-dev.txt
pytest tests/ -v
```

Current suite: **36 tests**, all passing, covering:

| File | Covers |
|---|---|
| `test_auth.py` | Register/login/duplicate-email/wrong-password/password-length validation, protected-route rejection without a token |
| `test_conversations.py` | CRUD, ownership isolation (user A can't read user B's conversation), streaming chat's SSE event shape |
| `test_vision.py` | Upload type/size validation, end-to-end image-attachment → chat pipeline, cross-user attachment isolation |
| `test_memory_service.py` | Add/retrieve memory, graceful no-op when Chroma is unavailable, error handling doesn't propagate to callers |
| `test_llm_service.py` | Model routing rules (explicit choice wins, vision fallback, unknown-model fallback), streaming token yield, retry-on-transient-failure, error surfacing |
| `test_admin.py` | Admin-only access control, stats/user list, toggle-active, role promotion/demotion, deletion, all four self-lockout protections, 404 on unknown user |

### Notes on the test environment

- `LLM_API_KEY` is forced empty in `conftest.py`, so tests exercise the
  graceful-degradation path (no real API calls, no network needed, no
  cost). `test_llm_service.py` separately monkeypatches a fake OpenAI
  client to test the real streaming/retry code paths in isolation.
- `chromadb`/`sentence-transformers` are **not required** to run the
  suite — `memory_service.py` detects their absence at import time and
  degrades to no-ops, and `test_memory_service.py` verifies both the
  "available" and "unavailable" code paths by monkeypatching the
  module's internal collection accessor rather than requiring the real
  (heavy) ML stack to be installed.
- Each test file that needs an authenticated user creates one inline
  with a unique email (helper functions like `_auth_headers` /
  `_register`) rather than relying on shared fixtures, because the test
  database is session-scoped (persists across all tests in a run) to
  keep the suite fast — reusing an email across tests would 409.

### Adding a new backend test

1. Put it in `backend/tests/`, named `test_<feature>.py`.
2. Use the `client` fixture from `conftest.py` (an `httpx.AsyncClient`
   wired to the FastAPI app via ASGI transport — no real server needed).
3. If you need an authenticated user, register one with a unique email
   inline rather than assuming another test's user exists.
4. Run `pytest tests/test_<feature>.py -v` in isolation first, then the
   full suite (`pytest tests/ -q`) to check for cross-test interference.

## Frontend

There is currently **no** Jest/Playwright test suite (tracked in
`TODO.md`). What is verified today, and should be re-run after any
frontend change:

```bash
cd frontend
npm install --legacy-peer-deps
npx tsc --noEmit      # type-check, zero errors expected
npm run build          # production build, must complete without errors
```

Both are run as part of this project's own development process before
any milestone is marked complete — treat a red `tsc` or failed `build`
the same as a failing backend test.

### Manual smoke test (recommended before any release)

1. `docker compose up --build`, then open http://localhost:3000
2. Register a new account → should land on `/chat`
3. Send a message → should stream tokens in (or the placeholder message
   if `LLM_API_KEY` isn't set) and appear in the sidebar as a new conversation
4. Attach an image and ask about it → should show the attachment chip
5. Toggle dark/light mode → should persist across a page reload
6. Search conversations in the sidebar → should filter by title/content
7. If your account's email is in `ADMIN_EMAILS`, visit `/admin` → stats
   and user table should load, and role/active/delete actions should work
   against a second test account (not your own — those are blocked by design)

## Full regression check (run before any milestone is marked done)

```bash
cd backend && pytest tests/ -q
cd ../frontend && npx tsc --noEmit && npm run build
```

Both must be clean. This is the same check described in
`ARCHITECTURE.md`'s "How to resume work" section.
