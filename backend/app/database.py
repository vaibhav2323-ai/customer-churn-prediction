# TODO: swap SQLite for postgres before going to prod for real
# sqlite is fine for single instance but can't handle concurrent writes
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    from app.auth.models import User  # noqa: F401
    from app.auth.refresh_models import RefreshToken  # noqa: F401
    from app.predictions.models import Prediction  # noqa: F401
    Base.metadata.create_all(bind=engine)
