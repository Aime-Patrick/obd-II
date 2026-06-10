<p align="center">
  <img src="assets/logo.png" alt="SmartDriveX logo" width="120">
</p>

# SmartDriveX API

FastAPI backend for **SmartDriveX** — OBD-II vehicle health diagnostics, ML fault classification, maintenance recommendations, and admin ML operations.

Pairs with:

- **Mobile app** (separate repo) — Flutter client, Bluetooth OBD-II, JWT auth
- **Admin dashboard** (separate repo) — analytics, retrain controls, settings

Default port: **8001**

---

## Features

| Area | Capability |
|------|------------|
| **Auth** | User register/login (JWT), password reset via email OTP |
| **Vehicles** | CRUD per user |
| **Diagnostics** | Rule-based sensor analysis + Gradient Boosting ML, recommendations, email reports |
| **Trends** | Per-vehicle sensor history (last 30 scans) |
| **Labeling** | Users confirm fault/healthy — feeds retrain pipeline |
| **Admin** | Dashboard stats, fault/label trends, model info, manual retrain, rollback, audit history |
| **ML ops** | Quality gates, metric comparison before promote, hot-swap model reload, scheduled retrain |

---

## Architecture

```text
Flutter app  ──Bluetooth──►  ELM327 OBD-II adapter
     │
     │  HTTPS + JWT
     ▼
FastAPI (main.py)
     ├── routes/auth, vehicles, diagnostics
     ├── routes/predict          (deprecated → 410 Gone)
     ├── routes/admin_auth       (admin JWT login)
     └── routes/admin            (dashboard APIs)
              │
              ├── services/ml_model.py      inference + hot reload
              ├── services/retrain_service.py background training job
              ├── services/scheduler_service.py  daily scheduled retrain check
              ├── services/recommendation_engine.py
              └── services/sensor_analyzer.py
     │
     ▼
MongoDB Atlas
     collections: users, vehicles, diagnostics, admin_users,
                  admin_api_keys, system_settings, retrain_history, password_resets
```

**Diagnostic flow** (`POST /diagnostics`):

1. Validate vehicle ownership and non-zero sensor payload
2. **SensorAnalyzer** — threshold rules from `rules/fault_rules.json`
3. **ml_model** — Gradient Boosting prediction + confidence
4. Fuse signals → severity (`HEALTHY` / `CAUTION` / `WARNING` / `CRITICAL`)
5. **RecommendationEngine** — plain-language actions
6. Persist to MongoDB; optional email in background

**Retrain flow** (`POST /admin/retrain`):

1. Eligibility gates (min labeled samples, min per class)
2. Backup current `ml/obd_model.joblib`
3. Subprocess: `ml/collect_real_data.py` → `ml/train_model.py`
4. Compare F1 / ROC-AUC vs previous model
5. Promote (hot reload) or restore backup + audit log in `retrain_history`

---

## Project structure

```text
backend/
├── main.py                 # App entry, startup hooks, CORS
├── config/
│   ├── settings.py         # Pydantic settings from .env
│   └── database.py         # Motor client + connect retry
├── auth/                   # JWT, passwords, admin access
├── routes/                 # HTTP routers
├── models/                 # Pydantic request/response schemas
├── services/               # Business logic
├── ml/
│   ├── train_model.py      # Train Gradient Boosting, save joblib
│   ├── collect_real_data.py # Export labeled MongoDB rows for retrain
│   └── cleaned_data.csv    # Base training dataset (~70k rows)
├── rules/fault_rules.json  # Sensor threshold rules
├── Dockerfile
├── docker-compose.yml
└── startup.sh              # Local dev: install, train if missing, run uvicorn
```

---

## Requirements

- Python **3.11+**
- MongoDB (**Atlas** or local)
- Optional: Docker Desktop (for containerised run)

---

## Quick start

### 1. Environment

```bash
cp .env.example .env
# Edit .env — at minimum: MONGODB_URL, DATABASE_NAME, JWT_SECRET, ADMIN_PASSWORD
```

### 2. Local (recommended for development)

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt

# Train model if obd_model.joblib is missing
python ml/train_model.py

