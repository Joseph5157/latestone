# Power Plant Monitoring — Setup & Operator Guide

## What this is

A web dashboard for monitoring 30 power plants, their transformers and
devices, across 8 electrical metrics (temperature, voltage, current, active
power, reactive power, power factor, frequency, energy). It runs on your own
PC: a local PostgreSQL database plus a Python web application you open in
your browser.

## Prerequisites

Install these two things before anything else:

- **Python 3.11 or newer** — https://www.python.org/downloads/
- **Docker Desktop** (includes Docker Compose) — https://www.docker.com/products/docker-desktop/

You'll also need **git** to download the project, or you can download it as
a ZIP from GitHub instead.

## Installation

Run these steps once, in order, from the project folder.

**1. Get the project**

```bash
git clone https://github.com/Joseph5157/powerplant-dashboard-client.git
cd powerplant-dashboard-client
```

**2. Create your local settings file**

```bash
cp .env.example .env
```
Windows PowerShell: `copy .env.example .env`

The defaults in this file are ready to use as-is for local use — including
demo login credentials (see step 7).

**3. Install Python dependencies**

```bash
python -m venv .venv
pip install -r requirements.txt
```
Activate the virtual environment first:
- Windows: `.venv\Scripts\activate`
- Mac/Linux: `source .venv/bin/activate`

**4. Start the database**

```bash
docker compose up -d postgres
```
This starts an **empty** local PostgreSQL container (Docker Desktop must be
running first). It takes a few seconds on first run and creates no tables —
step 5 does that. Leave off `postgres` if you also want pgAdmin, which is
optional and appears on http://localhost:5050.

**5. Build the database schema**

```bash
alembic upgrade head
```
Creates the schema and applies every migration. This is the only thing that
defines the database structure — you never need `alembic stamp` on a fresh
database. Re-running it when you are already up to date does nothing.

**6. Load the sample data**

```bash
python -m db.seed_plant_monitoring --reset
python -m db.seed_admin_demo --reset
```
The first loads 30 days of readings (~1.38 million rows) across 30 plants, 71
transformers and 120 devices, and takes about 30 seconds. The second adds the
administration demo: 5 technicians, with 96 of the 120 devices assigned and 24
left unassigned so the Administrator screens have something to show.

Readings are timestamped relative to **when you run the seed**, so a database
seeded days ago will show its data as stale. Re-run the first command to
refresh it.

**7. Run the dashboard**

```bash
python app.py
```
Open **http://127.0.0.1:8050** in your browser and log in. (On Windows,
`localhost` also works but adds about 0.2–0.3 s to every request: it tries
IPv6 first and the dev server listens on IPv4.)

- Username: `admin`
- Password: `demo1234`

These are placeholder credentials for local use. To change them, edit
`DEMO_USERNAME` / `DEMO_PASSWORD` in `.env` — there is no fallback, so if
they are ever unset, login is refused entirely.

### Signing in as the other roles

`admin` is an Administrator. To sign in as a Technician or a General User, seed
those identities and give them a password:

```bash
python -m db.seed_admin_demo       # demo.tech01..05   (technician)
python -m db.seed_demo_personas    # demo.general01    (general)
```

then add logins for them in `.env`:

```
DEMO_CREDENTIALS={"demo.tech01": "tech1234", "demo.general01": "general1234"}
```

It is a JSON object so a password can contain any character — commas and
colons included — and still have exactly one reading.

**The password does not decide the role — the user row does.** `DEMO_CREDENTIALS`
says who may sign in; `plant_monitoring.users` says who they are and what they
may do. A credential naming a username that has no row is refused, so adding an
entry can never invent a user or grant a permission.

A malformed, non-string or repeated entry refuses *every* login rather than
some, which is deliberate — see `.env.example`. If all logins suddenly fail,
check the application log: it names the offending entry and why, without
printing any secret or the configuration value itself.

## Everyday use

Once installed, you don't repeat the full setup — just:

```bash
docker compose up -d postgres   # start the database (if not already running)
.venv\Scripts\activate          # Windows — or: source .venv/bin/activate
python app.py
```

To stop: `Ctrl+C` in the terminal running the app. The database container
can keep running in the background, or stop it with `docker compose stop`.

## Using the dashboard

Navigation drills down through the plant hierarchy:

**Plants overview** → click a plant → **Plant detail** (its transformers) →
click a transformer → **Transformer detail** (its devices) → click a device
→ **Device dashboard**.

The device dashboard is the main operator view:

- **Equipment context bar** — which plant, transformer and device you're
  looking at, and its status.
- **8-metric snapshot strip** — one tile per metric with its current value;
  click a tile to focus that metric below.
- **Metric selector + period filter** — switch metrics, and choose 24h / 7d
  / 30d / a custom date range.
- **KPI row** — current / minimum / maximum / average for most metrics;
  current / period change for energy (it's cumulative).
- **Chart** — a zoomable, pannable line chart of the selected metric over
  the chosen period.
- **Recent readings table** — the underlying raw readings, newest first.
- **Freshness badge** — shows whether the latest data is fresh, stale, or
  missing.

## Troubleshooting

| Problem | Fix |
|---|---|
| `docker compose up` fails / hangs | Open Docker Desktop first and wait for it to fully start. |
| Port already in use | Something else on your PC is using the database or app port. Change `POSTGRES_PORT` / `DASH_PORT` in `.env` (the default database port is 5436). |
| Login always fails | Confirm `DEMO_USERNAME` and `DEMO_PASSWORD` are set in `.env` — there's no built-in fallback. |
| Dashboard loads but shows no data | Re-run `python -m db.seed_plant_monitoring --reset`. |
| Readings all look stale | The seed timestamps data at the moment it runs. Re-run `python -m db.seed_plant_monitoring --reset`. |
| `relation ... does not exist` | Step 5 was skipped. Run `alembic upgrade head`, then the seeds. |

## Running the tests (optional)

```bash
python -m pytest -m "not db" -v   # logic only, no database needed
python -m pytest -v                # full suite, requires steps 4–6 done
```
