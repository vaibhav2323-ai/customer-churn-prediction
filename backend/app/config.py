from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Runtime environment ─────────────────────────────────────────────────
    ENVIRONMENT: str = "development"  # Set to "production" in prod

    # ── JWT ─────────────────────────────────────────────────────────────────
    # These MUST be changed in production (generate with: openssl rand -hex 32)
    SECRET_KEY: str = "dev-only-do-NOT-use-in-production-change-me!!"
    REFRESH_SECRET_KEY: str = "dev-only-refresh-do-NOT-use-in-production!!!"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15       # Short-lived access tokens
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7          # Longer-lived refresh tokens

    # ── Database ────────────────────────────────────────────────────────────
    DATABASE_URL: str = "sqlite:///./churn.db"

    # ── CORS — no wildcard allowed in production ────────────────────────────
    # Vercel production URL is included as a default so the deployment works
    # even if the CORS_ORIGINS env var is not explicitly set on Render.
    # Override via env var to add/remove origins for your own deployment.
    CORS_ORIGINS: str = (
        "http://localhost:3000,"
        "http://localhost:5173,"
        "https://customer-churn-prediction-dun.vercel.app"
    )

    # ── Brute-force protection ──────────────────────────────────────────────
    LOGIN_MAX_ATTEMPTS: int = 5
    LOGIN_LOCKOUT_MINUTES: int = 15

    # ── Cookie security ─────────────────────────────────────────────────────
    COOKIE_SECURE: bool = False   # True in production (HTTPS only)
    COOKIE_SAMESITE: str = "lax"  # "strict" is safer; "lax" allows top-level nav

    @field_validator("SECRET_KEY", "REFRESH_SECRET_KEY")
    @classmethod
    def enforce_key_strength(cls, v: str, info) -> str:
        if len(v) < 32:
            raise ValueError(f"{info.field_name} must be at least 32 characters")
        return v

    @field_validator("CORS_ORIGINS")
    @classmethod
    def no_wildcard_cors(cls, v: str) -> str:
        if "*" in v:
            raise ValueError("Wildcard CORS origin '*' is not permitted — specify exact origins")
        return v

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
