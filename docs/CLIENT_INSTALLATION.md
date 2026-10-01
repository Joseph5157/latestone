# Client Laptop Installation

How to install and run the RTL monitoring application on the client laptop,
into a **new folder**, from the client deployment repository. The previous
installation is left untouched as rollback/reference until this one is verified.

This is the production procedure. The synthetic-data quickstart in
`GETTING_STARTED.md` is for local development only and does **not** apply here.

## What runs where

- **Application database — PostgreSQL 16** holds application-owned state
  (users, Technician assignments, temperature limits). It is created by Alembic.
- **RTL temperature source — client SQL Server**, accessed **read-only**. The
  application never writes to it. The connection is opened lazily, only when an
  RTL-backed page is viewed — the application starts and logs in without it, and
  RTL pages show a safe "source unavailable" state if it is misconfigured.

## Prerequisites

- **Python 3.11 or newer**.
- **PostgreSQL 16** — Docker Desktop is the tested, documented option
  (`docker compose up -d postgres`). A native PostgreSQL 16 service is
  acceptable if the client prefers; point the `POSTGRES_*` variables at it.
- Network access from the laptop to the client RTL SQL Server, with a
  **read-only** login (see `docs/database/RTL_READ_ONLY_ACCESS.md`).

## Install steps

1. **Clone the deployment repository** into a new folder:
   ```
   git clone https://github.com/Joseph5157/rtl-monitoring-platform.git
   cd rtl-monitoring-platform
   ```

2. **Create `.env`** from the template and set real values — never copy the old
   installation's `.env`:
   ```
   copy .env.example .env    (Windows)   /   cp .env.example .env
   ```
   Set at minimum:
   - `APP_ENV=production`
   - `FLASK_SECRET_KEY=` a strong, persistent secret (required in production;
     startup fails closed without it).
   - `POSTGRES_*` for the application database.
   - `RTL_DB_HOST/PORT/NAME/USER/RTL_DB_PASSWORD` — the **read-only** client SQL
     Server login.
   - Leave `AUTH_DEMO_LOGIN_ENABLED` **unset** — production refuses to start if
     any `DEMO_*` / demo-login variable is set.

3. **Create the virtual environment and install dependencies:**
   ```
   python -m venv .venv
   .venv\Scripts\activate            (Windows)   /   source .venv/bin/activate
   pip install -r requirements.txt
   ```

4. **Start PostgreSQL** (Docker option):
   ```
   docker compose up -d postgres
   ```

5. **Build the application schema** (migrates to head `017_local_auth_hardening`):
   ```
   python -m alembic upgrade head
   ```

6. **Configure the read-only client SQL Server connection** and confirm the
   laptop can reach it with the read-only login (see
   `docs/database/RTL_READ_ONLY_ACCESS.md`).

7. **Bootstrap the initial Administrator** (one-time; prints a single-use setup
   link — open it and choose the password):
   ```
   python -m scripts.bootstrap_admin --username <name> --full-name "<Full Name>"
   ```

8. **Bootstrap Technician assignments** (preview first, then apply if clean):
   ```
   python -m scripts.bootstrap_rtl_assignments
   python -m scripts.bootstrap_rtl_assignments --apply
   ```
   This reads the client SQL Server SELECT-only and writes only the application
   PostgreSQL assignment store.

9. **Run the production preflight** — it must print OK before starting:
   ```
   python -m scripts.auth_preflight --force
   ```

10. **Start the application (Windows, production).** Use Waitress:
    ```
    waitress-serve --listen=0.0.0.0:8050 app:server
    ```
    Waitress is the supported Windows client-laptop WSGI server (pinned in
    `requirements.txt`). Open `http://127.0.0.1:8050`.

    Do **not** use Gunicorn on Windows — it imports the Unix-only `fcntl` and
    cannot start there (`gunicorn app:server` applies only to the Linux/Railway
    deployment). Do **not** use the Dash/Flask development server (`python app.py`)
    as the normal client startup path; it is for local development only.

11. **Browser acceptance** — open the app and run the acceptance checklist below.

## Acceptance checklist

- Log in.
- Command Center / overview loads.
- Registered RTLs (`/rtls`) lists RTLs.
- A real RTL detail page opens (`/rtls/<uid>`) and shows temperature history.
- Network and Historical Events (`/events`) load.
- Technician Assignments (`/technicians/assignments`); a Technician sees only
  their assigned RTLs.
- Users / authentication (Administrator) work.
- Reports (`/reports`) generate.
- The retired synthetic Plant/Device views do **not** appear in normal
  navigation (`/plants`, `/devices`, `/admin/devices` show the retired panel).
- The client SQL Server remains read-only throughout.
- Restart the application; it comes back up.
- No secrets were committed (`.env` stays local).

## Backup / rollback

- The previous client installation and the `RTL-Legacy` repository remain
  available and unmodified. To roll back, resume the previous install folder.
- This installation is a **new folder**; it adds nothing to, and removes
  nothing from, the previous one.
- The client SQL Server is read-only and is never modified by this application,
  so there is no client-data rollback to perform.
