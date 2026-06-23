# ChurnGuard — Customer Churn Prediction Platform

AI-powered customer churn prediction with XGBoost, SHAP explanations, and a full-stack web interface.

## Features

- **ML Model** — XGBoost trained on synthetic Telco churn data; SHAP explainability; ROC-AUC comparison with Logistic Regression
- **Backend** — FastAPI + SQLite; JWT auth; single & batch prediction; dashboard analytics; rate limiting
- **Frontend** — React + Tailwind CSS; live charts (Recharts); SHAP waterfall; CSV batch upload/download
- **DevOps** — Docker Compose; GitHub Actions CI/CD

---

## Quick Start (Docker Compose)

```bash
# 1. Clone the repo
git clone <your-repo-url>
cd churnguard

# 2. Create environment file
cp .env.example .env
# Edit .env and set a strong SECRET_KEY

# 3. Start all services
docker compose up --build

# Frontend → http://localhost:3000
# Backend API → http://localhost:8000
# API Docs → http://localhost:8000/docs
```

**Demo login:** `demo@churnprediction.ai` / `Demo1234!`

---

## Local Development

### Backend

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt

# Train the ML model (first time only)
python -m ml.train

# Seed demo data
python -m scripts.seed

# Start the API server
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

### Frontend

```bash
cd frontend
npm install
npm run dev
```

App: http://localhost:5173

Vite's dev proxy forwards all API calls to `http://localhost:8000`.

---

## Project Structure

```
project/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, CORS, rate limiter
│   │   ├── config.py            # Pydantic settings
│   │   ├── database.py          # SQLAlchemy engine + session
│   │   ├── auth/                # JWT register / login
│   │   ├── predictions/         # /predict, /batch-predict, /history
│   │   ├── dashboard/           # /dashboard/stats
│   │   └── customers/           # /customers (latest prediction per ID)
│   ├── ml/
│   │   ├── train.py             # Generate data, train XGBoost + LR, save artefacts
│   │   ├── predict.py           # Load model, preprocess, infer, SHAP
│   │   └── models/              # Saved model artefacts (created by train.py)
│   ├── scripts/
│   │   └── seed.py              # Populate demo user + 100 predictions
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── pages/               # Dashboard, Predict, BatchUpload, History, Customers
│   │   ├── components/          # Navbar, RiskBadge, LoadingSpinner, ProtectedRoute
│   │   ├── context/AuthContext  # JWT auth state
│   │   └── utils/api.js         # Axios instance with auth interceptors
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
└── .github/workflows/ci-cd.yml
```

---

## API Reference

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/auth/register` | — | Create account |
| POST | `/auth/login` | — | Get JWT token |
| GET | `/auth/me` | JWT | Current user |
| POST | `/predictions/predict` | JWT | Single churn prediction + SHAP |
| POST | `/predictions/batch-predict` | JWT | CSV upload, up to 1,000 rows |
| GET | `/predictions/history` | JWT | Paginated prediction history |
| GET | `/dashboard/stats` | JWT | Aggregate stats + monthly trend |
| GET | `/customers` | JWT | Latest prediction per customer |
| GET | `/health` | — | Model health check |

---

## ML Model Details

| Metric | Value |
|--------|-------|
| Algorithm | XGBoost (vs Logistic Regression, best wins) |
| Dataset | Synthetic Telco Churn (7,043 samples, 19 features) |
| ROC-AUC | ~0.87 |
| Explainability | SHAP TreeExplainer |

**Risk tiers:**
- 🔴 **High** — probability ≥ 70%
- 🟡 **Medium** — 40% ≤ probability < 70%
- 🟢 **Low** — probability < 40%

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | *required* | JWT signing secret (≥32 chars) |
| `ALGORITHM` | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Token TTL |
| `DATABASE_URL` | `sqlite:///./churn.db` | SQLAlchemy DSN |
| `CORS_ORIGINS` | `http://localhost:3000,...` | Comma-separated allowed origins |
| `VITE_API_URL` | *(empty = proxy)* | Frontend API base URL |

---

## Deployment

### Production checklist

- [ ] Set a strong `SECRET_KEY` in `.env` (`openssl rand -hex 32`)
- [ ] Update `CORS_ORIGINS` to your actual frontend domain
- [ ] Replace SQLite with PostgreSQL for multi-instance deployments
- [ ] Point `VITE_API_URL` to your production API URL before building frontend
- [ ] Configure deploy secrets in GitHub Actions (`DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`)

### Deploy to any VPS

```bash
# On the server
mkdir /opt/churnguard && cd /opt/churnguard
# Copy docker-compose.yml and .env
docker compose up -d
```

### Deploy backend to Railway / Render

Set the start command to:
```
python -m ml.train && python -m scripts.seed && uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### Deploy frontend to Vercel / Netlify

```bash
cd frontend
npm run build
# Upload dist/ to your static host
# Set VITE_API_URL to your backend URL
```

---

## CSV Batch Upload Format

Required columns (case-sensitive):

```
gender, senior_citizen, partner, dependents, tenure,
phone_service, multiple_lines, internet_service,
online_security, online_backup, device_protection,
tech_support, streaming_tv, streaming_movies,
contract, paperless_billing, payment_method,
monthly_charges, total_charges
```

Download the template from the **Batch Upload** page in the app.

---

## License

MIT
