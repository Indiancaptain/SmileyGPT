import io


def _valid_png_bytes() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (2, 2), color=(255, 0, 0)).save(buf, format="PNG")
    return buf.getvalue()


async def _auth_headers(client, email):
    res = await client.post("/api/v1/auth/register", json={"email": email, "password": "password123"})
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def test_upload_rejects_spoofed_content_type(client):
    """A non-image file claiming to be image/png should be rejected once
    we actually inspect the bytes, not just trust the header."""
    headers = await _auth_headers(client, "spoofed@test.com")
    res = await client.post(
        "/api/v1/files/upload",
        files={"file": ("fake.png", io.BytesIO(b"this is definitely not a PNG file"), "image/png")},
        headers=headers,
    )
    assert res.status_code == 422


async def test_upload_rejects_spoofed_pdf(client):
    headers = await _auth_headers(client, "spoofedpdf@test.com")
    res = await client.post(
        "/api/v1/files/upload",
        files={"file": ("fake.pdf", io.BytesIO(b"not a real pdf"), "application/pdf")},
        headers=headers,
    )
    assert res.status_code == 422


async def test_upload_accepts_genuine_pdf_magic_bytes(client):
    headers = await _auth_headers(client, "realpdf@test.com")
    res = await client.post(
        "/api/v1/files/upload",
        files={"file": ("real.pdf", io.BytesIO(b"%PDF-1.4\n%fake but has the right header\n"), "application/pdf")},
        headers=headers,
    )
    assert res.status_code == 201


async def test_upload_rejects_missing_filename(client):
    headers = await _auth_headers(client, "nofilename@test.com")
    res = await client.post(
        "/api/v1/files/upload",
        files={"file": ("", io.BytesIO(b"hello"), "text/plain")},
        headers=headers,
    )
    assert res.status_code in (422, 400)


async def test_upload_rejects_disallowed_type(client):
    headers = await _auth_headers(client, "filetype@test.com")
    res = await client.post(
        "/api/v1/files/upload",
        files={"file": ("script.exe", io.BytesIO(b"MZ"), "application/octet-stream")},
        headers=headers,
    )
    assert res.status_code == 415


async def test_upload_and_use_in_chat_stream(client):
    headers = await _auth_headers(client, "vision@test.com")

    png_bytes = _valid_png_bytes()
    upload_res = await client.post(
        "/api/v1/files/upload",
        files={"file": ("pixel.png", io.BytesIO(png_bytes), "image/png")},
        headers=headers,
    )
    assert upload_res.status_code == 201
    file_id = upload_res.json()["id"]
    assert upload_res.json()["is_image"] is True

    async with client.stream(
        "POST",
        "/api/v1/chat/stream",
        json={"message": "What's in this image?", "attachment_ids": [file_id]},
        headers=headers,
    ) as res:
        assert res.status_code == 200
        chunks = [chunk async for chunk in res.aiter_text()]
        full = "".join(chunks)
        assert "event: start" in full
        assert "event: done" in full


async def test_upload_rejects_oversized_file(client):
    headers = await _auth_headers(client, "oversize@test.com")
    from app.core.config import settings

    big = b"0" * ((settings.MAX_UPLOAD_MB + 1) * 1024 * 1024)
    res = await client.post(
        "/api/v1/files/upload",
        files={"file": ("big.png", io.BytesIO(big), "image/png")},
        headers=headers,
    )
    assert res.status_code == 413


async def test_attachment_from_other_user_is_ignored_not_leaked(client):
    """A user cannot piggyback another user's file id to have it read into
    their own vision request — the attachment lookup is scoped by owner."""
    headers_a = await _auth_headers(client, "ownerA@test.com")
    headers_b = await _auth_headers(client, "ownerB@test.com")

    png_bytes = _valid_png_bytes()
    upload_res = await client.post(
        "/api/v1/files/upload",
        files={"file": ("secret.png", io.BytesIO(png_bytes), "image/png")},
        headers=headers_a,
    )
    file_id = upload_res.json()["id"]

    # userB references userA's file id; request should still succeed (image silently skipped)
    async with client.stream(
        "POST",
        "/api/v1/chat/stream",
        json={"message": "describe", "attachment_ids": [file_id]},
        headers=headers_b,
    ) as res:
        assert res.status_code == 200
