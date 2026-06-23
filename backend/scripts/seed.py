import json
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.auth.models import User
from app.auth.utils import hash_password
from app.database import SessionLocal, create_tables
from app.predictions.models import Prediction
from ml.predict import load_model, predict_single

DEMO_EMAIL = "demo@churnprediction.ai"
DEMO_PASSWORD = "Demo1234!"
DEMO_NAME = "Demo User"

SAMPLE_CUSTOMERS = [
    # High-risk profiles
    {"gender": "Male", "senior_citizen": 0, "partner": "No", "dependents": "No",
     "tenure": 3, "phone_service": "Yes", "multiple_lines": "No",
     "internet_service": "Fiber optic", "online_security": "No", "online_backup": "No",
     "device_protection": "No", "tech_support": "No", "streaming_tv": "Yes",
     "streaming_movies": "Yes", "contract": "Month-to-month",
     "paperless_billing": "Yes", "payment_method": "Electronic check",
     "monthly_charges": 89.95, "total_charges": 269.85},
    {"gender": "Female", "senior_citizen": 1, "partner": "No", "dependents": "No",
     "tenure": 6, "phone_service": "Yes", "multiple_lines": "Yes",
     "internet_service": "Fiber optic", "online_security": "No", "online_backup": "No",
     "device_protection": "No", "tech_support": "No", "streaming_tv": "No",
     "streaming_movies": "No", "contract": "Month-to-month",
     "paperless_billing": "Yes", "payment_method": "Electronic check",
     "monthly_charges": 98.00, "total_charges": 588.0},
    # Medium-risk profiles
    {"gender": "Male", "senior_citizen": 0, "partner": "Yes", "dependents": "No",
     "tenure": 18, "phone_service": "Yes", "multiple_lines": "No",
     "internet_service": "DSL", "online_security": "Yes", "online_backup": "No",
     "device_protection": "Yes", "tech_support": "No", "streaming_tv": "No",
     "streaming_movies": "No", "contract": "Month-to-month",
     "paperless_billing": "No", "payment_method": "Mailed check",
     "monthly_charges": 55.90, "total_charges": 1006.2},
    {"gender": "Female", "senior_citizen": 0, "partner": "Yes", "dependents": "Yes",
     "tenure": 24, "phone_service": "Yes", "multiple_lines": "No",
     "internet_service": "DSL", "online_security": "No", "online_backup": "Yes",
     "device_protection": "No", "tech_support": "No", "streaming_tv": "No",
     "streaming_movies": "No", "contract": "One year",
     "paperless_billing": "Yes", "payment_method": "Credit card (automatic)",
     "monthly_charges": 60.15, "total_charges": 1443.6},
    # Low-risk profiles
    {"gender": "Male", "senior_citizen": 0, "partner": "Yes", "dependents": "Yes",
     "tenure": 60, "phone_service": "Yes", "multiple_lines": "Yes",
     "internet_service": "DSL", "online_security": "Yes", "online_backup": "Yes",
     "device_protection": "Yes", "tech_support": "Yes", "streaming_tv": "Yes",
     "streaming_movies": "Yes", "contract": "Two year",
     "paperless_billing": "No", "payment_method": "Bank transfer (automatic)",
     "monthly_charges": 110.00, "total_charges": 6600.0},
    {"gender": "Female", "senior_citizen": 0, "partner": "Yes", "dependents": "Yes",
     "tenure": 70, "phone_service": "Yes", "multiple_lines": "Yes",
     "internet_service": "DSL", "online_security": "Yes", "online_backup": "Yes",
     "device_protection": "Yes", "tech_support": "Yes", "streaming_tv": "No",
     "streaming_movies": "No", "contract": "Two year",
     "paperless_billing": "Yes", "payment_method": "Credit card (automatic)",
     "monthly_charges": 79.50, "total_charges": 5565.0},
]

