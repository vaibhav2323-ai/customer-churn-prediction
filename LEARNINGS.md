# What I Learned Building This Project

Honest notes on what was hard, what I'd do differently, and what I want to learn next.
Writing this partly for myself and partly because I keep seeing "what did you learn from this project?" in interview prep guides.

---

## What was hardest

### CORS + cross-origin cookies (lost the most time here)

I thought CORS was just "add a header that says allow this origin" and that would be it.
It's not.

When you have a frontend on one domain (Vercel) making credentialed requests to a backend on another domain (Render), you need everything lined up:

- `allow_credentials=True` in FastAPI
- The **exact** origin in `allow_origins` — you literally cannot use `*` with credentials, FastAPI throws an error if you try
- `SameSite=None` on the Set-Cookie header — the default is `Lax` which silently blocks cookies on cross-origin requests
- `Secure=True` on the cookie — browsers refuse to set `SameSite=None` cookies without this
- `withCredentials: true` in axios on the frontend

If any one of these is missing, the browser either blocks the request silently or drops the cookie without telling you. The browser console just says "Network Error" or "CORS error" with no detail about which of the five things is wrong.

I probably spent 8–10 hours total across multiple sessions debugging this.

### passlib breaking silently in production

Every FastAPI tutorial uses passlib for bcrypt. I used it too. It worked fine locally.

Then I deployed to Render and every login attempt failed with `ValueError: password cannot be longer than 72 bytes`. Even for passwords that were 9 characters long. The error is from bcrypt 4.x, which now enforces the 72-byte limit strictly instead of silently truncating. Passlib 1.7.4 (last updated 2019) doesn't handle this — it does some internal stuff that trips the check.

I wasted a whole day adding guards and validators before realising the fix was to just delete passlib and call bcrypt directly. Should have read the passlib GitHub issues before spending that much time.

Lesson: if a library is unmaintained for 5+ years, don't use it for anything security-critical.

### Understanding SHAP output shapes

The SHAP library is powerful but the API is confusing if you're using it for the first time.

For XGBoost binary classification, `TreeExplainer.shap_values()` returns a 2D numpy array of shape `(n_samples, n_features)`. But for RandomForest with sklearn, it returns a *list* of two arrays (one per class). I was getting the wrong shape because I copied code from a different model type and didn't notice.

Once I understood what I was looking at it made sense, but debugging wrong-shaped arrays is really frustrating.

Useful reference that actually explained it clearly: https://shap.readthedocs.io/en/latest/

### Docker non-root user + volume permissions

Security best practice is to run the app as a non-root user inside the container. This is fine until you add a Docker volume for SQLite — the volume directory is created as root and then your non-root user (uid 1001) can't write to it.

The fix is an entrypoint shell script that:
1. Runs as root
2. Creates the data directory
3. `chown`s it to uid 1001
4. Uses `gosu` to drop to uid 1001 and exec the actual command

It's the standard pattern but I didn't know about `gosu` before this and the errors when it's wrong aren't obvious.

---

## What I'd do differently

**PostgreSQL from day one.** SQLite is great for getting started and this app uses it fine since it's single-instance, but you can't run multiple workers, can't do horizontal scaling, and migrations are more awkward. If I was doing this again I'd set up Postgres in docker-compose from the start even though it feels like overkill for a side project.

**Proper logging from the start.** I only added real logging when I was debugging production failures and couldn't reproduce things locally. Should have had structured logging from the first commit — would have saved hours.

**Learn about cookies before writing auth.** I jumped into implementing JWT refresh tokens without fully understanding how cookies work cross-origin. Would have saved a lot of pain to read about SameSite, Secure, and HttpOnly before writing any auth code.

**Write tests as I go.** I have pytest set up but barely any actual tests. The CI pipeline catches CVEs and SAST issues but not functional bugs. A test for the login endpoint alone would have caught the passlib issue in CI before it hit production.

**Smaller scope, working end-to-end faster.** I tried to add refresh tokens, rate limiting, SHAP, batch predictions, Docker, and CI/CD all roughly at once. Should have gotten the simplest possible version working end-to-end (predict endpoint + one page frontend) then added features one at a time.

---

## What I want to learn next

**PostgreSQL + Alembic** — proper schema migrations instead of `create_all()` which can't handle column changes.

**React Query (TanStack Query)** — I rolled my own data fetching with useEffect and it's messy. React Query handles caching, loading states, and refetching way more cleanly.

**Model monitoring** — once a model is in production, how do you know when the data distribution has shifted and predictions are getting worse? Tools like Evidently AI or Arize look interesting.

**FastAPI background tasks / Celery** — for batch predictions I'm blocking the request thread doing synchronous ML inference. For large batches this should be async with a task queue.

**Testing ML code properly** — unit testing the model pipeline and not just the API is something I want to get better at.

**Kubernetes** — eventually. Docker Compose is fine for this scale but I want to understand how real services manage containers at scale.

---

## Things that surprised me

The ML part was actually the easiest part. Fitting an XGBoost model and computing SHAP values took maybe a day. The auth, CORS, Docker, deployment, and debugging took weeks.

SHAP explanations are genuinely useful. I was expecting them to be a checkbox thing ("look, explainability!") but when you actually look at the output it tells you real things — like that month-to-month contracts and electronic check payment are the biggest churn predictors. Makes intuitive sense.

Render's free tier cold starts are brutal. 30–60 seconds to wake up means anyone who hits the demo after a quiet period thinks the app is broken. Not much I can do about this without paying for a plan.

Reading the FastAPI source code is actually pretty approachable and I learned a lot about how Starlette (the underlying framework) works just from doing that.
