# Customer Churn Prediction

A full-stack ML web app I built to learn full-stack ML deployment. You give it a telecom customer's details and it tells you how likely they are to cancel their subscription, plus *why* (using SHAP values).

**Live demo:** https://customer-churn-prediction-dun.vercel.app  
Login: `demo@churnprediction.ai` / `Demo1234!`

Backend: https://customer-churn-prediction-w9zi.onrender.com

---

## Why I built this

I'd done the Kaggle Telco churn dataset in a notebook before but I wanted to actually *deploy* something — a real app that other people could use, not just a `.ipynb` file that only works on my laptop.

Goals I set for myself:
- Serve an ML model through a proper REST API
- Build a frontend that doesn't look terrible
- Figure out JWT auth (I didn't really understand it before this)
- Get it running on the cloud with CI/CD

It took way longer than I thought. Mostly because of CORS. More on that below.

---

## What it does

- Enter customer info → get churn probability + SHAP explanation of the top factors
- Upload a CSV → batch predict for hundreds of customers at once
- Dashboard with charts of your prediction history over time
- Accounts system with login/logout (JWT + httpOnly refresh cookie)

---

## Tech stack

- **ML:** XGBoost vs Logistic Regression — trains both, picks whichever has better ROC-AUC
- **Explainability:** SHAP TreeExplainer (learned about this from the original paper — really cool)
- **Backend:** FastAPI + SQLite + SQLAlchemy
- **Frontend:** React 18 + Vite + Tailwind CSS + Recharts
- **Auth:** JWT access tokens (15 min) + httpOnly refresh cookie (7 days, rotated on use)
- **Infra:** Docker, GitHub Actions CI/CD, Render (backend), Vercel (frontend)

---

## Running it locally

### Backend

```bash
cd backend

python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

pip install -r requirements.txt

# train the model first — creates a models/ folder with .pkl files
python -m ml.train

# seed the demo user + some sample predictions
python -m scripts.seed

# start the API
uvicorn app.main:app --reload --port 8000
```

API docs (Swagger UI): http://localhost:8000/docs

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Opens at http://localhost:5173. Vite proxies `/auth`, `/predictions`, etc. to port 8000 automatically so you don't need to touch CORS in dev.

---

## Project layout

```
project/
├── backend/
│   ├── app/
│   │   ├── auth/           # register, login, JWT, refresh tokens, brute-force lockout
│   │   ├── predictions/    # /predict, /batch-predict, /history
│   │   ├── dashboard/      # aggregate stats for the charts
│   │   ├── customers/      # customer list (latest prediction per ID)
│   │   ├── config.py       # env var settings (Pydantic BaseSettings)
│   │   └── main.py         # app entry point, CORS, middleware
│   ├── ml/
│   │   ├── train.py        # generate data, train models, save artifacts
│   │   └── predict.py      # load model, preprocess input, run inference + SHAP
│   └── scripts/seed.py     # creates demo user + 100 sample predictions
├── frontend/
│   └── src/
│       ├── pages/          # Dashboard, Predict, BatchUpload, History, Customers
│       ├── context/        # AuthContext (JWT state)
│       └── utils/api.js    # axios with automatic token refresh on 401
├── docker-compose.yml
├── render.yaml             # Render deployment config
└── .github/workflows/      # CI: gitleaks, bandit, pip-audit, npm audit, pytest, Trivy
```

---

## Struggles I ran into

**CORS was genuinely horrible.** Frontend on Vercel, backend on Render — browser kept blocking requests with zero useful error messages. Turns out for cross-origin requests with credentials you need ALL of:
1. Exact origin in `allow_origins` (wildcards break with `allow_credentials=True`)
2. `SameSite=None` on the cookie (default `Lax` silently blocks cross-origin cookie sends)
3. `Secure=True` on the cookie (browsers refuse `SameSite=None` without this)
4. `withCredentials: true` in axios

Miss any one of these and it silently fails. Took me way too long.

**passlib crashed in production.** I started with passlib for bcrypt (it's in every FastAPI tutorial) but it's unmaintained and crashes with bcrypt 4.x — threw `ValueError: password cannot be longer than 72 bytes` even for 9-character passwords. Spent a whole day debugging before I just ripped it out and called bcrypt directly.

**Docker volume permissions.** Running as a non-root user inside the container is good practice, but then the volume mount is owned by root and the app can't write to it. Fix is an entrypoint script that runs as root to `chown` the volume then drops to uid 1001 with `gosu`. Annoying but it works.

---

## What I learned

- **SHAP values** actually make sense now. The TreeExplainer is really fast for tree-based models and the outputs are genuinely useful for understanding predictions — not just a gimmick
- **JWT refresh token rotation** is more complex than tutorials make it seem. I implemented the full flow: short-lived access token in memory, long-lived refresh token in httpOnly cookie, rotate on every use, revoke on logout
- **Timing attacks** are real and preventing user enumeration through login response times is an actual thing you have to think about
- **CI/CD** with GitHub Actions is actually not that bad once you get past the YAML syntax. I have secret scanning, Python SAST, dependency CVE checks, and Docker image scanning all running automatically
- Deploying a real app is like 80% config/infra problems and 20% actual code

---

## API endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/auth/register` | — | Create account |
| POST | `/auth/login` | — | Login, returns JWT |
| POST | `/auth/refresh` | cookie | Refresh access token |
| POST | `/predictions/predict` | JWT | Single prediction + SHAP |
| POST | `/predictions/batch-predict` | JWT | CSV upload, up to 1000 rows |
| GET | `/predictions/history` | JWT | Paginated prediction history |
| GET | `/dashboard/stats` | JWT | Aggregate stats + monthly trend |
| GET | `/customers` | JWT | Latest prediction per customer ID |
| GET | `/health` | — | Health check |

---

## Model performance

Trained on 7,043 synthetic samples (same structure as Kaggle Telco Churn dataset):

| Metric | Value |
|--------|-------|
| Algorithm | XGBoost (consistently beats LR on this dataset) |
| ROC-AUC | ~0.87 |
| Features | 19 customer attributes |

Risk tiers: High ≥ 70% · Medium 40–70% · Low < 40%

---

## Deployment notes

Backend is on Render free tier — it spins down after 15 min of inactivity so the first request after a while will be slow (30–60s cold start). That's a Render free plan thing, not a bug.

For your own deployment, set these env vars on Render:
```
SECRET_KEY=<openssl rand -hex 32>
REFRESH_SECRET_KEY=<different key>
CORS_ORIGINS=https://your-frontend.vercel.app
COOKIE_SECURE=true
COOKIE_SAMESITE=none
ENVIRONMENT=production
```

And on Vercel:
```
VITE_API_URL=https://your-backend.onrender.com
```

---

## License

MIT. Use it however, just don't blame me if it breaks :)
