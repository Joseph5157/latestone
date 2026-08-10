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
demo login credentials (see step 6).

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
docker compose up -d
```
This starts a local PostgreSQL container (Docker Desktop must be running
first). It only needs a few seconds to initialize on first run.

**5. Load the sample data**

```bash
python -m db.seed_plant_monitoring --reset
```
Loads 30 days of readings (~1.38 million rows) across 30 plants, 71
transformers and 120 devices. Takes about 30 seconds.

**6. Run the dashboard**

```bash
python app.py
```
Open **http://localhost:8050** in your browser and log in:

- Username: `admin`
- Password: `demo1234`

These are placeholder credentials for local use. To change them, edit
`DEMO_USERNAME` / `DEMO_PASSWORD` in `.env` — there is no fallback, so if
they are ever unset, login is refused entirely.

## Everyday use

Once installed, you don't repeat the full setup — just:

```bash
docker compose up -d      # start the database (if not already running)
.venv\Scripts\activate    # Windows — or: source .venv/bin/activate
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
| Port already in use | Something else on your PC is using 5432 or 8050. Change `POSTGRES_PORT` / `DASH_PORT` in `.env`. |
| Login always fails | Confirm `DEMO_USERNAME` and `DEMO_PASSWORD` are set in `.env` — there's no built-in fallback. |
| Dashboard loads but shows no data | Re-run `python -m db.seed_plant_monitoring --reset`. |

## Running the tests (optional)

```bash
python -m pytest -m "not db" -v   # logic only, no database needed
python -m pytest -v                # full suite, requires steps 4–5 done
```
