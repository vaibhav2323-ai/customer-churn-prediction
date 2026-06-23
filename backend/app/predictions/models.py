from datetime import datetime, timezone
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    customer_id: Mapped[str] = mapped_column(String(128), index=True, default="")
    input_data: Mapped[str] = mapped_column(Text, nullable=False)
    churn_probability: Mapped[float] = mapped_column(Float, nullable=False)
    churn_prediction: Mapped[int] = mapped_column(Integer, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False)
    shap_data: Mapped[str] = mapped_column(Text, default="[]")
    source: Mapped[str] = mapped_column(String(16), default="single")  # single | batch
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
