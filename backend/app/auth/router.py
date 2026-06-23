"""
Authentication router.

Security measures applied here:
- Strict rate limiting: 5 req/min on login, 10/min on register
- Constant-time password verification (prevents user-enumeration via timing)
- Brute-force lockout after LOGIN_MAX_ATTEMPTS failures
- httpOnly + Secure + SameSite cookies for refresh tokens
- Refresh-token rotation: old token revoked on every refresh
- Vague error messages to avoid leaking whether an email exists
"""
import logging
import traceback
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.auth.models import User
from app.auth.schemas import (
    LoginRequest,
    RefreshResponse,
    RegisterRequest,
    TokenResponse,
    UserOut,
)
from app.auth.utils import (
    check_account_lockout,
    constant_time_password_check,
    create_access_token,
    create_and_store_refresh_token,
    get_client_ip,
    get_current_user,
    hash_password,
    record_failed_login,
    record_successful_login,
    revoke_all_user_refresh_tokens,
    revoke_refresh_token,
    verify_and_rotate_refresh_token,
)
from app.config import settings
from app.database import get_db
from app.limiter import limiter

router = APIRouter()

_COOKIE_NAME = "refresh_token"
_COOKIE_PATH = "/auth"  # Scope cookie to /auth to minimise surface area


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=_COOKIE_NAME,
        value=token,
        httponly=True,                       # JS cannot read this cookie
        secure=settings.COOKIE_SECURE,       # True in production → HTTPS only
        samesite=settings.COOKIE_SAMESITE,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path=_COOKIE_PATH,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=_COOKIE_NAME, path=_COOKIE_PATH)


# ── Register ─────────────────────────────────────────────────────────────────

@router.post("/register", status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
def register(request: Request, payload: RegisterRequest, db: Session = Depends(get_db)):
    user = User(
        email=payload.email.lower(),
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
    )
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    access_token = create_access_token({"sub": str(user.id)})
    refresh_token = create_and_store_refresh_token(
        user.id, db, ip=get_client_ip(request),
        user_agent=request.headers.get("user-agent", ""),
    )

    content = TokenResponse(
        access_token=access_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserOut.model_validate(user),
    ).model_dump(mode="json")

    response = JSONResponse(content=content, status_code=201)
    _set_refresh_cookie(response, refresh_token)
    return response


# ── Login ─────────────────────────────────────────────────────────────────────

@router.post("/login")
@limiter.limit("5/minute")          # Strict: 5 attempts per minute per IP
def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)):
    email = payload.email.lower()
    client_ip = get_client_ip(request)
    origin = request.headers.get("origin", "<no origin header>")

    logger.info("[LOGIN] attempt email=%s ip=%s origin=%s", email, client_ip, origin)
    logger.info("[LOGIN] CORS allowed origins: %s", settings.cors_origins_list)
    logger.info(
        "[LOGIN] cookie settings: secure=%s samesite=%s",
        settings.COOKIE_SECURE, settings.COOKIE_SAMESITE,
    )

    try:
        user: User | None = db.query(User).filter(User.email == email).first()
        logger.info("[LOGIN] user found in DB: %s (id=%s)", user is not None, getattr(user, "id", None))

        # Always run bcrypt to prevent timing-based user-enumeration
        try:
            password_ok = constant_time_password_check(
                payload.password,
                user.hashed_password if user else None,
            )
            logger.info("[LOGIN] password_ok=%s", password_ok)
        except Exception as pw_exc:
            logger.error("[LOGIN] bcrypt check raised: %s\n%s", pw_exc, traceback.format_exc())
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Password verification error: {pw_exc}",
            )

        if not user:
            logger.warning("[LOGIN] rejected — no user for email=%s", email)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
            )

        if user.locked_until and user.locked_until > datetime.now(timezone.utc):
            logger.warning("[LOGIN] account locked email=%s locked_until=%s", email, user.locked_until)
            check_account_lockout(user)  # raises 429

        if not password_ok:
            logger.warning("[LOGIN] wrong password email=%s attempts=%s", email, user.failed_login_attempts + 1)
            record_failed_login(user, db)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
            )

        if not user.is_active:
            logger.warning("[LOGIN] account inactive email=%s", email)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

        record_successful_login(user, db, client_ip)
        logger.info("[LOGIN] success email=%s id=%s", email, user.id)

        try:
            access_token = create_access_token({"sub": str(user.id)})
            refresh_token = create_and_store_refresh_token(
                user.id, db, ip=client_ip,
                user_agent=request.headers.get("user-agent", ""),
            )
            logger.info("[LOGIN] tokens created for user id=%s", user.id)
        except Exception as tok_exc:
            logger.error("[LOGIN] token creation failed: %s\n%s", tok_exc, traceback.format_exc())
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Token creation error: {tok_exc}",
            )

        content = TokenResponse(
            access_token=access_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserOut.model_validate(user),
        ).model_dump(mode="json")

        response = JSONResponse(content=content)
        _set_refresh_cookie(response, refresh_token)
        logger.info(
            "[LOGIN] response ready — Set-Cookie: refresh_token path=%s secure=%s samesite=%s",
            _COOKIE_PATH, settings.COOKIE_SECURE, settings.COOKIE_SAMESITE,
        )
        return response

    except HTTPException:
        raise  # let FastAPI handle expected HTTP errors normally
    except Exception as exc:
        logger.error("[LOGIN] unexpected error: %s\n%s", exc, traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login error: {exc}",
        )


# ── Refresh ───────────────────────────────────────────────────────────────────

@router.post("/refresh")
@limiter.limit("30/minute")
def refresh(request: Request, db: Session = Depends(get_db)):
    """Exchange a valid refresh-token cookie for a new access token + rotated refresh token."""
    token = request.cookies.get(_COOKIE_NAME)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing",
        )

    user = verify_and_rotate_refresh_token(token, db)

    new_access = create_access_token({"sub": str(user.id)})
    new_refresh = create_and_store_refresh_token(
        user.id, db, ip=get_client_ip(request),
        user_agent=request.headers.get("user-agent", ""),
    )

    content = RefreshResponse(
        access_token=new_access,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    ).model_dump(mode="json")

    response = JSONResponse(content=content)
    _set_refresh_cookie(response, new_refresh)
    return response


# ── Logout ────────────────────────────────────────────────────────────────────

@router.post("/logout")
def logout(request: Request, db: Session = Depends(get_db)):
    """Revoke the current refresh token and clear the cookie."""
    token = request.cookies.get(_COOKIE_NAME)
    if token:
        revoke_refresh_token(token, db)

    response = JSONResponse(content={"message": "Logged out successfully"})
    _clear_refresh_cookie(response)
    return response


@router.post("/logout-all")
def logout_all(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Revoke ALL refresh tokens for the current user (e.g. after password change)."""
    revoke_all_user_refresh_tokens(current_user.id, db)
    response = JSONResponse(content={"message": "All sessions terminated"})
    _clear_refresh_cookie(response)
    return response


# ── Me ────────────────────────────────────────────────────────────────────────

@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return UserOut.model_validate(current_user)
