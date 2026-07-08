"""
Regression test: RequestValidationError.errors() can include non-JSON
-serializable objects, which previously crashed our own error handler
(returning an unhandled 500 instead of a clean 422). See CHANGELOG.md.
"""


async def test_missing_multipart_file_field_returns_clean_422(client):
    """Omitting the required 'file' field entirely triggers a Pydantic
    validation error whose shape has, in the past, included values that
    broke naive JSON serialization in the app's own error handler."""
    res = await client.post("/api/v1/auth/register", json={"email": "novalidfile@test.com", "password": "password123"})
    token = res.json()["access_token"]

    res = await client.post("/api/v1/files/upload", files={}, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code in (422, 400)
    # Must be valid, parseable JSON with our standard error shape — not a
    # raw 500 from a crashed exception handler.
    body = res.json()
    assert "detail" in body


async def test_register_with_invalid_email_returns_clean_422(client):
    res = await client.post("/api/v1/auth/register", json={"email": "not-an-email", "password": "password123"})
    assert res.status_code == 422
    body = res.json()
    assert "detail" in body
