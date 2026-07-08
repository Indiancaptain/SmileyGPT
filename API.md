# SmileyGPT API Reference

Base URL (local dev via Docker): `http://localhost:8000`
All endpoints below are prefixed with `/api/v1` except `/api/health`.

Interactive Swagger UI is always available at **`/api/docs`** and reflects
the live schema — treat this document as a guided tour, and the Swagger
UI as the source of truth for exact request/response shapes.

Auth: every endpoint except `/auth/register`, `/auth/login`,
`/auth/refresh`, and `/api/health` requires an `Authorization: Bearer
<access_token>` header.

---

## Health

### `GET /api/health`
No auth required. Returns `{"status": "ok", "app": "SmileyGPT", "env": "..."}`.

---

## Auth

### `POST /auth/register`
```json
{ "email": "you@example.com", "password": "at-least-8-chars", "display_name": "optional" }
```
→ `201` `{ "access_token": "...", "refresh_token": "...", "token_type": "bearer" }`
`409` if the email is already registered. If the email is in the
server's `ADMIN_EMAILS` list, the account is created with the `admin` role.

### `POST /auth/login`
```json
{ "email": "you@example.com", "password": "..." }
```
→ `200` same token shape as register. `401` on bad credentials, `403` if
the account was deactivated by an admin.

### `POST /auth/refresh`
```json
{ "refresh_token": "..." }
```
→ `200` a fresh access/refresh token pair. `401` if the refresh token is
invalid, expired, or not a refresh-type token.

---

## Users

### `GET /users/me`
→ `200` the current user's profile (id, email, display_name, avatar_url,
role, preferred_model, theme, created_at).

### `PATCH /users/me`
Partial update. Any subset of:
```json
{ "display_name": "...", "avatar_url": "...", "preferred_model": "gpt-4o", "theme": "light" }
```
→ `200` the updated profile.

---

## Conversations

### `GET /conversations?q=<search term>`
Lists the caller's conversations, most recently updated first. `q` is
optional and searches both conversation titles and message content
(case-insensitive substring match).

### `POST /conversations`
```json
{ "title": "optional", "model": "optional" }
```
→ `201` the created conversation. If omitted, `model` defaults to the
user's `preferred_model`.

### `GET /conversations/{id}/messages`
→ `200` array of messages in chronological order. `404` if the
conversation doesn't exist or isn't owned by the caller.

### `PATCH /conversations/{id}`
```json
{ "title": "optional", "is_archived": true }
```
→ `200` the updated conversation.

### `DELETE /conversations/{id}`
→ `204`. Cascades to delete all messages in the conversation.

---

## Chat (streaming)

### `POST /chat/stream`
```json
{
  "conversation_id": "optional — omit to start a new conversation",
  "message": "What's in this image?",
  "model": "optional — falls back to the conversation's model",
  "attachment_ids": ["optional array of uploaded file ids"],
  "use_memory": true
}
```

Response is `text/event-stream` (Server-Sent Events), not a normal JSON
body. Three event types are emitted, each as `event: <type>\ndata:
<json>\n\n`:

- `start` — `{"conversation_id": "..."}`. If you didn't pass a
  `conversation_id`, this is where you learn the newly created one.
- `token` — `{"content": "..."}`, one per streamed chunk of the reply.
  Concatenate these in order to reconstruct the full response.
- `done` — `{"conversation_id": "..."}`. The assistant's full message has
  already been persisted to the database by this point.

If any `attachment_ids` reference an image file owned by the caller, the
request is automatically routed to `LLM_VISION_MODEL` and the image is
embedded into the prompt as a base64 data URL. IDs that don't exist or
belong to another user are silently skipped (not leaked, not erroring
the whole request). If `use_memory` is true (default), relevant
long-term memories for the user are retrieved and injected as an
additional system message before the model call.

If the server has no `LLM_API_KEY` configured, this endpoint still
streams a valid SSE response — just with a clearly-labeled placeholder
message instead of a real model reply, so the rest of the stack remains
testable without credentials.

---

## Files

### `POST /files/upload`
`multipart/form-data` with a single `file` field.

Allowed content types: `image/png`, `image/jpeg`, `image/webp`,
`image/gif`, `application/pdf`, `text/plain`, `text/markdown`. Max size
is `MAX_UPLOAD_MB` (default 20MB) — `413` if exceeded, `415` if the type
isn't allowed.

→ `201`:
```json
{ "id": "...", "filename": "...", "content_type": "image/png", "size_bytes": 12345, "is_image": true }
```
Pass the returned `id` in a subsequent `/chat/stream` call's
`attachment_ids` to have it considered by the model (images only —
non-image uploads are stored but not yet wired into the LLM prompt).

---

## Admin

All routes below require the caller's account to have the `admin` role
(`403` otherwise).

### `GET /admin/stats`
→ `200` `{ "total_users": n, "total_conversations": n, "total_messages": n, "active_today": n }`

### `GET /admin/users`
→ `200` array of all user profiles (same shape as `/users/me`, for every user).

### `PATCH /admin/users/{id}/toggle-active`
Flips the target user's `is_active` flag (deactivated users can't log
in). `400` if you target your own account — you can't lock yourself out.

### `PATCH /admin/users/{id}/role`
```json
{ "role": "admin" }
```
`400` if you try to remove your own admin role (prevents an admin
locking themselves out of the dashboard with nobody left to restore
access).

### `DELETE /admin/users/{id}`
→ `204`. Cascades to delete the user's conversations, messages, and
uploaded files. `400` if you target your own account.

---

## Error format

All errors (validation, auth, not-found, rate limit, unhandled) return:
```json
{ "detail": "human-readable message" }
```
or, for `422` validation errors, `detail` is the standard FastAPI/Pydantic
list-of-errors structure.

## Rate limiting

Every `/api/v1/*` request is counted per client IP in a 60-second fixed
window (`RATE_LIMIT_PER_MINUTE`, default 60). Exceeding it returns `429`
with `{"detail": "Rate limit exceeded. Please slow down."}`. If Redis is
unreachable, the limiter fails open (requests are allowed through) rather
than taking the whole API down.
