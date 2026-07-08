"""
Token revocation via a Redis denylist keyed by jti. Rather than storing
every issued token, we only ever store the (small) set of explicitly
revoked ones, each with a TTL matching its remaining natural lifetime —
so the denylist never grows unbounded and self-cleans as tokens expire.
"""
import time

from app.core.logging import get_logger
from app.core.redis_client import redis_client

logger = get_logger(__name__)

_DENYLIST_PREFIX = "revoked_jti:"


async def revoke_token(jti: str, exp: int) -> None:
    ttl = max(int(exp - time.time()), 1)
    try:
        await redis_client.set(f"{_DENYLIST_PREFIX}{jti}", "1", ex=ttl)
    except Exception as exc:  # noqa: BLE001
        # If Redis is briefly unavailable, logout still "succeeds" from the
        # client's point of view (it discards its local tokens either way);
        # we just won't have server-side enforcement for that one token.
        logger.warning(f"Failed to persist token revocation for jti={jti}: {exc}")


async def is_token_revoked(jti: str) -> bool:
    try:
        return bool(await redis_client.exists(f"{_DENYLIST_PREFIX}{jti}"))
    except Exception as exc:  # noqa: BLE001
        # Fail open, consistent with the rate limiter: a Redis outage
        # shouldn't lock every user out of an app that was working fine.
        logger.warning(f"Failed to check token revocation for jti={jti}: {exc}")
        return False
