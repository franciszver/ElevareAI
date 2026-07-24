# Database Expiry Recovery Runbook

**Scope:** Render free-tier PostgreSQL databases expire 30 days after creation. This runbook restores a demo-ready database end-to-end.

## When to Use

Database expiry is confirmed if:
- Deploy health check fails; Render dashboard shows the Postgres instance is gone or marked "Deleted"
- `/health` endpoint returns `{"status":"unhealthy","database":"disconnected"}` (or curl fails)
- Web service logs show `FATAL: no pg_hba.conf entry for ...` or connection timeouts

## Recovery Steps (Estimated Time: ~5 minutes)

### 0. Try Blueprint Sync First

Before manual provisioning, check if Render can auto-recover the database:

Dashboard → Blueprints → Manual Sync may recreate `elevareai-db` and rebind `DATABASE_URL` automatically, since the database is declared in `render.yaml`. After syncing, verify in the Render dashboard whether the sync recreated the database:
- **If yes:** Skip to Step 4 (re-seed) and then Step 6 (verify).
- **If no:** Continue with Steps 1–5 as the manual fallback.

### 1. Provision New Database

Go to [Render Dashboard](https://dashboard.render.com):
- Click **New → PostgreSQL**
- Name: `elevareai-db` (matches `render.yaml` blueprint)
- Database: `elevareai` (default; matches blueprint)
- User: `elevareai` (default; matches blueprint)
- Plan: **Free** (required; database will expire 30 days from creation)
- Region: Same as your other services (check existing services)
- Click **Create Database**
- Wait for status to show **Available** (visible in the dashboard; ~1 min)

Note the database creation timestamp in the dashboard—you'll need to set a calendar reminder for ~day 28.

**Note:** A manually-created database is NOT part of the Blueprint's managed resource group, even if given the same name. A future Blueprint sync may attempt to re-provision `elevareai-db` and conflict. Verify in the Render dashboard after any later Blueprint sync.

### 2. Get Connection Credentials

From the new database's page in Render dashboard:
- Copy the **External Database URL** (looks like `postgresql://user:password@host:1234/dbname`)
- Do NOT commit this URL anywhere; treat it as a secret

### 3. Set Up Local Environment

On your local machine (or wherever you run the seed script):

```env
# Create/update .env with credentials extracted from the External Database URL
# The URL format is: postgresql://user:password@host:port/dbname
# So map to:
DB_HOST=<host from URL>
DB_PORT=<port from URL>
DB_NAME=<dbname from URL>
DB_USER=<user from URL>
DB_PASSWORD=<password from URL>

# Demo account password (set to something secure; never commit)
DEMO_PASSWORD=<choose a secure password>
```

### 4. Run Schema Creation and Seeding

From the repository root:

```bash
python scripts/seed_demo_data.py
```

This runs:
- Database schema creation via `scripts/setup_db.py` (applies migrations in `migrations/` directory)
- Seeding of demo accounts and data idempotently

Expected output: `[SUCCESS] Demo data seeding complete!`

Output shows demo login credentials (email + password). Demo account password = the value you set in `DEMO_PASSWORD` above.

### 5. Update Render Web Service

In Render dashboard, go to **elevareai-api** service settings:
- Environment variables
- Update `DATABASE_URL` with the new **Internal Database URL** from the new database (the exact label may vary in the Render dashboard; verify the option is available before using it; use the External URL only if the Internal URL isn't offered or reachable)
- Save and trigger **Manual Deploy**
- Wait for deploy to complete (~2 min)

### 6. Verify

```bash
# Health check should return "connected"
curl https://elevareai-api.onrender.com/health
```

Expected response: `{"status":"healthy","database":"connected"}`

If you get connection refused or timeout, the deploy may still be in progress; wait ~30 seconds and retry.

### 7. Test Frontend

- Open https://elevareai-frontend.onrender.com
- Log in as `demo@elevare.ai` with your DEMO_PASSWORD
- Verify demo data is visible (goals, sessions, practice items)

## Prevention

Render free Postgres databases expire exactly 30 days after creation. Set a calendar reminder for ~day 28:
- Check Render dashboard → your database → "Created at" timestamp
- Before day 30, either:
  - Upgrade the database plan to paid (prevents expiry), OR
  - Run this recovery procedure to recreate with fresh 30-day window

No maintenance required between creation and day 28; the database remains stable and does not require activity to stay alive.
