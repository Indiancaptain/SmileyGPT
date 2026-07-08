# SmileyGPT

A production-structured, ChatGPT-style AI chat platform: FastAPI backend,
Next.js frontend, Postgres, Redis, and an embedded vector memory store —
all wired together with streaming responses, multimodal image
understanding, voice input/output, and an admin dashboard.

See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full status table and
design rationale, [`API.md`](./API.md) for endpoint reference,
[`TESTING.md`](./TESTING.md) for how to run and extend the test suite,
and [`CHANGELOG.md`](./CHANGELOG.md) / [`TODO.md`](./TODO.md) for
what's changed and what's left.

## Feature summary

- **Auth** — JWT access/refresh tokens, bcrypt password hashing
- **Conversations** — create, list, search, archive, delete
- **Streaming chat** — Server-Sent Events, token-by-token
- **Multi-model routing** — switch models per conversation via an allow-list
- **Image understanding** — upload an image, ask about it, routed to a vision model
- **Voice input/output** — browser-native Web Speech API (no backend cost)
- **Long-term memory** — Chroma-backed retrieval-augmented context per user
- **Markdown + syntax highlighting** in responses
- **Dark/light mode**
- **Admin dashboard** — stats, user list, role management, activate/deactivate, delete
- **Rate limiting** — Redis fixed-window per client IP
- **Docker Compose** — full stack in one command, with a production overlay

## Quick start (Docker — recommended)

Requires Docker Engine with the Compose plugin (`docker compose version`
should print `v2.24` or newer — needed for the `env_file: required: false`
syntax used below).

```bash
git clone <this-repo>
cd smileygpt

# Optional but recommended: real secrets instead of dev defaults
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
# edit backend/.env: set SECRET_KEY (openssl rand -hex 32) and LLM_API_KEY

docker compose up --build
```

- Frontend: http://localhost:3000
- Backend docs (Swagger UI): http://localhost:8000/api/docs
- Backend health check: http://localhost:8000/api/health

First run automatically applies database migrations (`alembic upgrade
head`) before starting the API.

If you skip the `.env` copy step, the stack still boots — `LLM_API_KEY`
defaults to empty, so chat responses fall back to a clearly-labeled
placeholder message instead of calling a real model. Everything else
(auth, conversations, uploads, streaming plumbing, UI) works normally,
which is useful for kicking the tires without an API key.

### Production deployment

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

This overlay removes host-exposed ports for Postgres/Redis, runs the
backend with multiple Uvicorn workers, sets resource limits, and switches
`DEBUG` off. It does **not** include TLS termination — put a reverse
proxy (Caddy, Traefik, nginx, or your cloud load balancer) in front and
terminate HTTPS there; that part is too environment-specific to hardcode.

## Local development (without Docker)

### Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env   # edit DATABASE_URL/REDIS_URL to point at local services
alembic upgrade head
uvicorn app.main:app --reload
```

Requires a running Postgres and Redis instance — either install them
locally or run just those two services via
`docker compose up postgres redis`.

### Frontend

```bash
cd frontend
npm install --legacy-peer-deps
cp .env.example .env
npm run dev
```

The `--legacy-peer-deps` flag is needed because some peer dependency
ranges in the current package set haven't caught up to React 19 yet.

## Configuration reference

All backend configuration lives in environment variables (see
`backend/.env.example`) and is parsed by `app/core/config.py`. Key ones:

| Variable | Purpose |
|---|---|
| `SECRET_KEY` | JWT signing secret. **Change this before deploying anywhere real.** |
| `DATABASE_URL` | Async SQLAlchemy connection string (Postgres) |
| `REDIS_URL` | Used for rate limiting |
| `LLM_API_KEY` / `LLM_BASE_URL` | Any OpenAI-compatible provider (OpenAI, Groq, local Ollama shim, etc.) |
| `AVAILABLE_MODELS` | JSON array allow-list exposed to the model picker |
| `LLM_VISION_MODEL` | Model used when a request includes image attachments |
| `CHROMA_PERSIST_DIR` | Where long-term memory vectors are stored on disk |
| `ADMIN_EMAILS` | JSON array — accounts registered with these emails become admins automatically |

The frontend only needs `BACKEND_INTERNAL_URL` (see `frontend/.env.example`),
used server-side by Next.js to proxy `/api/backend/*` to the FastAPI
service so the browser never talks to the backend origin directly.

## Known limitations

See the "Known gaps / TODO" section of `ARCHITECTURE.md` and `TODO.md`
for the current, up-to-date list — this README won't be kept in perfect
sync with that as the project evolves. Headline items right now: no
frontend component/e2e test suite yet, uploads are stored on local disk
(fine for one instance, swap to S3-compatible storage before scaling
out), and the embedded Chroma memory store can hit SQLite lock
contention if you run many backend workers under heavy concurrent load.

## License

Provided as-is for learning/portfolio/internal use. Add your own license
file before distributing.
