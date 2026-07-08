from app.core.config import settings
from app.core.redis_client import redis_client


async def test_rate_limit_blocks_after_ceiling_exceeded(client, monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_PER_MINUTE", 3)

    statuses = []
    for _ in range(5):
        res = await client.get("/api/v1/users/me")  # 401s still count as API traffic
        statuses.append(res.status_code)

    assert 429 in statuses, f"expected a 429 once the ceiling was exceeded, got {statuses}"

    async for key in redis_client.scan_iter("ratelimit:*"):
        await redis_client.delete(key)


async def test_rate_limit_does_not_apply_to_health_check(client, monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_PER_MINUTE", 1)

    statuses = [(await client.get("/api/health")).status_code for _ in range(10)]
    assert all(s == 200 for s in statuses)
