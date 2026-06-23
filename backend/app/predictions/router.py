"""
Prediction endpoints.

All routes:
- Require JWT (get_current_user)
- Are rate-limited (tighter limits on heavier endpoints)
- Use parameterised ORM queries only — no raw SQL, no string formatting
- Validate input strictly via CustomerInput (Pydantic, Literal types)
- Never echo internal error messages in production
"""
import io
import json
import logging
import re
import uuid
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.auth.models import User
from app.auth.utils import get_current_user
from app.database import get_db
from app.limiter import limiter
from app.predictions.models import Prediction
from app.predictions.schemas import BatchResult, CustomerInput, PredictionRecord, PredictionResult
from ml.predict import predict_batch, predict_single

logger = logging.getLogger(__name__)
router = APIRouter()

_SAFE_CUSTOMER_ID_RE = re.compile(r'^[A-Za-z0-9\-_]{1,64}$')


def _safe_customer_id(raw: str | None) -> str:
    """Return a valid customer-ID or generate one; strip anything unsafe."""
    if raw and _SAFE_CUSTOMER_ID_RE.match(raw):
        return raw
    return f"C-{uuid.uuid4().hex[:8].upper()}"


# ── Single prediction ─────────────────────────────────────────────────────────

@router.post("/predict", response_model=PredictionResult)
@limiter.limit("30/minute")
def predict(
    request: Request,
    payload: CustomerInput,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        result = predict_single(payload.model_dump())
    except Exception as exc:
        logger.exception("predict_single failed for user %s", current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Prediction service error",
        )

    customer_id = _safe_customer_id(payload.customer_id)

    # ORM insert — parameterised, no raw SQL
    prediction = Prediction(
        user_id=current_user.id,
        customer_id=customer_id,
        input_data=payload.model_dump_json(),
        churn_probability=result["churn_probability"],
        churn_prediction=result["churn_prediction"],
        risk_level=result["risk_level"],
        shap_data=json.dumps(result.get("top_reasons", [])),
        source="single",
    )
    db.add(prediction)
    db.commit()
    db.refresh(prediction)

    return PredictionResult(**result, prediction_id=prediction.id)


# ── Batch prediction ──────────────────────────────────────────────────────────

@router.post("/batch-predict", response_model=BatchResult)
@limiter.limit("5/minute")      # Heavy endpoint — tighter limit
async def batch_predict(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # File-type validation — check both name and content type
    filename = file.filename or ""
    content_type = file.content_type or ""
    if not filename.lower().endswith(".csv") and "csv" not in content_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV files are accepted",
        )

    # Cap file size to 5 MB before parsing
    MAX_BYTES = 5 * 1024 * 1024
    contents = await file.read(MAX_BYTES + 1)
    if len(contents) > MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds 5 MB limit",
        )

    try:
        df = pd.read_csv(io.BytesIO(contents))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not parse CSV — ensure it is valid UTF-8 comma-separated text",
        )

    if len(df) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CSV has no data rows")

    if len(df) > 1000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Max 1,000 rows per batch",
        )

    records = df.to_dict("records")

    try:
        results = predict_batch(records)
    except Exception:
        logger.exception("predict_batch failed for user %s", current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Batch prediction service error",
        )

    successful = 0
    for record, res in zip(records, results):
        if res.get("status") == "success":
            prediction = Prediction(
                user_id=current_user.id,
                customer_id=_safe_customer_id(str(record.get("customer_id", ""))),
                input_data=json.dumps(record),
                churn_probability=res["churn_probability"],
                churn_prediction=res["churn_prediction"],
                risk_level=res["risk_level"],
                shap_data=json.dumps(res.get("top_reasons", [])),
                source="batch",
            )
            db.add(prediction)
            successful += 1

    db.commit()

    return BatchResult(
        total=len(results),
        successful=successful,
        failed=len(results) - successful,
        results=results,
    )


# ── History ───────────────────────────────────────────────────────────────────

@router.get("/history", response_model=dict)
@limiter.limit("60/minute")
def prediction_history(
    request: Request,
    page: int = Query(1, ge=1, le=10000),
    page_size: int = Query(20, ge=1, le=100),
    risk_level: Optional[str] = Query(None, pattern="^(High|Medium|Low)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # ORM filter — never interpolate risk_level directly into SQL
    query = db.query(Prediction).filter(Prediction.user_id == current_user.id)
    if risk_level:
        query = query.filter(Prediction.risk_level == risk_level)

    total = query.count()
    items = (
        query.order_by(Prediction.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, -(-total // page_size)),
        "items": [PredictionRecord.model_validate(p) for p in items],
    }
