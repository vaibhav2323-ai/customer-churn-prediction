from collections import defaultdict
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.models import User
from app.auth.utils import get_current_user
from app.database import get_db
from app.limiter import limiter
from app.predictions.models import Prediction
from ml.predict import get_metrics

router = APIRouter()


@router.get("/stats")
@limiter.limit("60/minute")
def dashboard_stats(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    base_q = db.query(Prediction).filter(Prediction.user_id == current_user.id)
    total_predictions = base_q.count()

    high_risk = base_q.filter(Prediction.risk_level == "High").count()
    medium_risk = base_q.filter(Prediction.risk_level == "Medium").count()
    low_risk = base_q.filter(Prediction.risk_level == "Low").count()

    avg_prob_row = db.query(func.avg(Prediction.churn_probability)).filter(
        Prediction.user_id == current_user.id
    ).scalar()
    avg_probability = round(float(avg_prob_row or 0), 4)

    churned_count = base_q.filter(Prediction.churn_prediction == 1).count()
    churn_rate = round(churned_count / total_predictions, 4) if total_predictions else 0.0

    # Monthly trend – last 6 months
    six_months_ago = datetime.now(timezone.utc) - timedelta(days=180)
    recent = (
        base_q.filter(Prediction.created_at >= six_months_ago)
        .order_by(Prediction.created_at)
        .all()
    )

    month_buckets: dict[str, list[float]] = defaultdict(list)
    for p in recent:
        key = p.created_at.strftime("%b %Y")
        month_buckets[key].append(p.churn_probability)

    monthly_trend = [
        {
            "month": month,
            "avg_probability": round(sum(probs) / len(probs), 4),
            "count": len(probs),
        }
        for month, probs in month_buckets.items()
    ]

    model_metrics = get_metrics()

    return {
        "total_predictions": total_predictions,
        "high_risk_count": high_risk,
        "medium_risk_count": medium_risk,
        "low_risk_count": low_risk,
        "avg_churn_probability": avg_probability,
        "overall_churn_rate": churn_rate,
        "churned_count": churned_count,
        "risk_distribution": [
            {"risk": "High", "count": high_risk},
            {"risk": "Medium", "count": medium_risk},
            {"risk": "Low", "count": low_risk},
        ],
        "monthly_trend": monthly_trend,
        "model_metrics": model_metrics,
    }
