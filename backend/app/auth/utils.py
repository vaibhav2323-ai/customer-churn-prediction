# auth utilities - hashing, JWT, refresh tokens, brute force protection
# originally used passlib but it crashes with bcrypt 4.x in prod (spent a day debugging this)
# now calling bcrypt directly which is less "proper" but actually works
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any

import bcrypt as _bcrypt
import jwt as pyjwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db

_BCRYPT_ROUNDS = 12
_BCRYPT_MAX_BYTES = 72  # hard bcrypt limit, enforced strictly in bcrypt 4.x

bearer_scheme = HTTPBearer(auto_error=False)


# precompute once so we can always run bcrypt even when user doesn't exist
# (prevents timing attacks that let you enumerate valid emails)
@lru_cache(maxsize=1)
def _dummy_hash() -> bytes:
    return _bcrypt.hashpw(b"dummy-for-timing-safety", _bcrypt.gensalt(rounds=_BCRYPT_ROUNDS))


def _encode_password(password: str) -> bytes:
    encoded = password.encode("utf-8")
    if len(encoded) > _BCRYPT_MAX_BYTES:
        raise ValueError(f"Password too long (max {_BCRYPT_MAX_BYTES} bytes)")
    return encoded


def hash_password(password: str) -> str:
    return _bcrypt.hashpw(
        _encode_password(password),
        _bcrypt.gensalt(rounds=_BCRYPT_ROUNDS),
    ).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return _bcrypt.checkpw(_encode_password(plain), hashed.encode("utf-8"))


def constant_time_password_check(plain: str, hashed: str | None) -> bool:
    # always run bcrypt even if user doesn't exist, so login time doesn't leak whether email is valid
    try:
        encoded = _encode_password(plain)
    except ValueError:
        # Password too long — still run a dummy check to keep response time constant.
        _bcrypt.checkpw(b"dummy", _dummy_hash())
        return False
    effective_hash = hashed.encode("utf-8") if hashed else _dummy_hash()
    result = _bcrypt.checkpw(encoded, effective_hash)
    return result and hashed is not None


def create_access_token(data: dict[str, Any]) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload["type"] = "access"
    # PyJWT 2.x encode() returns str directly (no .decode() needed)
    return pyjwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        payload = pyjwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "access":
            raise pyjwt.InvalidTokenError("Wrong token type")
        return payload
    except pyjwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def create_and_store_refresh_token(
    user_id: int,
    db: Session,
    ip: str = "",
    user_agent: str = "",
) -> str:
    from app.auth.refresh_models import RefreshToken, generate_refresh_token

    plaintext, token_hash = generate_refresh_token()
    rt = RefreshToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        ip_address=ip[:64] if ip else None,
        user_agent=user_agent[:512] if user_agent else None,
    )
    db.add(rt)
    db.commit()
    return plaintext


def verify_and_rotate_refresh_token(token: str, db: Session):
    from app.auth.models import User
    from app.auth.refresh_models import RefreshToken, hash_token

    token_hash = hash_token(token)
    rt = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == token_hash, RefreshToken.revoked == False)
        .first()
    )

    if rt is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    if rt.expires_at < datetime.now(timezone.utc):
        rt.revoked = True
        rt.revoked_at = datetime.now(timezone.utc)
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")

    user = db.get(User, rt.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    # Revoke old token (rotation prevents replay)
    rt.revoked = True
    rt.revoked_at = datetime.now(timezone.utc)
    db.commit()

    return user


def revoke_refresh_token(token: str, db: Session) -> None:
    from app.auth.refresh_models import RefreshToken, hash_token

    token_hash = hash_token(token)
    rt = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
    if rt and not rt.revoked:
        rt.revoked = True
        rt.revoked_at = datetime.now(timezone.utc)
        db.commit()


def revoke_all_user_refresh_tokens(user_id: int, db: Session) -> None:
    from app.auth.refresh_models import RefreshToken

    db.query(RefreshToken).filter(
        RefreshToken.user_id == user_id,
        RefreshToken.revoked == False,
    ).update({"revoked": True, "revoked_at": datetime.now(timezone.utc)})
    db.commit()


def check_account_lockout(user) -> None:
    if user.locked_until and user.locked_until > datetime.now(timezone.utc):
        remaining = max(1, int((user.locked_until - datetime.now(timezone.utc)).total_seconds() // 60))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Account locked due to too many failed attempts. Try again in {remaining} minute(s).",
        )


def record_failed_login(user, db: Session) -> None:
    user.failed_login_attempts += 1
    if user.failed_login_attempts >= settings.LOGIN_MAX_ATTEMPTS:
        user.locked_until = datetime.now(timezone.utc) + timedelta(
            minutes=settings.LOGIN_LOCKOUT_MINUTES
        )
        user.failed_login_attempts = 0
    db.commit()


def record_successful_login(user, db: Session, ip: str) -> None:
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = datetime.now(timezone.utc)
    user.last_login_ip = ip[:64] if ip else None
    db.commit()


def get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    x_real_ip = request.headers.get("X-Real-IP")
    if x_real_ip:
        return x_real_ip.strip()
    return request.client.host if request.client else "unknown"


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    from app.auth.models import User

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(credentials.credentials)
    user_id: str | None = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    user = db.get(User, int(user_id))
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    return user
