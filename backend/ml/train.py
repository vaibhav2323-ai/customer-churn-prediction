# trains XGBoost and LR on synthetic telco data, picks the better one by ROC-AUC
# TODO: try with the real IBM Telco dataset from Kaggle - synthetic might be too clean
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import shap
import xgboost as xgb
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

MODELS_DIR = Path(__file__).parent / "models"
MODELS_DIR.mkdir(exist_ok=True)


def generate_synthetic_data(n_samples: int = 7043) -> pd.DataFrame:
    rng = np.random.default_rng(42)

    gender = rng.choice(["Male", "Female"], n_samples)
    senior_citizen = rng.binomial(1, 0.16, n_samples)
    partner = rng.choice(["Yes", "No"], n_samples, p=[0.48, 0.52])
    dependents = np.where(
        partner == "Yes",
        rng.choice(["Yes", "No"], n_samples, p=[0.46, 0.54]),
        rng.choice(["Yes", "No"], n_samples, p=[0.13, 0.87]),
    )

    contract = rng.choice(
        ["Month-to-month", "One year", "Two year"],
        n_samples,
        p=[0.55, 0.21, 0.24],
    )

    tenure_raw = np.where(
        contract == "Month-to-month",
        rng.exponential(15, n_samples),
        np.where(
            contract == "One year",
            rng.normal(35, 15, n_samples),
            rng.normal(55, 12, n_samples),
        ),
    )
    tenure = np.clip(tenure_raw, 1, 72).astype(int)

    internet_service = rng.choice(
        ["DSL", "Fiber optic", "No"], n_samples, p=[0.34, 0.44, 0.22]
    )
    has_internet = internet_service != "No"

    phone_service = rng.choice(["Yes", "No"], n_samples, p=[0.90, 0.10])
    multiple_lines = np.where(
        phone_service == "No",
        "No phone service",
        rng.choice(["Yes", "No"], n_samples, p=[0.42, 0.58]),
    )

    def inet_feature(p_yes: float = 0.30) -> np.ndarray:
        vals = rng.choice(["Yes", "No"], n_samples, p=[p_yes, 1 - p_yes])
        return np.where(has_internet, vals, "No internet service")

    online_security = inet_feature(0.29)
    online_backup = inet_feature(0.34)
    device_protection = inet_feature(0.34)
    tech_support = inet_feature(0.29)
    streaming_tv = inet_feature(0.38)
    streaming_movies = inet_feature(0.39)

    paperless_billing = rng.choice(["Yes", "No"], n_samples, p=[0.59, 0.41])
    payment_method = rng.choice(
        [
            "Electronic check",
            "Mailed check",
            "Bank transfer (automatic)",
            "Credit card (automatic)",
        ],
        n_samples,
        p=[0.34, 0.23, 0.22, 0.21],
    )

    base_charge = np.where(
        internet_service == "No",
        20.0,
        np.where(internet_service == "DSL", 45.0, 75.0),
    )
    phone_charge = np.where(phone_service == "Yes", 20.0, 0.0)
    addon_count = (
        (online_security == "Yes").astype(int)
        + (online_backup == "Yes").astype(int)
        + (device_protection == "Yes").astype(int)
        + (tech_support == "Yes").astype(int)
        + (streaming_tv == "Yes").astype(int)
        + (streaming_movies == "Yes").astype(int)
    )
    monthly_charges = np.clip(
        base_charge + phone_charge + addon_count * 10 + rng.normal(0, 5, n_samples),
        18,
        120,
    ).round(2)
    total_charges = np.clip(
        tenure * monthly_charges + rng.normal(0, 50, n_samples), 0, None
    ).round(2)

    # hand-tuned churn score weights based on what I saw in the kaggle dataset EDA
    # Logistic churn score
    score = np.zeros(n_samples)
    score += np.where(contract == "Month-to-month", 2.0, 0.0)
    score += np.where(contract == "One year", 0.5, 0.0)
    score -= tenure / 30.0
    score += np.where(internet_service == "Fiber optic", 1.0, 0.0)
    score += np.where(payment_method == "Electronic check", 0.8, 0.0)
    score += (monthly_charges - 65) / 50.0
    score += np.where(online_security == "No", 0.5, 0.0)
    score += np.where(tech_support == "No", 0.5, 0.0)
    score += np.where(senior_citizen == 1, 0.3, 0.0)
    score -= np.where(partner == "Yes", 0.3, 0.0)
    score -= np.where(dependents == "Yes", 0.3, 0.0)

    churn_prob = 1 / (1 + np.exp(-score + 0.5))
    churn = (rng.random(n_samples) < churn_prob).astype(int)

    return pd.DataFrame(
        {
            "gender": gender,
            "senior_citizen": senior_citizen,
            "partner": partner,
            "dependents": dependents,
            "tenure": tenure,
            "phone_service": phone_service,
            "multiple_lines": multiple_lines,
            "internet_service": internet_service,
            "online_security": online_security,
            "online_backup": online_backup,
            "device_protection": device_protection,
            "tech_support": tech_support,
            "streaming_tv": streaming_tv,
            "streaming_movies": streaming_movies,
            "contract": contract,
            "paperless_billing": paperless_billing,
            "payment_method": payment_method,
            "monthly_charges": monthly_charges,
            "total_charges": total_charges,
            "churn": churn,
        }
    )


