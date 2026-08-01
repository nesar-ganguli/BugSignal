import hashlib
import logging

from fastapi import HTTPException, Request
from redis import Redis
from redis.exceptions import RedisError

from app.config import get_settings


logger = logging.getLogger("bugsignal.rate_limit")

_FIXED_WINDOW_SCRIPT = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return {current, redis.call('TTL', KEYS[1])}
"""


def enforce_expensive_rate_limit(request: Request) -> None:
    settings = get_settings()
    if not settings.rate_limit_enabled:
        return

    client_host = request.client.host if request.client else "unknown"
    authorization = request.headers.get("Authorization", "anonymous")
    identity = hashlib.sha256(f"{client_host}:{authorization}".encode()).hexdigest()[:24]
    route = request.url.path.replace("/", ":")
    key = f"bugsignal:rate:{identity}:{route}"
    redis_client = Redis.from_url(
        settings.celery_broker_url,
        socket_connect_timeout=2,
        socket_timeout=2,
    )
    try:
        count, ttl = redis_client.eval(
            _FIXED_WINDOW_SCRIPT,
            1,
            key,
            settings.expensive_rate_limit_window_seconds,
        )
    except RedisError:
        logger.exception("Rate limiter unavailable; allowing request")
        return
    finally:
        redis_client.close()

    if int(count) > settings.expensive_rate_limit_requests:
        retry_after = max(int(ttl), 1)
        raise HTTPException(
            status_code=429,
            detail="Too many expensive operations. Try again later.",
            headers={"Retry-After": str(retry_after)},
        )
