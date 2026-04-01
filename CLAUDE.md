# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Harbor is a personal operations console that ingests data from Gmail (work + personal), GitHub, Google Calendar, and Hedy (meeting transcripts), uses Claude API for triage and draft generation, syncs results to Supabase, and serves a Next.js web dashboard.

## VM Environment

- **Project Path**: /home/harbor/harbor
- **User**: harbor (application), root (admin)
- **Python venv**: /home/harbor/harbor/.venv
- **Services**: harbor-worker, harbor-scheduler, redis-server (all systemd)

## Quick Commands

```bash
# Run tests
cd /home/harbor/harbor
sudo -u harbor PYTHONPATH=. .venv/bin/pytest -q

# Run single test file
sudo -u harbor PYTHONPATH=. .venv/bin/pytest tests/test_gmail_source.py -q

# Lint (ruff, via pre-commit)
sudo -u harbor .venv/bin/ruff check src/ tests/
sudo -u harbor .venv/bin/ruff format --check src/ tests/

# Trigger a manual run
sudo -u harbor PYTHONPATH=. .venv/bin/python -m src.main enqueue-once

# Initialize local SQLite DB
sudo -u harbor PYTHONPATH=. .venv/bin/python -m src.main init-db

# Service management
systemctl status harbor-worker harbor-scheduler
systemctl restart harbor-worker harbor-scheduler
journalctl -u harbor-worker -f
journalctl -u harbor-scheduler -f

# Check Redis
redis-cli ping
redis-cli KEYS "rq:*"

# Web dev server
cd /home/harbor/harbor/web && npm run dev
npm run typecheck
npm run build
```

## Code Style

- Python: ruff (line-length 110, target py311). Pre-commit hooks run `ruff --fix` and `ruff-format` on commit.
- Config in `pyproject.toml` under `[tool.ruff]`.
- Pydantic models for settings and schemas throughout.

## Architecture

### Python Worker (`src/`)

| Module | Purpose |
|--------|---------|
| sources/ | Data source adapters: gmail, github, calendar, hedy |
| intelligence/ | Claude LLM integration: triage, prompts, schema, enhanced_triage, normalizer, storage |
| queue/ | RQ job orchestration: workers, jobs, scheduler, connection |
| integrations/ | Supabase sync |
| state/ | Local SQLite: db, checkpoints, drafts |
| delivery/ | Output: email_digest, sms |
| reporting/ | Follow-through reports |
| privacy/ | Data redaction |
| utils/ | Helpers: timestamps, http, auth, filters, logging |
| settings.py | Pydantic Settings model, loads from .env + config/*.yaml |
| main.py | CLI entrypoint (init-db, enqueue-once, bootstrap-schedule, report-follow-through) |

### Configuration

- `config/settings.yaml` - app config (schedule hours, filters, source toggles, delivery)
- `config/workspaces.yaml` - workspace definitions and draft routing rules
- `.env` - secrets and environment-specific overrides
- Settings cascade: YAML defaults -> env var overrides (see `load_settings()` in settings.py)

### Job Flow

1. **Scheduler** triggers run via cron (hours configured in settings.yaml) or manual `enqueue-once`
2. **Fetch jobs** run in parallel: gmail_work, gmail_personal, github, calendar, hedy
3. Each fetch: read checkpoint -> fetch from API -> write to SQLite -> update checkpoint
4. **Aggregate job** runs after all fetches: Claude API triage -> generate drafts -> sync to Supabase -> save HTML digest

### Workspaces

Items route to workspaces based on source (defined in `config/workspaces.yaml`):
- **work**: gmail_work, github
- **downer**: gmail_personal, calendar, hedy

Draft routing uses email patterns to assign drafts to workspaces.

### Web App (`web/`)

Next.js 14 App Router with Supabase server-side reads. Protected by password gate (`middleware.ts`).

| Path | Purpose |
|------|---------|
| app/[workspaceSlug]/ | Workspace dashboard |
| app/login/ | Password gate |
| lib/ | Supabase client and utilities |

Deployed to Vercel (auto-deploy from main). Set Vercel project root to `web`.

## External Services

- **Supabase**: Tables: assistant_runs, assistant_items, assistant_drafts, assistant_workspaces, assistant_checkpoints, assistant_source_events. Migrations in `supabase/migrations/`.
- **Anthropic Claude API**: Triage + draft generation (model configured via ANTHROPIC_MODEL, default claude-sonnet-4-6)
- **Gmail/Calendar API**: OAuth refresh tokens (one shared Google client for both accounts)
- **GitHub API**: Personal access token
- **Hedy API**: Meeting transcripts

## Key Environment Variables

Root worker (`.env`): REDIS_URL, DATABASE_PATH, ANTHROPIC_API_KEY, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN_WORK, GOOGLE_REFRESH_TOKEN_PERSONAL, GITHUB_TOKEN, GITHUB_ORG, HEDY_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY

Web app (`web/.env`): SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, ASSISTANT_WEB_PASSWORD

## Troubleshooting

- **Auth errors**: Gmail OAuth tokens may need refresh via `scripts/setup_oauth.py --account work --no-browser`
- **Worker stuck**: Check `systemctl status harbor-worker`, `redis-cli ping`, restart if needed
- **Supabase sync**: Check migrations applied, check logs with `journalctl -u harbor-worker | grep -i supabase`

## Known Issues

1. GOOGLE_REFRESH_TOKEN_PERSONAL may need periodic re-generation via OAuth flow
2. Local SQLite used for checkpoints; Supabase checkpoints table is optional fallback
