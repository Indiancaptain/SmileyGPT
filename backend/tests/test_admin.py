import itertools

from app.core.config import settings

_admin_counter = itertools.count()


async def _register(client, email, password="password123"):
    res = await client.post("/api/v1/auth/register", json={"email": email, "password": password})
    return res.json()["access_token"]


async def _admin_headers(client, monkeypatch):
    # settings is a process-wide singleton created before this module loads,
    # so it must be patched directly rather than via os.environ (too late).
    # A unique email per call avoids 409 conflicts against the session-wide test DB.
    email = f"superadmin{next(_admin_counter)}@test.com"
    monkeypatch.setattr(settings, "ADMIN_EMAILS", [email])
    token = await _register(client, email)
    return {"Authorization": f"Bearer {token}"}


async def test_non_admin_cannot_access_admin_routes(client):
    token = await _register(client, "regularjoe@test.com")
    res = await client.get("/api/v1/admin/stats", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403


async def test_admin_can_view_stats_and_users(client, monkeypatch):
    headers = await _admin_headers(client, monkeypatch)
    res = await client.get("/api/v1/admin/stats", headers=headers)
    assert res.status_code == 200
    assert "total_users" in res.json()

    res = await client.get("/api/v1/admin/users", headers=headers)
    assert res.status_code == 200
    assert isinstance(res.json(), list)


async def test_admin_can_toggle_other_user_active_status(client, monkeypatch):
    admin_headers = await _admin_headers(client, monkeypatch)
    other_token = await _register(client, "toggleuser@test.com")

    res = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {other_token}"})
    other_id = res.json()["id"]

    res = await client.patch(f"/api/v1/admin/users/{other_id}/toggle-active", headers=admin_headers)
    assert res.status_code == 200
    assert res.json()["is_active"] is False


async def test_admin_cannot_deactivate_self(client, monkeypatch):
    admin_headers = await _admin_headers(client, monkeypatch)
    res = await client.get("/api/v1/users/me", headers=admin_headers)
    admin_id = res.json()["id"]

    res = await client.patch(f"/api/v1/admin/users/{admin_id}/toggle-active", headers=admin_headers)
    assert res.status_code == 400


async def test_admin_can_promote_and_demote_other_user(client, monkeypatch):
    admin_headers = await _admin_headers(client, monkeypatch)
    other_token = await _register(client, "promoteuser@test.com")
    res = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {other_token}"})
    other_id = res.json()["id"]

    res = await client.patch(f"/api/v1/admin/users/{other_id}/role", json={"role": "admin"}, headers=admin_headers)
    assert res.status_code == 200
    assert res.json()["role"] == "admin"

    res = await client.patch(f"/api/v1/admin/users/{other_id}/role", json={"role": "user"}, headers=admin_headers)
    assert res.status_code == 200
    assert res.json()["role"] == "user"


async def test_admin_cannot_remove_own_admin_role(client, monkeypatch):
    admin_headers = await _admin_headers(client, monkeypatch)
    res = await client.get("/api/v1/users/me", headers=admin_headers)
    admin_id = res.json()["id"]

    res = await client.patch(f"/api/v1/admin/users/{admin_id}/role", json={"role": "user"}, headers=admin_headers)
    assert res.status_code == 400


async def test_admin_can_delete_other_user(client, monkeypatch):
    admin_headers = await _admin_headers(client, monkeypatch)
    other_token = await _register(client, "deleteme@test.com")
    res = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {other_token}"})
    other_id = res.json()["id"]

    res = await client.delete(f"/api/v1/admin/users/{other_id}", headers=admin_headers)
    assert res.status_code == 204

    # Deleted user's own token should no longer resolve
    res = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {other_token}"})
    assert res.status_code == 401


async def test_admin_cannot_delete_self(client, monkeypatch):
    admin_headers = await _admin_headers(client, monkeypatch)
    res = await client.get("/api/v1/users/me", headers=admin_headers)
    admin_id = res.json()["id"]

    res = await client.delete(f"/api/v1/admin/users/{admin_id}", headers=admin_headers)
    assert res.status_code == 400


async def test_admin_action_on_nonexistent_user_returns_404(client, monkeypatch):
    admin_headers = await _admin_headers(client, monkeypatch)
    res = await client.patch("/api/v1/admin/users/does-not-exist/toggle-active", headers=admin_headers)
    assert res.status_code == 404