uvicorn main:app --reload --host 0.0.0.0 --port 8001
```

Or use the helper script:

```bash
bash startup.sh
```

### 3. Docker

```bash
cd backend
docker compose up --build
```

The image runs `train_model.py` at **build time** so the bundled scikit-learn/numpy versions match the saved `.joblib` artifact.

**Health check:** `GET http://localhost:8001/health`

**Interactive docs:** `http://localhost:8001/docs`

### 4. Admin dashboard

Point the Next.js admin app at this API:

```env
# admin-dashboard/.env.local
NEXT_PUBLIC_API_URL=http://localhost:8001
```

On first startup, if `admin_users` is empty, an admin account is seeded from `ADMIN_EMAIL` / `ADMIN_PASSWORD` in `.env`. Sign in at `/login` on the dashboard.

---

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MONGODB_URL` | Yes | — | MongoDB connection string (Atlas SRV or `mongodb://`) |
| `DATABASE_NAME` | Yes | — | Database name |
| `JWT_SECRET` | Yes | — | Secret for user + admin JWT signing |
| `JWT_ALGORITHM` | No | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | `30` | Mobile user token lifetime |
| `PORT` | No | `8001` | HTTP port |
| `ADMIN_EMAIL` | No | `admin@smartdrivex.com` | Seeded admin login email |
| `ADMIN_PASSWORD` | Yes* | — | Seeded admin password (*required on first boot) |
| `ADMIN_ACCESS_TOKEN_EXPIRE_MINUTES` | No | `480` | Admin JWT lifetime |
| `ADMIN_API_KEY` / `ADMIN_BOOTSTRAP_KEY` | No | — | Optional legacy API key bootstrap |
| `MIN_LABELED_SAMPLES` | No | `50` | Retrain gate: total labels |
| `MIN_LABELS_PER_CLASS` | No | `5` | Retrain gate: fault + healthy each |
| `METRIC_TOLERANCE` | No | `0.005` | Max allowed F1 regression on promote |
| `SCHEDULE_RETRAIN_ENABLED` | No | `false` | Enable APScheduler retrain job |
| `SCHEDULE_RETRAIN_INTERVAL_DAYS` | No | `7` | Days between scheduled retrains |
| `MAIL_*` | No | — | SMTP for welcome, diagnostic, reset emails |

Retrain thresholds can also be changed at runtime via `PATCH /admin/settings/retrain` (stored in MongoDB `system_settings`).

---

## API reference

### Public / legacy

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/` | — | API info |
| `GET` | `/health` | — | Health + loaded model version/metrics |
| `GET` | `/app/version` | — | Mobile OTA check (`platform`, `current_version`, `current_build`) |
| `GET` | `/releases/{file}` | — | Static APK hosting (upload to `backend/releases/`) |
| `POST` | `/predict` | — | **Removed** — returns 410; use `/diagnostics` |

### Mobile (Bearer JWT)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/auth/register` | Create account |
| `POST` | `/auth/login` | Get access token |
| `POST` | `/auth/forgot-password` | Send reset OTP email |
| `POST` | `/auth/verify-otp` | Validate OTP |
| `POST` | `/auth/reset-password` | Set new password |
| `GET` | `/auth/me` | Current user profile |
| `GET` / `POST` | `/vehicles` | List / add vehicles |
| `GET` / `PUT` / `DELETE` | `/vehicles/{id}` | Vehicle detail / update / delete |
| `POST` | `/diagnostics` | Run full diagnostic (rules + ML + recommendations) |
| `GET` | `/diagnostics` | List diagnostics (`?vehicle_id=` optional) |
| `GET` | `/diagnostics/{id}` | Single diagnostic |
| `GET` | `/diagnostics/trends/{vehicle_id}` | Sensor time-series (last 30) |
| `PATCH` | `/diagnostics/{id}/label` | User label for retraining |

**Auth header:** `Authorization: Bearer <token>`

