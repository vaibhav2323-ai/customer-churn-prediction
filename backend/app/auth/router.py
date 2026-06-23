import logging

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
_COOKIE_PATH = "/auth"


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path=_COOKIE_PATH,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=_COOKIE_NAME, path=_COOKIE_PATH)


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


@router.post("/login")
@limiter.limit("5/minute")
def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)):
    email = payload.email.lower()
    client_ip = get_client_ip(request)

    user: User | None = db.query(User).filter(User.email == email).first()

    # always run bcrypt even if user doesn't exist — prevents timing-based email enumeration
    password_ok = constant_time_password_check(
        payload.password,
        user.hashed_password if user else None,
    )

    if not user or not password_ok:
        if user and not password_ok:
            record_failed_login(user, db)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    check_account_lockout(user)

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    record_successful_login(user, db, client_ip)
    logger.info("login success email=%s id=%s", email, user.id)

    access_token = create_access_token({"sub": str(user.id)})
    refresh_token = create_and_store_refresh_token(
        user.id, db, ip=client_ip,
        user_agent=request.headers.get("user-agent", ""),
    )

    content = TokenResponse(
        access_token=access_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserOut.model_validate(user),
    ).model_dump(mode="json")

    response = JSONResponse(content=content)
    _set_refresh_cookie(response, refresh_token)
    return response


@router.post("/refresh")
@limiter.limit("30/minute")
def refresh(request: Request, db: Session = Depends(get_db)):
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


@router.post("/logout")
def logout(request: Request, db: Session = Depends(get_db)):
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
    revoke_all_user_refresh_tokens(current_user.id, db)
    response = JSONResponse(content={"message": "All sessions terminated"})
    _clear_refresh_cookie(response)
    return response


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return UserOut.model_validate(current_user)
