async def _auth_headers(client, email="chatuser@test.com"):
    res = await client.post("/api/v1/auth/register", json={"email": email, "password": "password123"})
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def test_create_and_list_conversations(client):
    headers = await _auth_headers(client)
    res = await client.post("/api/v1/conversations", json={"title": "Test chat"}, headers=headers)
    assert res.status_code == 201
    convo_id = res.json()["id"]

    res = await client.get("/api/v1/conversations", headers=headers)
    assert res.status_code == 200
    assert any(c["id"] == convo_id for c in res.json())


async def test_delete_conversation(client):
    headers = await _auth_headers(client, "deleteuser@test.com")
    res = await client.post("/api/v1/conversations", json={"title": "To delete"}, headers=headers)
    convo_id = res.json()["id"]

    res = await client.delete(f"/api/v1/conversations/{convo_id}", headers=headers)
    assert res.status_code == 204

    res = await client.get(f"/api/v1/conversations/{convo_id}/messages", headers=headers)
    assert res.status_code == 404


async def test_conversation_not_owned_returns_404(client):
    headers_a = await _auth_headers(client, "usera@test.com")
    headers_b = await _auth_headers(client, "userb@test.com")

    res = await client.post("/api/v1/conversations", json={"title": "Private"}, headers=headers_a)
    convo_id = res.json()["id"]

    res = await client.get(f"/api/v1/conversations/{convo_id}/messages", headers=headers_b)
    assert res.status_code == 404


async def test_chat_stream_without_llm_key_degrades_gracefully(client):
    headers = await _auth_headers(client, "streamuser@test.com")
    async with client.stream(
        "POST", "/api/v1/chat/stream", json={"message": "Hello there"}, headers=headers
    ) as res:
        assert res.status_code == 200
        chunks = [chunk async for chunk in res.aiter_text()]
        full = "".join(chunks)
        assert "event: start" in full
        assert "event: done" in full
