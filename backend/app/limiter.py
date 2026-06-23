from fastapi import Request
from slowapi import Limiter


# need to read real IP from the proxy headers, not the connection IP
# otherwise all requests look like they come from the nginx container
def get_real_ip(request: Request) -> str:
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "127.0.0.1"


limiter = Limiter(key_func=get_real_ip, default_limits=["300/minute"])
