import logging
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
    logger.info("DB tables ready")

    from ml.predict import load_model
    load_model()
    logger.info("ML model loaded")

    from scripts.seed import ensure_demo_user
    try:
        ensure_demo_user()
    except Exception as exc:
        logger.error("ensure_demo_user failed: %s", exc, exc_info=True)

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

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
    expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining", "Retry-After"],
    max_age=600,
)


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    if settings.is_production:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An internal server error occurred."},
        )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": str(exc), "type": type(exc).__name__},
    )


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
