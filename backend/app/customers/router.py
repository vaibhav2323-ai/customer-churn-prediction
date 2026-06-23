import json
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.models import User
from app.auth.utils import get_current_user
from app.database import get_db
from app.limiter import limiter
from app.predictions.models import Prediction

router = APIRouter()


@router.get("")
@limiter.limit("60/minute")
def list_customers(
    request: Request,
    page: int = Query(1, ge=1, le=10000),
    page_size: int = Query(20, ge=1, le=100),
    risk_level: Optional[str] = Query(None, pattern="^(High|Medium|Low)$"),
    search: Optional[str] = Query(None, max_length=64),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Subquery: latest prediction ID per customer_id for this user
    latest_subq = (
        db.query(
            Prediction.customer_id,
            func.max(Prediction.id).label("max_id"),
        )
        .filter(Prediction.user_id == current_user.id)
        .group_by(Prediction.customer_id)
        .subquery()
    )

    query = db.query(Prediction).join(
        latest_subq,
        (Prediction.customer_id == latest_subq.c.customer_id)
        & (Prediction.id == latest_subq.c.max_id),
    )

    if risk_level:
        query = query.filter(Prediction.risk_level == risk_level)
    if search:
        query = query.filter(Prediction.customer_id.ilike(f"%{search}%"))

    total = query.count()
    items = (
        query.order_by(Prediction.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    customers = []
    for p in items:
        try:
            inp = json.loads(p.input_data)
        except Exception:
            inp = {}
        customers.append(
            {
                "customer_id": p.customer_id,
                "churn_probability": p.churn_probability,
                "churn_prediction": p.churn_prediction,
                "risk_level": p.risk_level,
                "contract": inp.get("contract", "—"),
                "tenure": inp.get("tenure", "—"),
                "monthly_charges": inp.get("monthly_charges", "—"),
                "internet_service": inp.get("internet_service", "—"),
                "last_predicted": p.created_at.isoformat(),
                "prediction_id": p.id,
            }
        )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, -(-total // page_size)),
        "customers": customers,
    }
