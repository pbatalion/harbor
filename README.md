# AI Assistant (Worker + Web Console)

This project implements the architecture in `../ai-assistant-plan.md`:
- Redis + RQ + rq-scheduler orchestration
- Per-source checkpoints with overlap windows and idempotent dedupe
- Pre-LLM redaction
- Source-level summaries + aggregate triage
- Draft-only workflow (no auto-send of drafts)
- Optional Supabase sync for a Vercel-hosted web console

## Architecture

- `src/`: Python ingestion, queue orchestration, LLM triage, draft generation
- `web/`: Next.js app for the workspace dashboard (`work` and `downer`)
- `supabase/migrations/`: database schema for the web console

Recommended deployment split:

- `Vercel`: `web/`
- `Supabase`: Postgres for runs, queue items, drafts, workspace data
- `Worker host` (VM/Fly/Railway): Python pipeline in `src/`

## 1. Quick start (Docker)

1. Copy `.env.example` to `.env` and set credentials as needed.
2. Start core services:

```bash
docker compose up --build -d redis worker scheduler
```

3. Trigger one run:

```bash
docker compose run --rm runner
```

4. Check output digest preview files:

```bash
ls -la data/outbox
```

If email delivery is disabled (`DELIVERY_EMAIL_ENABLED=false`), digests are written to `data/outbox`.

## 2. Local Python run (without Docker)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m src.queue.scheduler
python -m src.queue.workers
python -m src.main enqueue-once
```

On macOS, if worker child processes crash with `objc_initializeAfterForkError`, set:

```bash
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
```

## 3. Draft-only behavior

- Draft actions are generated and stored in SQLite.
- No approval links.
- No automated sending of drafted replies/comments.

## 4. Useful commands

```bash
python -m src.main enqueue-once
python -m src.main report-follow-through
python scripts/test_sources.py
pytest -q
```

For a specific run and tighter list size:

```bash
python -m src.main report-follow-through --run-id <run_id> --actionable-limit 15
```

## 5. Web Console

1. Install the web app:

```bash
cd web
npm install
```

2. Add web env vars in `web/.env.local`:

```bash
SUPABASE_URL=...
SUPABASE_SERVICE_ROLE_KEY=...
ASSISTANT_WEB_PASSWORD=...
```

3. Start the dashboard:

```bash
npm run dev
```

4. Apply the Supabase schema:

Use [0001_assistant_console.sql](/Users/pbatalion/Documents/Documents%20-%20Mac/Git%20Projects/assistant/ai-assistant/supabase/migrations/0001_assistant_console.sql)

5. Enable Python-to-Supabase sync in `.env`:

```bash
SUPABASE_URL=...
SUPABASE_SERVICE_ROLE_KEY=...
```

## 6. Notes

- Missing credentials do not crash the pipeline. Sources return empty data and the run proceeds.
- Set `SEED_MOCK_DATA_IF_EMPTY=true` for local no-credential smoke testing.
- Gmail reporting uses a rolling lookback window (default `LOOKBACK_DAYS=30`) and thread-level dedupe for actionable digests.
- Gmail API pagination is enabled via `GMAIL_PAGE_SIZE` and `GMAIL_MAX_PAGES`.
