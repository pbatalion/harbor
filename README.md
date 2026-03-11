# Harbor

Harbor is a workspace-first personal operations console.

It combines:
- a Python worker that ingests Gmail, GitHub, Google Calendar, and Hedy
- LLM triage and draft generation
- a Supabase-backed data model for synced runs, queue items, and drafts
- a Vercel-hosted Next.js web app with separate `work` and `downer` views

Current workspace mapping:
- `work`: `gmail_work` and `github`
- `downer`: `gmail_personal`, `calendar`, and `hedy`

## Architecture

Directories:
- `src/`: Python ingestion, queue orchestration, summarization, syncing
- `web/`: Next.js app deployed to Vercel
- `supabase/migrations/`: SQL schema for Harbor tables
- `scripts/`: operational helpers such as Google OAuth token generation
- `tests/`: Python test suite

Runtime split:
- `Vercel`: serves the Harbor web UI from `web/`
- `Supabase`: stores synced runs, items, drafts, and workspace records
- `Worker host`: runs the Python worker and scheduler
- `Redis`: backs the RQ job queue used by the Python worker

## What Is Live Now

Implemented:
- Gmail, GitHub, Calendar, and Hedy ingestion
- thread-aware Gmail handling with direct-address gating for reply drafts
- 30-day Gmail lookback with pagination and thread dedupe
- draft-only workflow, no auto-send
- Supabase sync for completed runs
- Harbor web UI with password gate and workspace split

Still transitional:
- local SQLite is still used by the worker for checkpoints, local drafts, and local fallbacks
- HTML digest files are still generated locally as artifacts
- Docker support exists, but the long-term direction is Vercel + Supabase + worker host

## Required Environment Variables

Root worker config comes from [`.env.example`](/Users/pbatalion/Documents/Documents%20-%20Mac/Git%20Projects/assistant/ai-assistant/.env.example).

Important root variables:

```bash
REDIS_URL=redis://localhost:6379/0
LOCAL_TIMEZONE=America/New_York

ANTHROPIC_API_KEY=

GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REFRESH_TOKEN_WORK=
GOOGLE_REFRESH_TOKEN_PERSONAL=
GOOGLE_CALENDAR_IDS=

GITHUB_TOKEN=
GITHUB_ORG=Network-Craze

HEDY_API_BASE_URL=https://api.hedy.bot
HEDY_API_KEY=

SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
```

Web app config comes from [`web/.env.example`](/Users/pbatalion/Documents/Documents%20-%20Mac/Git%20Projects/assistant/ai-assistant/web/.env.example):

```bash
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
ASSISTANT_WEB_PASSWORD=
```

Notes:
- the web app currently reads Supabase server-side, so there is no public anon key in use
- `SUPABASE_SERVICE_ROLE_KEY` is used both by the Python sync and the server-rendered Next app

## Supabase Setup

Create a Supabase project, then run:
- [0001_assistant_console.sql](/Users/pbatalion/Documents/Documents%20-%20Mac/Git%20Projects/assistant/ai-assistant/supabase/migrations/0001_assistant_console.sql)

This creates:
- `assistant_workspaces`
- `assistant_runs`
- `assistant_items`
- `assistant_drafts`

## Web App

Install locally:

```bash
cd web
npm install
```

Run locally:

```bash
npm run dev
```

Validation:

```bash
npm run typecheck
npm run build
```

Deployment:
- deploy `web/` to Vercel
- set the Vercel project root to `web`
- add:
  - `SUPABASE_URL`
  - `SUPABASE_SERVICE_ROLE_KEY`
  - `ASSISTANT_WEB_PASSWORD`

The UI is protected by a simple password gate in [`web/middleware.ts`](/Users/pbatalion/Documents/Documents%20-%20Mac/Git%20Projects/assistant/ai-assistant/web/middleware.ts).

## Python Worker

Install locally:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Initialize local DB if needed:

```bash
PYTHONPATH=. .venv/bin/python -m src.main init-db
```

Run a worker:

```bash
OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES PYTHONPATH=. .venv/bin/python -m src.queue.workers
```

Enqueue one run:

```bash
PYTHONPATH=. .venv/bin/python -m src.main enqueue-once
```

Bootstrap the scheduler:

```bash
PYTHONPATH=. .venv/bin/python -m src.main bootstrap-schedule
```

Useful local reporting:

```bash
PYTHONPATH=. .venv/bin/python -m src.main report-follow-through
PYTHONPATH=. .venv/bin/python -m src.main report-follow-through --actionable-limit 15
```

## Google OAuth Token Refresh

Use the helper:
- [scripts/setup_oauth.py](/Users/pbatalion/Documents/Documents%20-%20Mac/Git%20Projects/assistant/ai-assistant/scripts/setup_oauth.py)

Generate a new work token:

```bash
PYTHONPATH=. .venv/bin/python scripts/setup_oauth.py --account work --no-browser
```

Generate a new personal token:

```bash
PYTHONPATH=. .venv/bin/python scripts/setup_oauth.py --account personal --no-browser
```

Default behavior:
- requests `gmail.readonly`
- starts a local callback server on `http://127.0.0.1:8765`
- prints the exact `GOOGLE_REFRESH_TOKEN_*=` line to paste into `.env`

If you also need calendar scope:

```bash
PYTHONPATH=. .venv/bin/python scripts/setup_oauth.py --account personal --include-calendar --no-browser
```

Important:
- the callback flow currently assumes the OAuth client in `.env` is a Google `Web application` client with `http://127.0.0.1:8765` added as an authorized redirect URI
- one `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` pair is shared by both Google accounts

## Development Notes

Gmail behavior:
- queries a rolling 30-day window by default
- fetches full thread metadata
- marks reply drafts as valid only when the latest relevant message is directly addressed to the account, not CC-only

Sync behavior:
- completed runs are mirrored into Supabase
- Harbor reads the latest synced run and its associated items/drafts

Local artifacts:
- SQLite remains useful for local checkpoints and fallback inspection
- HTML digests are written to `data/outbox/` when SMTP delivery is disabled

## Validation

Python:

```bash
PYTHONPATH=. .venv/bin/pytest -q
```

Web:

```bash
cd web
npm run typecheck
npm run build
```

## Optional / Legacy

These files still exist, but they are no longer the primary deployment path:
- [Dockerfile](/Users/pbatalion/Documents/Documents%20-%20Mac/Git%20Projects/assistant/ai-assistant/Dockerfile)
- [docker-compose.yml](/Users/pbatalion/Documents/Documents%20-%20Mac/Git%20Projects/assistant/ai-assistant/docker-compose.yml)

They are safe to keep while the worker hosting story is still evolving.
