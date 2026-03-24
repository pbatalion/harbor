# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Harbor is a workspace-first personal operations console combining:
- Python worker for ingesting Gmail, GitHub, Google Calendar, and Hedy
- LLM triage and draft generation using Claude/Anthropic API
- Supabase-backed data model for synced runs, queue items, and drafts
- Next.js web app with workspace-specific views (`work` and `downer`)

## Commands

### Python Worker

```bash
# Setup
python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt

# Initialize local SQLite DB
PYTHONPATH=. .venv/bin/python -m src.main init-db

# Run tests
PYTHONPATH=. .venv/bin/pytest -q

# Run single test file
PYTHONPATH=. .venv/bin/pytest tests/test_gmail_source.py -q

# Start RQ worker
OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES PYTHONPATH=. .venv/bin/python -m src.queue.workers

# Enqueue single run
PYTHONPATH=. .venv/bin/python -m src.main enqueue-once

# Bootstrap scheduler
PYTHONPATH=. .venv/bin/python -m src.main bootstrap-schedule
```

### Web App (Next.js)

```bash
cd web
npm install
npm run dev        # local dev server
npm run typecheck  # TypeScript validation
npm run build      # production build
```

## Architecture

### Python (`src/`)

- `sources/` - Data source adapters: `gmail.py`, `github.py`, `calendar.py`, `hedy.py`
- `intelligence/` - Claude LLM integration: `claude.py` (API calls), `triage.py` (classification), `prompts.py`, `schema.py`
- `queue/` - RQ job orchestration: `workers.py`, `jobs.py`, `scheduler.py`
- `integrations/supabase.py` - Sync completed runs to Supabase
- `state/` - Local SQLite state management
- `delivery/` - HTML digest generation
- `settings.py` - Pydantic settings from `.env`
- `main.py` - CLI entry point

### Web (`web/`)

- Next.js 14 App Router with Supabase server-side reads
- `app/[workspaceSlug]/` - Workspace-specific dashboard routing
- `lib/supabase/` - Supabase client
- `lib/contracts.ts`, `lib/dashboard.ts`, `lib/workspaces.ts` - Data contracts
- `middleware.ts` - Password gate protection

### Runtime Components

- **Vercel**: hosts the Next.js web UI
- **Supabase**: stores runs, items, drafts, workspaces
- **Worker host**: runs Python worker and scheduler
- **Redis**: backs the RQ job queue

## Key Patterns

- Gmail ingestion uses 30-day rolling window with thread deduplication
- Reply drafts require direct-address (not CC-only) on latest message
- Local SQLite still used for checkpoints alongside Supabase sync
- Web app uses `SUPABASE_SERVICE_ROLE_KEY` for server-side data access
