import re
from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator


def _safe_id(v: str | None) -> str | None:
    if v is None:
        return v
    if not re.match(r'^[A-Za-z0-9\-_]{1,64}$', v):
        raise ValueError("customer_id may only contain letters, digits, hyphens and underscores (max 64 chars)")
    return v


class CustomerInput(BaseModel):
    customer_id: Optional[str] = Field(None, max_length=64)
    gender: Literal["Male", "Female"] = "Male"
    senior_citizen: int = Field(ge=0, le=1, default=0)
    partner: Literal["Yes", "No"] = "No"
    dependents: Literal["Yes", "No"] = "No"
    tenure: int = Field(ge=0, le=72, default=12)
    phone_service: Literal["Yes", "No"] = "Yes"
    multiple_lines: Literal["Yes", "No", "No phone service"] = "No"
    internet_service: Literal["DSL", "Fiber optic", "No"] = "DSL"
    online_security: Literal["Yes", "No", "No internet service"] = "No"
    online_backup: Literal["Yes", "No", "No internet service"] = "No"
    device_protection: Literal["Yes", "No", "No internet service"] = "No"
    tech_support: Literal["Yes", "No", "No internet service"] = "No"
    streaming_tv: Literal["Yes", "No", "No internet service"] = "No"
    streaming_movies: Literal["Yes", "No", "No internet service"] = "No"
    contract: Literal["Month-to-month", "One year", "Two year"] = "Month-to-month"
    paperless_billing: Literal["Yes", "No"] = "Yes"
    payment_method: Literal[
        "Electronic check",
        "Mailed check",
        "Bank transfer (automatic)",
        "Credit card (automatic)",
    ] = "Electronic check"
    monthly_charges: float = Field(ge=0.0, le=500.0, default=65.0)
    total_charges: float = Field(ge=0.0, le=1_000_000.0, default=1000.0)

    @field_validator("customer_id")
    @classmethod
    def validate_customer_id(cls, v):
        return _safe_id(v)


class ReasonItem(BaseModel):
    feature: str
    impact: float
    direction: str


class ImpactItem(BaseModel):
    feature: str
    feature_key: str
    shap_value: float
    raw_value: float


class PredictionResult(BaseModel):
    churn_probability: float
    churn_prediction: int
    risk_level: str
    top_reasons: list[ReasonItem]
    feature_impacts: list[ImpactItem]
    prediction_id: Optional[int] = None


class PredictionRecord(BaseModel):
    id: int
    customer_id: str
    churn_probability: float
    churn_prediction: int
    risk_level: str
    source: str
    created_at: datetime

    model_config = {"from_attributes": True}


class BatchResult(BaseModel):
    total: int
    successful: int
    failed: int
    results: list[dict[str, Any]]
