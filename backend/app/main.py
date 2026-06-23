"""
FastAPI application entry point.

Security layers applied here:
1. Strict CORS — no wildcard, credentials allowed only for listed origins
2. Security-header middleware (CSP, HSTS, X-Frame-Options, etc.)
3. Global rate limiter (tightened per-endpoint in individual routers)
4. Production error handler — hides stack traces from clients
5. OpenAPI docs disabled in production
"""
import logging
import logging.config
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.database import create_tables
from app.limiter import limiter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    logger.info("[STARTUP] DB tables ready")

    from ml.predict import load_model
    load_model()
    logger.info("[STARTUP] ML model loaded")

    # ── CORS diagnostics ──────────────────────────────────────────────────────
    logger.info("[STARTUP] CORS allowed origins: %s", settings.cors_origins_list)
    logger.info(
        "[STARTUP] Cookie settings: secure=%s samesite=%s",
        settings.COOKIE_SECURE, settings.COOKIE_SAMESITE,
    )
    logger.info("[STARTUP] Environment: %s", settings.ENVIRONMENT)

    # ── Demo user ─────────────────────────────────────────────────────────────
    from scripts.seed import ensure_demo_user
    try:
        ensure_demo_user()
    except Exception as exc:
        logger.error("[STARTUP] ensure_demo_user failed: %s", exc, exc_info=True)

    # ── Verify demo user is really in DB ─────────────────────────────────────
    try:
        from app.database import SessionLocal
        from app.auth.models import User
        with SessionLocal() as db:
            demo = db.query(User).filter(User.email == "demo@churnprediction.ai").first()
            if demo:
                logger.info(
                    "[STARTUP] Demo user confirmed in DB: id=%s email=%s active=%s",
                    demo.id, demo.email, demo.is_active,
                )
            else:
                logger.error("[STARTUP] Demo user NOT found in DB after ensure_demo_user()")
    except Exception as exc:
        logger.error("[STARTUP] DB demo-user check failed: %s", exc, exc_info=True)

    yield


# Disable interactive docs in production to reduce attack surface
_docs_url = None if settings.is_production else "/docs"
_redoc_url = None if settings.is_production else "/redoc"
_openapi_url = None if settings.is_production else "/openapi.json"

app = FastAPI(
    title="Customer Churn Prediction API",
    version="1.0.0",
    description="ML-powered churn prediction with SHAP explanations",
    lifespan=lifespan,
    docs_url=_docs_url,
    redoc_url=_redoc_url,
    openapi_url=_openapi_url,
)

# ── Rate limiting ─────────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS — explicit origins only, no wildcard ─────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,                         # Required for httpOnly cookie
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
    expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining", "Retry-After"],
    max_age=600,
)


# ── CORS + request diagnostics middleware ────────────────────────────────────
@app.middleware("http")
async def log_requests(request: Request, call_next):
    origin = request.headers.get("origin")
    if origin:
        logger.info(
            "[REQUEST] %s %s  origin=%s",
            request.method, request.url.path, origin,
        )
    response = await call_next(request)
    if origin:
        acao = response.headers.get("access-control-allow-origin", "<not set>")
        logger.info(
            "[CORS] Access-Control-Allow-Origin: %s  (request origin: %s)",
            acao, origin,
        )
    return response


# ── Security headers middleware ───────────────────────────────────────────────
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)

    # Prevent MIME-type sniffing
    response.headers["X-Content-Type-Options"] = "nosniff"
    # Block clickjacking
    response.headers["X-Frame-Options"] = "DENY"
    # Legacy XSS filter (belt-and-suspenders)
    response.headers["X-XSS-Protection"] = "1; mode=block"
    # Limit referrer info
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    # Restrict browser features
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=(), payment=()"
    # Remove server fingerprint header added by uvicorn
    response.headers.pop("server", None)

    # HSTS — only meaningful over HTTPS; safe to send always so it's effective
    # the moment the site moves to HTTPS
    response.headers["Strict-Transport-Security"] = (
        "max-age=31536000; includeSubDomains; preload"
    )

    return response


# ── Production error handler — no stack traces to clients ────────────────────
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    if settings.is_production:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An internal server error occurred."},
        )
    # Development: include type and message for easier debugging
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": str(exc), "type": type(exc).__name__},
    )


# ── Routers ───────────────────────────────────────────────────────────────────
from app.auth.router import router as auth_router  # noqa: E402
from app.predictions.router import router as predictions_router  # noqa: E402
from app.dashboard.router import router as dashboard_router  # noqa: E402
from app.customers.router import router as customers_router  # noqa: E402

app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(predictions_router, prefix="/predictions", tags=["Predictions"])
app.include_router(dashboard_router, prefix="/dashboard", tags=["Dashboard"])
app.include_router(customers_router, prefix="/customers", tags=["Customers"])


@app.get("/health", tags=["Health"])
def health():
    from ml.predict import get_metrics, is_loaded
    m = get_metrics()
    return {
        "status": "healthy",
        "model_loaded": is_loaded(),
        "model_type": m.get("model_type"),
        "model_auc": m.get("roc_auc"),
        "environment": settings.ENVIRONMENT,
    }
