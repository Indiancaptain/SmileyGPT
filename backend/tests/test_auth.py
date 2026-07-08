import pytest


async def test_register_and_login(client):
    res = await client.post("/api/v1/auth/register", json={"email": "a@test.com", "password": "password123"})
    assert res.status_code == 201
    body = res.json()
    assert "access_token" in body
    assert "refresh_token" in body

    res = await client.post("/api/v1/auth/login", json={"email": "a@test.com", "password": "password123"})
    assert res.status_code == 200


async def test_register_duplicate_email_rejected(client):
    await client.post("/api/v1/auth/register", json={"email": "dupe@test.com", "password": "password123"})
    res = await client.post("/api/v1/auth/register", json={"email": "dupe@test.com", "password": "password123"})
    assert res.status_code == 409


async def test_login_wrong_password_rejected(client):
    await client.post("/api/v1/auth/register", json={"email": "wrongpw@test.com", "password": "password123"})
    res = await client.post("/api/v1/auth/login", json={"email": "wrongpw@test.com", "password": "nope"})
    assert res.status_code == 401


async def test_password_too_short_rejected(client):
    res = await client.post("/api/v1/auth/register", json={"email": "short@test.com", "password": "abc"})
    assert res.status_code == 422


async def test_protected_route_requires_token(client):
    res = await client.get("/api/v1/users/me")
    assert res.status_code == 401