def encode_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    for col in ["partner", "dependents", "phone_service", "paperless_billing"]:
        df[col] = df[col].map({"Yes": 1, "No": 0}).astype(int)

    df["gender"] = df["gender"].map({"Male": 1, "Female": 0}).astype(int)
    df["senior_citizen"] = df["senior_citizen"].astype(int)

    df["multiple_lines"] = df["multiple_lines"].map(
        {"No phone service": 0, "No": 1, "Yes": 2}
    ).astype(int)

    df["internet_service"] = df["internet_service"].map(
        {"No": 0, "DSL": 1, "Fiber optic": 2}
    ).astype(int)

    addon_map = {"No internet service": 0, "No": 1, "Yes": 2}
    for col in [
        "online_security", "online_backup", "device_protection",
        "tech_support", "streaming_tv", "streaming_movies",
    ]:
        df[col] = df[col].map(addon_map).astype(int)

    df["contract"] = df["contract"].map(
        {"Month-to-month": 0, "One year": 1, "Two year": 2}
    ).astype(int)

    df["payment_method"] = df["payment_method"].map(
        {
            "Mailed check": 0,
            "Bank transfer (automatic)": 1,
            "Credit card (automatic)": 2,
            "Electronic check": 3,
        }
    ).astype(int)

    return df


def train_models() -> None:
    print("Generating synthetic Telco Customer Churn dataset …")
    df_raw = generate_synthetic_data(7043)
    df_raw.to_csv(MODELS_DIR / "sample_data.csv", index=False)

    print(f"  Rows: {len(df_raw)}  |  Churn rate: {df_raw['churn'].mean():.2%}")

    df = encode_dataframe(df_raw)
    feature_cols: list[str] = [c for c in df.columns if c != "churn"]
    X = df[feature_cols]
    y = df["churn"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    scaler = StandardScaler()
    X_train_sc = scaler.fit_transform(X_train)
    X_test_sc = scaler.transform(X_test)

    # ---------- Logistic Regression ----------
    print("\nTraining Logistic Regression …")
    lr = LogisticRegression(max_iter=1000, random_state=42, C=0.5)
    lr.fit(X_train_sc, y_train)
    lr_prob = lr.predict_proba(X_test_sc)[:, 1]
    lr_pred = (lr_prob >= 0.5).astype(int)
    lr_auc = roc_auc_score(y_test, lr_prob)
    print(f"  ROC-AUC: {lr_auc:.4f}")
    print(classification_report(y_test, lr_pred, target_names=["No Churn", "Churn"]))

    # ---------- XGBoost ----------
    print("Training XGBoost …")
    xgb_model = xgb.XGBClassifier(
        n_estimators=300,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        eval_metric="logloss",
        random_state=42,
        n_jobs=-1,
        verbosity=0,
    )
    xgb_model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=False,
    )
    xgb_prob = xgb_model.predict_proba(X_test)[:, 1]
    xgb_pred = (xgb_prob >= 0.5).astype(int)
    xgb_auc = roc_auc_score(y_test, xgb_prob)
    print(f"  ROC-AUC: {xgb_auc:.4f}")
    print(classification_report(y_test, xgb_pred, target_names=["No Churn", "Churn"]))

    # ---------- Select winner ----------
    if xgb_auc >= lr_auc:
        print(f"\n✓ XGBoost selected (AUC {xgb_auc:.4f} ≥ {lr_auc:.4f})")
        best_model = xgb_model
        best_pred = xgb_pred
        best_prob = xgb_prob
        model_type = "xgboost"
        needs_scaling = False
        # TreeExplainer is way faster than KernelExplainer for tree models
        # figured this out from the SHAP docs: https://shap.readthedocs.io/en/latest/
        explainer = shap.TreeExplainer(xgb_model)
    else:
        print(f"\n✓ Logistic Regression selected (AUC {lr_auc:.4f} > {xgb_auc:.4f})")
        best_model = lr
        best_pred = lr_pred
        best_prob = lr_prob
        model_type = "logistic_regression"
        needs_scaling = True
        explainer = shap.LinearExplainer(lr, X_train_sc, feature_perturbation="interventional")

    metrics = {
        "model_type": model_type,
        "accuracy": float(accuracy_score(y_test, best_pred)),
        "precision": float(precision_score(y_test, best_pred, zero_division=0)),
        "recall": float(recall_score(y_test, best_pred, zero_division=0)),
        "f1": float(f1_score(y_test, best_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_test, best_prob)),
        "xgboost_auc": float(xgb_auc),
        "lr_auc": float(lr_auc),
        "churn_rate": float(y.mean()),
        "n_samples": int(len(df)),
        "n_features": len(feature_cols),
    }
    print(f"\nMetrics: {json.dumps(metrics, indent=2)}")

    metadata = {
        "model_type": model_type,
        "needs_scaling": needs_scaling,
        "feature_cols": feature_cols,
        "metrics": metrics,
    }

    joblib.dump(best_model, MODELS_DIR / "model.pkl")
    joblib.dump(scaler, MODELS_DIR / "scaler.pkl")
    joblib.dump(explainer, MODELS_DIR / "explainer.pkl")
    joblib.dump(feature_cols, MODELS_DIR / "feature_cols.pkl")

    with open(MODELS_DIR / "metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

    with open(MODELS_DIR / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"\nartifacts saved to {MODELS_DIR}")


if __name__ == "__main__":
    train_models()
