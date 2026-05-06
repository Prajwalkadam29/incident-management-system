import time
import structlog
from fastapi import HTTPException, Request
from app.db.redis_client import get_redis
from app.core.config import settings

logger = structlog.get_logger(__name__)


class RateLimiter:
    """
    Sliding window rate limiter backed by Redis.
    Uses a sorted set per IP — members are timestamps, score is also timestamp.
    We count members in the last `window` seconds — if over limit, reject.
    """

    def __init__(
        self,
        requests: int = settings.RATE_LIMIT_REQUESTS,
        window: int = settings.RATE_LIMIT_WINDOW,
    ):
        self.requests = requests
        self.window = window

    async def check(self, request: Request):
        try:
            redis = get_redis()
            # Use IP as the key — X-Forwarded-For for proxied requests
            ip = request.headers.get("X-Forwarded-For", request.client.host)
            key = f"rl:{ip}"
            now = time.time()
            window_start = now - self.window

            # Pipeline: remove old entries, add current, count, set expiry — atomically
            async with redis.pipeline(transaction=True) as pipe:
                pipe.zremrangebyscore(key, 0, window_start)   # remove expired
                pipe.zadd(key, {str(now): now})                # add current request
                pipe.zcard(key)                                # count in window
                pipe.expire(key, self.window)                  # auto-cleanup
                results = await pipe.execute()

            count = results[2]

            if count > self.requests:
                logger.warning("Rate limit exceeded", ip=ip, count=count)
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "rate_limit_exceeded",
                        "message": f"Max {self.requests} requests per {self.window}s",
                        "retry_after_seconds": self.window,
                    }
                )

            return count
        except HTTPException:
            # Re-raise 429 exceptions so they are not bypassed
            raise
        except Exception as e:
            # Fail-Open under Redis connection or pool outages
            logger.error(
                "Rate limiter cache unavailable — failing OPEN",
                error=str(e),
            )
            return 0


# Singleton instance used as a FastAPI dependency
rate_limiter = RateLimiter()


async def rate_limit_dependency(request: Request):
    """FastAPI dependency — add to any route that needs rate limiting."""
    await rate_limiter.check(request)