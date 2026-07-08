# TODO.md

Actionable backlog, in priority order. See `PROJECT_STATUS.md` for the
milestone-level snapshot and `ARCHITECTURE.md` for design rationale.

## High priority

1. **Frontend test suite.** No Jest/React Testing Library or Playwright
   coverage exists yet. Type-checking and production build are verified
   after every change, but there's no automated regression check for
   component behavior (e.g. the streaming message loop, attachment chip
   rendering, admin action buttons) or user flows (login → chat →
   logout). Recommend starting with Playwright for the three flows in
   `TESTING.md`'s manual smoke test, since those exercise the most
   integration surface per test written.

2. **Silent refresh-token rotation on the frontend.** `lib/api.ts`
   stores `access_token`/`refresh_token` in `localStorage` and never
   calls `POST /auth/refresh` automatically. Right now, when the access
   token expires (24h by default), the user is simply bounced to
   `/login` — annoying but not broken. An `fetch` wrapper that catches a
   401, calls `/auth/refresh`, retries once, and only redirects to
   login if the refresh itself fails would fix this properly.

## Medium priority

3. **Object storage for uploads.** `app/api/routes/files.py` writes to
   local disk (`UPLOAD_DIR`, default `/data/uploads`). This is correct
   and simple for a single backend instance, but breaks the moment you
   run more than one backend replica (each would only see its own local
   files). Swap to an S3-compatible backend (boto3 + any S3-compatible
   provider) before scaling horizontally. The current `UploadedFile`
   model's `storage_path` field is already just an opaque string, so
   this is a service-layer change, not a schema migration.

4. **Chroma concurrency under multi-worker deployment.** Documented in
   `docker-compose.prod.yml` and `ARCHITECTURE.md`: the embedded
   Chroma client persists to SQLite on a shared volume, and multiple
   Uvicorn worker processes writing memories concurrently can hit lock
   contention under sustained heavy load. Either run `--workers 1` for
   memory-heavy deployments, or replace the Chroma client with a
   standalone Chroma server / Qdrant instance (the `MemoryService`
   interface is already isolated in `app/services/memory_service.py`
   specifically to make this swap localized).

5. **Non-image attachments aren't used by chat yet.** `/files/upload`
   accepts PDFs and plain text/markdown in addition to images, and
   they're stored successfully, but `chat.py`'s `_load_image_attachments`
   only extracts image content types into the prompt. Extracting text
   from PDFs (e.g. via a text-extraction library) and inlining plain
   text/markdown uploads as context would complete this.

## Lower priority / nice to have

6. **Audit log for admin actions.** Admin role changes, deactivations,
   and deletions are currently only recorded via structured application
   logs (`loguru`, see `app/core/logging.py`) — there's no queryable
   `audit_log` table. Fine for a small deployment where logs are
   centrally collected; a dedicated table with a `/admin/audit` endpoint
   would be needed for compliance-sensitive deployments.

7. **TLS/reverse proxy.** Intentionally out of scope — see the comment
   at the top of `docker-compose.prod.yml`. Left to the deployer since
   it's highly environment-specific (existing infra, DNS, cert issuer).

8. **Postgres full-text search instead of `ILIKE`.** Conversation search
   (`GET /conversations?q=`) currently does a substring `ILIKE` scan,
   which is fine at small-to-moderate scale but doesn't use an index.
   A `tsvector` column + GIN index would be the natural upgrade if
   conversation volume per user grows large.

9. **Structured pagination.** `GET /conversations` and `GET
   /admin/users` return the full result set with no `limit`/`offset` or
   cursor. Not urgent at expected scale for a personal/small-team
   deployment, but worth adding before either list could realistically
   grow past a few hundred rows per user/instance.
