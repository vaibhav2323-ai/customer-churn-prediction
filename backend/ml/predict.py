# loads the saved model + explainer and runs predictions
# also handles the SHAP output - took a while to figure out the shape differences
# between XGBoost and sklearn models (XGB returns 2D array, sklearn returns list of arrays)
import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

MODELS_DIR = Path(__file__).parent / "models"

_model: Any = None
_scaler: Any = None
_explainer: Any = None
_feature_cols: list[str] = []
_metadata: dict = {}

FEATURE_LABELS: dict[str, str] = {
    "gender": "Gender",
    "senior_citizen": "Senior Citizen",
    "partner": "Has Partner",
    "dependents": "Has Dependents",
    "tenure": "Tenure (months)",
    "phone_service": "Phone Service",
    "multiple_lines": "Multiple Lines",
    "internet_service": "Internet Service",
    "online_security": "Online Security",
    "online_backup": "Online Backup",
    "device_protection": "Device Protection",
    "tech_support": "Tech Support",
    "streaming_tv": "Streaming TV",
    "streaming_movies": "Streaming Movies",
    "contract": "Contract Type",
    "paperless_billing": "Paperless Billing",
    "payment_method": "Payment Method",
    "monthly_charges": "Monthly Charges ($)",
    "total_charges": "Total Charges ($)",
}


def load_model() -> bool:
    global _model, _scaler, _explainer, _feature_cols, _metadata

    _model = joblib.load(MODELS_DIR / "model.pkl")
    _scaler = joblib.load(MODELS_DIR / "scaler.pkl")
    _explainer = joblib.load(MODELS_DIR / "explainer.pkl")
    _feature_cols = joblib.load(MODELS_DIR / "feature_cols.pkl")

    with open(MODELS_DIR / "metadata.json") as f:
        _metadata = json.load(f)

    return True


def is_loaded() -> bool:
    return _model is not None


def get_metrics():
    return _metadata.get("metrics", {})


def _encode_row(data: dict) -> dict:
    yn = {"Yes": 1, "No": 0, True: 1, False: 0, 1: 1, 0: 0}
    multi_map = {"No phone service": 0, "No": 1, "Yes": 2}
    addon_map = {"No internet service": 0, "No": 1, "Yes": 2}

    return {
        "gender": 1 if str(data.get("gender", "Male")).lower() == "male" else 0,
        "senior_citizen": int(data.get("senior_citizen", 0)),
        "partner": yn.get(data.get("partner", "No"), 0),
        "dependents": yn.get(data.get("dependents", "No"), 0),
        "tenure": int(data.get("tenure", 0)),
        "phone_service": yn.get(data.get("phone_service", "Yes"), 1),
        "multiple_lines": multi_map.get(str(data.get("multiple_lines", "No")), 1),
        "internet_service": {"No": 0, "DSL": 1, "Fiber optic": 2}.get(
            str(data.get("internet_service", "DSL")), 1
        ),
        "online_security": addon_map.get(str(data.get("online_security", "No")), 1),
        "online_backup": addon_map.get(str(data.get("online_backup", "No")), 1),
        "device_protection": addon_map.get(str(data.get("device_protection", "No")), 1),
        "tech_support": addon_map.get(str(data.get("tech_support", "No")), 1),
        "streaming_tv": addon_map.get(str(data.get("streaming_tv", "No")), 1),
        "streaming_movies": addon_map.get(str(data.get("streaming_movies", "No")), 1),
        "contract": {"Month-to-month": 0, "One year": 1, "Two year": 2}.get(
            str(data.get("contract", "Month-to-month")), 0
        ),
        "paperless_billing": yn.get(data.get("paperless_billing", "Yes"), 1),
        "payment_method": {
            "Mailed check": 0,
            "Bank transfer (automatic)": 1,
            "Credit card (automatic)": 2,
            "Electronic check": 3,
        }.get(str(data.get("payment_method", "Electronic check")), 3),
        "monthly_charges": float(data.get("monthly_charges", 65.0)),
        "total_charges": float(data.get("total_charges", 1000.0)),
    }


def _risk_level(prob: float) -> str:
    if prob >= 0.70:
        return "High"
    if prob >= 0.40:
        return "Medium"
    return "Low"


def predict_single(data: dict) -> dict:
    if not is_loaded():
        load_model()

    row = _encode_row(data)
    X = pd.DataFrame([row])[_feature_cols]

    X_input = _scaler.transform(X) if _metadata.get("needs_scaling") else X.values

    probability = float(_model.predict_proba(X_input)[0][1])
    risk = _risk_level(probability)

    # SHAP - this part was confusing, XGBoost returns a 2D array directly
    # but sklearn models return a list of arrays (one per class)
    # TODO: double check this still works if we ever switch models
    sv_raw = _explainer.shap_values(X_input)
    if isinstance(sv_raw, list):
        sv = np.array(sv_raw[1][0])
    else:
        sv = np.array(sv_raw[0])

    impacts = [
        {
            "feature": FEATURE_LABELS.get(col, col),
            "feature_key": col,
            "shap_value": float(sv[i]),
            "raw_value": float(X[col].iloc[0]),
        }
        for i, col in enumerate(_feature_cols)
    ]
    impacts.sort(key=lambda x: abs(x["shap_value"]), reverse=True)

    top_reasons = [
        {
            "feature": imp["feature"],
            "impact": round(imp["shap_value"], 4),
            "direction": "increases" if imp["shap_value"] > 0 else "decreases",
        }
        for imp in impacts[:5]
    ]

    return {
        "churn_probability": round(probability, 4),
        "churn_prediction": int(probability >= 0.5),
        "risk_level": risk,
        "top_reasons": top_reasons,
        "feature_impacts": impacts[:10],
    }


def predict_batch(records: list[dict]):
    if not is_loaded():
        load_model()

    if not records:
        return []

    rows = [_encode_row(r) for r in records]
    X = pd.DataFrame(rows)[_feature_cols]
    X_input = _scaler.transform(X) if _metadata.get("needs_scaling") else X.values

    probs = _model.predict_proba(X_input)[:, 1]

    sv_raw = _explainer.shap_values(X_input)
    if isinstance(sv_raw, list):
        sv_all = np.array(sv_raw[1])
    else:
        sv_all = np.array(sv_raw)

    results = []
    for i, prob in enumerate(probs):
        sv = sv_all[i]
        impacts = sorted(
            [
                {
                    "feature": FEATURE_LABELS.get(col, col),
                    "feature_key": col,
                    "shap_value": float(sv[j]),
                    "raw_value": float(X.iloc[i][col]),
                }
                for j, col in enumerate(_feature_cols)
            ],
            key=lambda x: abs(x["shap_value"]),
            reverse=True,
        )
        top_reasons = [
            {
                "feature": imp["feature"],
                "impact": round(imp["shap_value"], 4),
                "direction": "increases" if imp["shap_value"] > 0 else "decreases",
            }
            for imp in impacts[:5]
        ]
        results.append(
            {
                "churn_probability": round(float(prob), 4),
                "churn_prediction": int(prob >= 0.5),
                "risk_level": _risk_level(float(prob)),
                "top_reasons": top_reasons,
                "status": "success",
            }
        )

    return results
