"""Redis-based sliding-window rate limiter for FastAPI."""
import time

import structlog
from fastapi import HTTPException, Request, status

logger = structlog.get_logger()

_redis_client = None


def _get_redis():
    global _redis_client
    if _redis_client is None:
        import redis
        from apps.api.config import get_settings
        settings = get_settings()
        _redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


class RateLimiter:
    """Sliding-window rate limiter using Redis INCR + EXPIRE.

    Usage as a FastAPI dependency:
        rate_limit = RateLimiter(max_calls=10, window_seconds=60)

        @router.post("/recompute")
        async def recompute(request: Request, _=Depends(rate_limit)):
            ...
    """

    def __init__(self, max_calls: int = 30, window_seconds: int = 60, key_prefix: str = "rl"):
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self.key_prefix = key_prefix

    def _make_key(self, request: Request) -> str:
        client_ip = request.client.host if request.client else "unknown"
        return f"{self.key_prefix}:{request.url.path}:{client_ip}"

    async def __call__(self, request: Request) -> None:
        try:
            r = _get_redis()
            key = self._make_key(request)
            current = r.incr(key)
            if current == 1:
                r.expire(key, self.window_seconds)
            if current > self.max_calls:
                ttl = r.ttl(key)
                logger.warning(
                    "rate_limit.exceeded",
                    path=request.url.path,
                    client=request.client.host if request.client else None,
                    limit=self.max_calls,
                    window=self.window_seconds,
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded. Try again in {max(ttl, 1)}s.",
                )
        except HTTPException:
            raise
        except Exception:
            logger.warning("rate_limit.redis_unavailable", exc_info=True)


auth_rate_limit = RateLimiter(max_calls=10, window_seconds=60, key_prefix="rl:auth")
recompute_rate_limit = RateLimiter(max_calls=5, window_seconds=60, key_prefix="rl:recompute")
