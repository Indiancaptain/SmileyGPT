async def _register(client, email):
    res = await client.post("/api/v1/auth/register", json={"email": email, "password": "password123"})
    return res.json()


async def test_logout_revokes_access_token(client):
    tokens = await _register(client, "logoutuser@test.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    # Works before logout
    res = await client.get("/api/v1/users/me", headers=headers)
    assert res.status_code == 200

    res = await client.post("/api/v1/auth/logout", json={}, headers=headers)
    assert res.status_code == 204

    # Same access token must now be rejected
    res = await client.get("/api/v1/users/me", headers=headers)
    assert res.status_code == 401


async def test_logout_revokes_refresh_token_when_provided(client):
    tokens = await _register(client, "logoutrefresh@test.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    res = await client.post(
        "/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]}, headers=headers
    )
    assert res.status_code == 204

    # The refresh token should no longer mint new tokens
    res = await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert res.status_code == 401


async def test_refresh_token_rotation_prevents_replay(client):
    tokens = await _register(client, "rotationuser@test.com")

    res = await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert res.status_code == 200
    new_tokens = res.json()
    assert new_tokens["refresh_token"] != tokens["refresh_token"]

    # Replaying the original (now-rotated-out) refresh token must fail
    res = await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert res.status_code == 401

    # But the newly issued refresh token still works
    res = await client.post("/api/v1/auth/refresh", json={"refresh_token": new_tokens["refresh_token"]})
    assert res.status_code == 200


async def test_logout_without_body_still_revokes_access_token(client):
    """The refresh_token field is optional — logging out with just the
    access token in the header (no JSON body) should still work."""
    tokens = await _register(client, "logoutnobody@test.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    res = await client.post("/api/v1/auth/logout", headers=headers)
    assert res.status_code == 204

    res = await client.get("/api/v1/users/me", headers=headers)
    assert res.status_code == 401


async def test_logout_requires_authentication(client):
    res = await client.post("/api/v1/auth/logout", json={})
    assert res.status_code == 401
