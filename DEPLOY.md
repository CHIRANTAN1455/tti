# Deploying to Render

This repo includes `render.yaml` at the root, so Render can deploy both the
backend (FastAPI) and frontend (React) from a single Blueprint. Two things
Render doesn't provide that you need to bring yourself: a MongoDB database
and a real Stripe secret key.

## 1. Push this repo to GitHub (or GitLab)

Render Blueprints deploy from a connected git repo — Render can't read a
local working directory. `backend/.env` and `frontend/.env` are already
gitignored, so no local secrets will be pushed.

## 2. Create a free MongoDB Atlas cluster

Render has no managed MongoDB. Go to [mongodb.com/atlas](https://www.mongodb.com/atlas),
create a free (M0) cluster, add a database user, and allow network access
from anywhere (`0.0.0.0/0`) — Render's IPs aren't static. Copy the connection
string; it looks like:

```
mongodb+srv://<user>:<password>@<cluster>.mongodb.net/?retryWrites=true&w=majority
```

## 3. Get a real Stripe secret key

The app ships with a placeholder `STRIPE_API_KEY` (`sk_test_emergent`) that
can't process real payments. Grab a real key (test or live) from your
[Stripe dashboard](https://dashboard.stripe.com/apikeys). While you're there,
once the backend is deployed, add a webhook endpoint pointing at
`https://<your-backend>.onrender.com/api/webhook/stripe` so payment
confirmations land immediately instead of waiting on the frontend's polling
fallback.

## 4. Deploy the Blueprint

1. In the Render dashboard: **New +** → **Blueprint**.
2. Connect the repo. Render finds `render.yaml` automatically and shows two
   services: `tti-backend` (Python web service) and `tti-frontend` (static
   site).
3. Render will prompt for every env var marked `sync: false` before it lets
   you deploy:
   - `MONGO_URL` — the Atlas connection string from step 2
   - `STRIPE_API_KEY` — the real key from step 3
   - `ADMIN_PASSWORD` — **set a real password.** The default in local dev is
     `1234`; that's fine on your laptop, not on a public URL.
4. Click **Apply**. Render builds both services — the backend runs `pip
   install` (with the extra index URL the private `emergentintegrations`
   package needs) then starts `uvicorn`; the frontend runs `yarn build` and
   serves the static output, rewriting all routes to `index.html` so React
   Router's client-side routing works.

## 5. Seed the database

The schema seeds itself, but the course catalog doesn't — nothing runs this
automatically on deploy. Once the backend is live, seed it once:

```bash
curl -X POST https://tti-backend.onrender.com/api/seed
```

This is destructive on courses (it deletes and re-inserts all 15), so only
run it again later if you're intentionally resetting the catalog — see the
"known limitations" note below.

## 6. Verify

- `https://tti-backend.onrender.com/api/health` → `{"status": "ok"}`
- `https://tti-frontend.onrender.com` loads the app, and course cards show
  real data (confirms the frontend is reaching the backend)
- Log in as the admin account (`ttl@admin.com` / whatever you set in step 3)
  and confirm the payment-bypass checkout still works

## About the predicted URLs

`render.yaml` hardcodes `CORS_ORIGINS` and `REACT_APP_BACKEND_URL` as
`https://tti-backend.onrender.com` / `https://tti-frontend.onrender.com` —
Render's default URL pattern for a service named `tti-backend` /
`tti-frontend`. If either name is already taken on your account, Render
appends a random suffix instead, and those two values will be wrong. If
that happens, open each service's **Environment** tab in the Render
dashboard and update the value to match the real assigned URL, then
manually redeploy.

## Known limitations to be aware of

- **Free tier spins down after inactivity.** The first request after a quiet
  period will be slow (cold start). Fine for a demo; upgrade the backend's
  `plan` in `render.yaml` before real usage.
- **Reseeding breaks existing progress.** `POST /api/seed` deletes and
  reinserts all courses with fresh IDs, which orphans any existing
  enrollments, quiz results, and certificates (they reference the old IDs).
  Only reseed a live database if you're prepared to lose user progress, or
  add cleanup logic first.
- **Course content was AI-researched, not clinically reviewed.** See the
  engagement brief — get a licensed practitioner's sign-off before this goes
  in front of real trainees.
