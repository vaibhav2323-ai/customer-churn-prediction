"""
Centralised rate-limiter shared across all routers.
Reads the real client IP from trusted reverse-proxy headers.
"""
from fastapi import Request
from slowapi import Limiter


def get_real_ip(request: Request) -> str:
    """Return leftmost (original client) IP from X-Forwarded-For if set by a
    trusted upstream (nginx), otherwise fall back to the direct connection IP."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "127.0.0.1"


# Global limiter — routers can tighten per-endpoint with their own @limiter.limit()
limiter = Limiter(key_func=get_real_ip, default_limits=["300/minute"])