CONTRACTS = ["Month-to-month", "One year", "Two year"]
INTERNET = ["DSL", "Fiber optic", "No"]
PAYMENT = ["Electronic check", "Mailed check", "Bank transfer (automatic)", "Credit card (automatic)"]
YN = ["Yes", "No"]


def random_customer() -> dict:
    contract = random.choice(CONTRACTS)
    internet = random.choice(INTERNET)
    tenure = random.randint(1, 72)
    monthly = round(random.uniform(20, 110), 2)
    return {
        "gender": random.choice(["Male", "Female"]),
        "senior_citizen": random.choice([0, 1]),
        "partner": random.choice(YN),
        "dependents": random.choice(YN),
        "tenure": tenure,
        "phone_service": random.choice(YN),
        "multiple_lines": random.choice(["Yes", "No", "No phone service"]),
        "internet_service": internet,
        "online_security": random.choice(["Yes", "No"] if internet != "No" else ["No internet service"]),
        "online_backup": random.choice(["Yes", "No"] if internet != "No" else ["No internet service"]),
        "device_protection": random.choice(["Yes", "No"] if internet != "No" else ["No internet service"]),
        "tech_support": random.choice(["Yes", "No"] if internet != "No" else ["No internet service"]),
        "streaming_tv": random.choice(["Yes", "No"] if internet != "No" else ["No internet service"]),
        "streaming_movies": random.choice(["Yes", "No"] if internet != "No" else ["No internet service"]),
        "contract": contract,
        "paperless_billing": random.choice(YN),
        "payment_method": random.choice(PAYMENT),
        "monthly_charges": monthly,
        "total_charges": round(monthly * tenure, 2),
    }


def ensure_demo_user() -> None:
    create_tables()
    db = SessionLocal()
    try:
        if not db.query(User).filter(User.email == DEMO_EMAIL).first():
            db.add(User(
                email=DEMO_EMAIL,
                hashed_password=hash_password(DEMO_PASSWORD),
                full_name=DEMO_NAME,
            ))
            db.commit()
            print(f"[startup] Demo user created → {DEMO_EMAIL} / {DEMO_PASSWORD}")
        else:
            print(f"[startup] Demo user already exists → {DEMO_EMAIL}")
    finally:
        db.close()


def main():
    create_tables()
    load_model()
    db = SessionLocal()

    try:
        # Create demo user
        existing = db.query(User).filter(User.email == DEMO_EMAIL).first()
        if existing:
            user = existing
            print(f"Demo user already exists (id={user.id})")
        else:
            user = User(
                email=DEMO_EMAIL,
                hashed_password=hash_password(DEMO_PASSWORD),
                full_name=DEMO_NAME,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"Created demo user: {DEMO_EMAIL} / {DEMO_PASSWORD}")

        # Delete existing seeded predictions for a clean slate
        db.query(Prediction).filter(Prediction.user_id == user.id).delete()
        db.commit()

        # Seed structured sample predictions
        now = datetime.now(timezone.utc)
        count = 0

        all_customers = SAMPLE_CUSTOMERS + [random_customer() for _ in range(94)]
        random.shuffle(all_customers)

        for i, customer in enumerate(all_customers):
            result = predict_single(customer)
            days_ago = random.randint(0, 180)
            created = now - timedelta(days=days_ago, hours=random.randint(0, 23))

            p = Prediction(
                user_id=user.id,
                customer_id=f"C-{uuid.uuid4().hex[:8].upper()}",
                input_data=json.dumps(customer),
                churn_probability=result["churn_probability"],
                churn_prediction=result["churn_prediction"],
                risk_level=result["risk_level"],
                shap_data=json.dumps(result.get("top_reasons", [])),
                source="single",
                created_at=created,
            )
            db.add(p)
            count += 1

        db.commit()
        print(f"Seeded {count} predictions for user {DEMO_EMAIL}")
        print("\nDemo credentials:")
        print(f"  Email   : {DEMO_EMAIL}")
        print(f"  Password: {DEMO_PASSWORD}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