### Admin (Bearer admin JWT or `X-Admin-API-Key`)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/admin/auth/login` | Admin dashboard login |
| `GET` | `/admin/stats` | Overview counters |
| `GET` | `/admin/trends/faults` | Daily fault trend (30 days) |
| `GET` | `/admin/trends/severity` | Severity breakdown |
| `GET` | `/admin/trends/labels` | Weekly user labels (12 weeks) |
| `GET` | `/admin/sensors/heatmap` | Top abnormal sensors |
| `GET` | `/admin/labels/summary` | Label coverage + retrain eligibility |
| `GET` | `/admin/model` | Production model metadata + metrics |
| `GET` | `/admin/retrain/eligibility` | Pre-flight retrain check |
| `POST` | `/admin/retrain` | Start background retrain |
| `GET` | `/admin/retrain/status` | Job progress |
| `GET` | `/admin/retrain/history` | Audit timeline |
| `POST` | `/admin/retrain/rollback` | Restore previous model |
| `GET` / `PATCH` | `/admin/settings/retrain` | Thresholds + schedule |
| `GET` / `PATCH` | `/admin/settings/app-release` | Android OTA version + APK URL |
| `POST` | `/admin/settings/app-release/upload` | Upload APK to `backend/releases/` (admin auth) |
| `GET` / `POST` | `/admin/keys` | Admin API key management |

---

## Machine learning

| Artifact | Path |
|----------|------|
| Trained model | `ml/obd_model.joblib` |
| Feature metadata | `model_metadata.json` |
| Test metrics | `ml/training_metrics.json` |
| Previous backup | `ml/obd_model.previous.joblib` |

**Classifier:** `GradientBoostingClassifier` in a `StandardScaler` pipeline.

**Train from scratch:**

```bash
python ml/train_model.py
```

**Compare candidate classifiers** (thesis Table 5.5:1 — Decision Tree, RF, SVM, GBM):

```bash
# Requires cleaned_data.csv (generate from ../archive if missing)
python ml/preprocess_data.py
python ml/compare_models.py
```

Outputs: `ml/model_comparison.json`, `.csv`, `.md`, `figure_5_5_model_comparison.png`.

**Retrain with user labels** (via admin UI or API):

```bash
# Exports labeled diagnostics from MongoDB, merges with base CSV, retrains
python ml/collect_real_data.py
```

The admin retrain endpoint runs this pipeline in a background thread with promote/rollback gates.

**Scheduled retrain:** APScheduler checks daily at **03:00 UTC**. Runs only when enabled, interval elapsed, new labels exist, and gates pass.

**Reload without restart:** `ml_model.reload()` after a successful promote.

---

## MongoDB collections

| Collection | Purpose |
|------------|---------|
| `users` | Mobile accounts |
| `vehicles` | Per-user vehicle profiles |
| `diagnostics` | Scan results, `user_label`, `labeled_at`, `model_version` |
| `password_resets` | OTP records |
| `admin_users` | Dashboard login |
| `admin_api_keys` | Hashed API keys (optional) |
| `system_settings` | Retrain thresholds + schedule (`_id: "retrain"`) |
| `retrain_history` | Retrain/rollback audit log |

---

## Development

```bash
# Regenerate thesis figures (learning curve, confusion matrix, model comparison)
python ml/generate_figures.py
python ml/compare_models.py

# Explore dataset
python ml/explore_data.py
```

**Recommendation engine details:** see [RECOMMENDATION_ENGINE.md](./RECOMMENDATION_ENGINE.md).

**System design (PDF):** `../docs/SmartDriveX_System_Design.pdf`

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `lookup registry-1.docker.io: no such host` | Docker DNS glitch — restart Docker Desktop, `docker pull python:3.11-slim`, retry build |
| MongoDB SRV DNS on first Docker start | Built-in retry in `connect_to_mongo()` (5×, 2s); wait or restart container |
| `MT19937 is not a known BitGenerator` | Model trained on different numpy — rerun `python ml/train_model.py` or rebuild Docker image |
| Admin dashboard "Backend offline" | Confirm API on `:8001`, `NEXT_PUBLIC_API_URL` matches, restart Next.js after `.env.local` change |
| Retrain rejected | New model F1/ROC-AUC worse than current — check `/admin/retrain/status` and history |
| No emails | Configure `MAIL_*` in `.env`; Gmail needs an app password |

---

## Production checklist

- [ ] Set a strong `JWT_SECRET` (not the dev default)
- [ ] Change `ADMIN_PASSWORD` after first login
- [ ] Restrict CORS in `main.py` to your app origins
- [ ] Use MongoDB Atlas IP allowlist + least-privilege DB user
- [ ] Store secrets in env / secret manager — never commit `.env`

---

## License

Academic / project use — University of Rwanda (UR) final-year project, 2025–2026.
