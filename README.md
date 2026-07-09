# PeopleOS — Zero-Chase Employee Experience Platform

> Nothing gets stuck. Nobody gets chased.

PeopleOS is a production-structured **modular monolith**: a React + TypeScript
frontend and a FastAPI backend over PostgreSQL, with private file storage.
State transitions automatically trigger the next unit of work, dashboards
surface what matters now, and managers receive decision context exactly where
they act.

---

## Demo


https://github.com/user-attachments/assets/086b0749-1705-4949-8c0d-09e638b305bd


A short screen recording walking through the app:


---

## Table of contents

- [Demo](#demo)
- [Quick start](#quick-start)
- [Architecture](#architecture)
  - [Frozen engineering contracts](#frozen-engineering-contracts)
- [Repository layout](#repository-layout)
- [Prerequisites](#prerequisites)
- [Environment variables](#environment-variables)
  - [Backend (`backend/.env`)](#backend-backendenv)
  - [Frontend (`frontend/.env`)](#frontend-frontendenv)
  - [Database (Supabase) setup](#database-supabase-setup)
- [Backend — setup & run](#backend--setup--run)
- [Frontend — setup & run](#frontend--setup--run)
- [Demo accounts](#demo-accounts)
  - [Testing different roles](#testing-different-roles)
- [Implemented workflows](#implemented-workflows-all-verified-e2e-against-a-live-db)
- [Running the tests](#running-the-tests)
- [Acceptance & RBAC tests](#acceptance--rbac-tests)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)
- [Notes](#notes)

---

## Quick start

TL;DR to get the whole app running locally, end to end. Assumes Python 3.11+,
Node 18+, and a reachable PostgreSQL database (local or Supabase).

```bash
# 1. Clone
git clone <your-repo-url> peopleos
cd peopleos

# 2. Backend: create a virtualenv and install deps
cd backend
python -m venv .venv
source .venv/bin/activate          # macOS/Linux
# .venv\Scripts\activate           # Windows (PowerShell/CMD)
pip install -r requirements.txt

# 3. Create your .env from the template
cp .env.example .env

# 4. Set DATABASE_URL in backend/.env
#    - local Postgres: postgresql+psycopg://postgres:postgres@localhost:5432/peopleos
#    - Supabase: use the connection POOLER string (see "Database (Supabase) setup")

# 5. Build the schema and load demo data (DROPS + recreates all tables)
python reset_db.py

# 6. Run the API (http://localhost:8000, docs at /docs)
uvicorn app.main:app --port 8000

# 7. Frontend (new terminal)
cd ../frontend
npm install
npm run dev                        # http://localhost:5173
```

Open <http://localhost:5173> and log in with any [demo account](#demo-accounts)
(password `Password123!`). The frontend talks to `http://localhost:8000` by
default, so no `frontend/.env` is required for local development.

---

## Architecture

```
React + TypeScript (Vite, Tailwind, TanStack Query, Axios)
        │  REST /api/v1
        ▼
FastAPI modular monolith (SQLAlchemy, Pydantic v2, python-jose, passlib)
  auth · employees · dashboard · leaves · requests_history · onboarding
  expenses · documents · notifications · audit · analytics
  + events dispatcher · shared notify/audit/storage · parse pipeline
        ▼
PostgreSQL (snake_case, UUID PKs, UTC)  +  private object storage
```

The backend mounts one router per module under the `/api/v1` prefix
(`auth`, `dashboard`, `employees`, `leaves`, `requests_history`, `onboarding`,
`expenses`, `documents`, `notifications`, `audit`, `analytics`) plus a
`GET /api/v1/health` liveness probe. CORS is configured from `CORS_ORIGINS`.

### Frozen engineering contracts
- API prefix `/api/v1`; DB snake_case; JSON camelCase (Pydantic `CamelModel`).
- Success envelope `{"data": ...}`; error envelope `{"error": {"code","message"}}`.
- Error mapping: 401 `UNAUTHENTICATED`, 403 `FORBIDDEN`, 404 `NOT_FOUND`,
  409 `CONFLICT`, 422 `VALIDATION`.
- Role ranks: `employee=1`, `manager=2`, `hr_admin=3`. **Role rank alone is never
  enough for scoped employee resources** — manager-chain authorization is enforced
  at the API layer.
- Access token 15 min (in memory on the client); refresh token 7 days, stored
  only as a SHA-256 hash server-side; logout revokes it.

---

## Repository layout

```
backend/
  app/
    core/        config, db, security (JWT + refresh), deps (RBAC + manager chain)
    events/      synchronous dispatcher + handlers
    shared/      models, responses (CamelModel + envelopes), notify, audit, storage
    parse/       extractor (pdfplumber/pytesseract), parser, rules  (no LLM)
    auth/ employees/ dashboard/ leaves/ requests_history/ onboarding/
    expenses/ documents/ notifications/ audit/ analytics/
    main.py
  schema.sql     complete schema (15 tables, generated tsvector, checks, indexes)
  seed.py        realistic demo data + two anomaly profiles
  reset_db.py    ONE-COMMAND rebuild + seed
  requirements.txt
  Dockerfile     includes tesseract-ocr + poppler-utils from the first build
  .env           your local secrets (gitignored — create from .env.example)
frontend/
  src/ app/ api/ components/ context/ pages/ lib/
```

> **Secrets & `.gitignore`.** A root `.gitignore` excludes `.env`, `__pycache__`,
> `.venv`, `backend/_storage/`, `node_modules`, and `dist`. **`.env` files are
> never committed** — real secrets live only in your local `backend/.env`. If you
> clone fresh, `backend/.env` will not exist; create it with
> `cp backend/.env.example backend/.env`.

---

## Prerequisites
- Python 3.11+, Node 18+, a PostgreSQL 14+ database (local, Docker, or Supabase).
- (Optional) Docker for a throwaway local Postgres:
  ```bash
  docker run -d --name peopleos-pg -e POSTGRES_PASSWORD=postgres \
    -e POSTGRES_DB=peopleos -p 5432:5432 postgres:16
  ```

---

## Environment variables

### Backend (`backend/.env`)

Copy `backend/.env.example` to `backend/.env` and fill in the values. All are
read by `app/core/config.py` (Pydantic settings).

| Variable | Required? | Default | Description |
|----------|-----------|---------|-------------|
| `DATABASE_URL` | **Yes** | `postgresql+psycopg://postgres:postgres@localhost:5432/peopleos` | SQLAlchemy connection URL. **Must use the `postgresql+psycopg://` prefix** (the app uses the psycopg driver). URL-encode special characters in the password (e.g. `@` → `%40`). |
| `JWT_SECRET` | **Yes** (in prod) | `dev-secret-change-me` | HMAC signing key for access/refresh tokens. Change this to a long random string outside local dev. |
| `JWT_ALGORITHM` | No | `HS256` | JWT signing algorithm. |
| `ACCESS_TTL` | No | `900` | Access-token lifetime in seconds (15 min). |
| `REFRESH_TTL` | No | `604800` | Refresh-token lifetime in seconds (7 days). |
| `SUPABASE_URL` | No | *(empty)* | Supabase project URL for private file storage. Blank ⇒ local `./_storage` dev fallback. |
| `SUPABASE_SERVICE_KEY` | No | *(empty)* | Supabase service-role key (server-side only). Required with `SUPABASE_URL` to enable the real bucket. |
| `SUPABASE_BUCKET` | No | `peopleos` | Name of the private storage bucket. |
| `CORS_ORIGINS` | No | `*` | Comma-separated list of allowed origins, or `*`. Set this to your frontend origin(s) in production. |

> Storage is only "configured" when **both** `SUPABASE_URL` and
> `SUPABASE_SERVICE_KEY` are set; otherwise the app writes to `backend/_storage/`
> and issues dev signed paths, so it runs locally with no external services.

### Frontend (`frontend/.env`)

`frontend/.env` is **optional for local development** — `frontend/src/lib/api.ts`
falls back to `http://localhost:8000` when `VITE_API_URL` is unset.

| Variable | Required? | Default | Description |
|----------|-----------|---------|-------------|
| `VITE_API_URL` | Only for deployment | `http://localhost:8000` | Base URL of the backend, **without** the `/api/v1` suffix (the client appends it). Set to your live backend URL when deploying. |

### Database (Supabase) setup

The database can run on [Supabase](https://supabase.com) Postgres. There are two
ways Supabase exposes the database, and the choice matters:

- **Direct connection** — `db.<project-ref>.supabase.co:5432`. This host is
  IPv6-first and frequently **hangs on IPv4-only networks** (many home/office
  ISPs and some CI runners). Avoid it unless you know your network has IPv6.
- **Connection pooler (recommended)** — `aws-<n>-<region>.pooler.supabase.com`.
  Works over IPv4 and is the reliable choice for this app.

**Get the pooler connection string:** in the Supabase dashboard go to
**Project Settings → Database → Connection pooling** and copy the connection
string. Note that with the pooler the **username has the project ref appended**
(`postgres.<project-ref>`), and there are two modes:

- **Transaction mode** — port **`6543`** (recommended default).
- **Session mode** — port **`5432`** on the pooler host (use if the transaction
  pooler gives you trouble with prepared statements).

Then build `DATABASE_URL` for `backend/.env`:

1. Start from the pooler string, e.g.
   `postgresql://postgres.<ref>:<password>@aws-1-ap-south-1.pooler.supabase.com:6543/postgres`.
2. **Change the prefix to `postgresql+psycopg://`** (the app uses the psycopg
   driver — plain `postgresql://` will not work).
3. **URL-encode special characters in the password.** For example a password
   `Puneeth@231245` becomes `Puneeth%40231245` (`@` → `%40`).

```env
DATABASE_URL=postgresql+psycopg://postgres.<ref>:<url-encoded-password>@aws-1-ap-south-1.pooler.supabase.com:6543/postgres
```

If the **transaction pooler** (port 6543) errors about **prepared statements**,
either append `?prepare_threshold=0` to the URL or switch to **session mode**
(port `5432` on the pooler host):

```env
# Disable prepared statements on the transaction pooler
DATABASE_URL=postgresql+psycopg://postgres.<ref>:<pwd>@aws-1-ap-south-1.pooler.supabase.com:6543/postgres?prepare_threshold=0

# ...or use session mode (port 5432 on the pooler host)
DATABASE_URL=postgresql+psycopg://postgres.<ref>:<pwd>@aws-1-ap-south-1.pooler.supabase.com:5432/postgres
```

Once `DATABASE_URL` is set, run `python reset_db.py`.

> ⚠️ **`reset_db.py` DROPS and recreates all tables**, then loads seed data.
> Running it against a database with real data will destroy it. It is intended
> for first-time setup and clean re-seeds only.

---

## Backend — setup & run
```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # macOS/Linux
# .venv\Scripts\activate           # Windows
pip install -r requirements.txt

cp .env.example .env               # then edit DATABASE_URL, JWT_SECRET, etc.

# ONE-COMMAND schema rebuild + seed (DROPS all tables first):
python reset_db.py

uvicorn app.main:app --port 8000   # API at :8000, interactive docs at /docs
```

## Frontend — setup & run
```bash
cd frontend
npm install
npm run dev      # dev server on :5173
npm run build    # production build (tsc -b + vite build)
npm run preview  # preview the production build locally
```

---

## Demo accounts (password `Password123!` for all)

| Login                    | Role      | Notes                                   |
|--------------------------|-----------|-----------------------------------------|
| `hr@peopleos.dev`        | hr_admin  | People ops, finance, audit, policies    |
| `manager1@peopleos.dev`  | manager   | Engineering; manages `employee@`, `eng*`|
| `manager2@peopleos.dev`  | manager   | Sales; out-of-chain for Eng reports     |
| `employee@peopleos.dev`  | employee  | Reports to `manager1`; Anomaly Profile A (Mon/Fri WFH cluster) |
| `newhire@peopleos.dev`   | employee  | status=onboarding (live onboarding run) |
| `eng1@peopleos.dev`      | employee  | Anomaly Profile B (frequent sick leave) |

New employees created through HR get the temporary password `Welcome@123`.

### Testing different roles

The session lives in a refresh token stored in `localStorage` under the key
`peopleos.refreshToken` (the access token is kept in memory). To explore the app
as different roles:

- **Sequentially:** log out and log back in with another account. A fresh login
  replaces the token and reshapes the whole UI for that role.
- **Simultaneously:** open each account in a **separate incognito / private
  window** (or a different browser). Because the session is per-`localStorage`,
  each window holds its own role session, so you can watch a manager approve a
  request that an employee just submitted, side by side.

---

## Implemented workflows (all verified E2E against a live DB)

- **Auth + RBAC + manager chain** — JWT access/refresh, hashed+revocable refresh
  tokens, server-side role guards, manager-chain resource authorization.
- **Contextual dashboards** — role-shaped `/dashboard` (employee, manager,
  new-hire, HR) with hero / needsAttention / waitingOnOthers(+ageDays) /
  upcoming / recentChanges / quickActions zones.
- **Leave + WFH** — one shared request flow; transactional balance settlement
  (`SELECT … FOR UPDATE`), pending reservation, overdraw prevention; **WFH never
  touches leave balances**; team-overlap warnings; approval queue.
- **Event-driven onboarding** — creating an employee auto-creates the run +
  sequential tasks (locked → unlocked → in_progress → done), notifies owners and
  the new hire; completing a task unlocks the next; locked completion → 409.
- **Expense + Smart Receipt Auto-Fill** — drag a PDF receipt → deterministic
  parse (amount/date/category) → editable, highlighted fields → explicit confirm
  (auto-fill never auto-submits). Threshold routing: `< ₹10,000` manager → paid;
  `≥ ₹10,000` manager → pending_finance → HR → paid. Private, signed short-lived
  receipt access; finance CSV export.
- **Approval History Context Panel** — `RequestHistoryPanel` renders inline in
  the manager approval card (6-month history, totals, balances, team overlap,
  anomaly flags), preloaded by notification deep links.
- **Secure Document Hub** — permission-scoped listing/search
  (`websearch_to_tsquery`, no leakage), signed short-lived downloads (never a
  public URL), policy versioning + change summaries + role-targeted publish
  notifications, acknowledgement tracking + HR CSV export.
- **Notification centre** — DB-backed, 10-second polling, unread badge, type
  filters, mark-read / read-all, and deep links that never dead-end (leave →
  approval card with history preloaded; policy → documents; expense → timeline).
- **Audit** — every sensitive state transition and document/receipt access is
  recorded; HR-only audit viewer + CSV export.

### Parsing pipeline
PDF text via **pdfplumber** (mandatory); image OCR via **pytesseract** (optional,
degrades gracefully). Extraction is fully **deterministic** — regex + keyword
maps + scoring. **No LLM** is used anywhere in parsing.

---

## Running the tests

The acceptance/RBAC suite exercises the API end to end against a **running server
on a freshly seeded database**. There is no separate unit-test framework wired in;
the checks in [Acceptance & RBAC tests](#acceptance--rbac-tests) are validated
against the live API.

To run them yourself:

```bash
# 1. Reseed a clean database
cd backend
source .venv/bin/activate
python reset_db.py

# 2. Start the API in one terminal
uvicorn app.main:app --port 8000

# 3. Exercise the flows against the running server, e.g.
curl http://localhost:8000/api/v1/health          # -> {"data":{"status":"ok"}}
```

> If a runnable acceptance script (e.g. `backend/_acceptance.py`) is present in
> your checkout, run it with the server up: `python _acceptance.py`. It is not
> part of the base repository, so the manual steps above are the fallback.

---

## Acceptance & RBAC tests

The full mandatory suite (Plan §22) passes **26/26** against the live server on a
freshly seeded DB, including:

- invalid access token → 401; refresh → new access → original request succeeds;
  logout → old refresh rejected 401
- employee approves leave → 403; own-request approval → 403; out-of-chain
  manager → 403; in-chain manager → 200 (balance settles); WFH approval leaves
  balance unchanged; overdraw → 409
- manager → `/analytics`, `/audit`, expense `finance-approve` → 403
- expense `< ₹10,000` paid after manager; `≥ ₹10,000` requires HR finance
- HR creates employee → onboarding run + tasks auto-created
- employee → another employee's history → 403; manager → report's history → 200
- employee → another employee's payslip download → 403; owner → signed URL
- audit captures sensitive actions; audit CSV export HR-only

---

## Deployment

The reference deployment matches the problem statement: **Railway** for the
backend, **Vercel** for the frontend, and **Supabase** for the database + private
file storage.

**Backend (Railway)**
- Deploy from `backend/` using the provided `Dockerfile` (it installs
  `tesseract-ocr` + `poppler-utils` so OCR works in the image). The container
  runs `uvicorn app.main:app` on `$PORT`.
- Set environment variables:
  - `DATABASE_URL` — the Supabase **pooler** URL with the `postgresql+psycopg://`
    prefix and URL-encoded password (see
    [Database (Supabase) setup](#database-supabase-setup)).
  - `JWT_SECRET` — a long random string.
  - `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_BUCKET` — for the private
    storage bucket + short-lived signed URLs.
  - `CORS_ORIGINS` — your Vercel frontend origin(s), comma-separated.

**Frontend (Vercel)**
- Build command `npm run build`, output `dist/`.
- Set `VITE_API_URL` to the live backend URL **without** the `/api/v1` suffix
  (the client appends it), e.g. `https://your-app.up.railway.app`.

**Database & storage (Supabase)**
- Run `python reset_db.py` once against the Supabase database to create the
  schema + seed data. Create the private storage bucket named to match
  `SUPABASE_BUCKET`.

---

## Troubleshooting

| Symptom | Likely cause & fix |
|---------|--------------------|
| `ModuleNotFoundError: No module named 'fastapi'` (or similar) | The virtualenv isn't activated or deps aren't installed. Run `source .venv/bin/activate` (Windows: `.venv\Scripts\activate`), then `pip install -r requirements.txt`. |
| `python reset_db.py` / `uvicorn` **hangs** connecting to Supabase | You're using the **direct** host `db.<ref>.supabase.co:5432`, which is IPv6-first and stalls on IPv4-only networks. Switch to the **connection pooler** host `aws-<n>-<region>.pooler.supabase.com:6543`. |
| Auth to Postgres fails with a password containing `@` | The `@` (or other special chars) must be **URL-encoded** in `DATABASE_URL` — `@` → `%40`, `#` → `%23`, `:` → `%3A`, etc. |
| Driver / dialect error, or connection refused despite a correct string | The URL prefix is wrong. It must be **`postgresql+psycopg://`**, not plain `postgresql://`. |
| Error mentioning **prepared statements** on Supabase | You're on the **transaction pooler** (port 6543). Append `?prepare_threshold=0` to `DATABASE_URL`, or use **session mode** (port `5432` on the pooler host). |
| Frontend requests blocked with a **CORS** error in the browser console | Set `CORS_ORIGINS` in `backend/.env` to include your frontend origin (e.g. `http://localhost:5173` or your Vercel URL), then restart the backend. |
| Frontend calls the wrong backend | For deployment set `VITE_API_URL` to the backend base URL **without** `/api/v1`. Locally it defaults to `http://localhost:8000`. |
| Table/data missing after deploy | Run `python reset_db.py` against the target database (remember: it **drops and recreates** all tables). |

---

## Notes
- The storage helper falls back to a local `./_storage` directory and dev signed
  paths when Supabase env vars are absent, so the app is fully runnable locally
  without external services. In production, set the `SUPABASE_*` vars for a
  private bucket with short-lived signed URLs.
- `docker build` of `backend/Dockerfile` installs `tesseract-ocr` and
  `poppler-utils` so OCR works in the deployed image.
- `.env` files are **gitignored** and must never be committed — secrets live only
  in `backend/.env`.
