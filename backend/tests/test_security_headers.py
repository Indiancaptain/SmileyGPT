async def test_security_headers_present_on_response(client):
    res = await client.get("/api/health")
    assert res.status_code == 200
    assert res.headers["X-Content-Type-Options"] == "nosniff"
    assert res.headers["X-Frame-Options"] == "DENY"
    assert res.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "geolocation=()" in res.headers["Permissions-Policy"]


async def test_security_headers_present_on_error_response(client):
    res = await client.get("/api/v1/users/me")
    assert res.status_code == 401
    assert res.headers["X-Content-Type-Options"] == "nosniff"
    assert res.headers["X-Frame-Options"] == "DENY"
