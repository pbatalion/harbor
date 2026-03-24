-- Source events table: normalized data from all integrations
-- Claude reads from this table for intelligent triage

create table if not exists public.assistant_source_events (
  id uuid primary key default gen_random_uuid(),

  -- Source identification
  source text not null,              -- gmail_work, gmail_personal, github, calendar, hedy
  event_type text not null,          -- email, issue, pr, pr_review, workflow, event, transcript
  external_id text,                  -- Original ID from source system

  -- Core content (normalized across all sources)
  title text not null,
  body text,                         -- Cleaned/truncated content for LLM
  snippet text,                      -- Short preview

  -- Actors
  actor text,                        -- Sender/author/organizer
  actor_email text,
  recipients jsonb default '[]',     -- [{email, name, type: "to"|"cc"|"attendee"}]

  -- Timing
  occurred_at timestamptz not null,
  due_at timestamptz,                -- For calendar events or deadlines

  -- Classification (pre-computed)
  is_directed_to_user boolean default false,  -- User is in TO/assignee
  is_mention boolean default false,           -- User is @mentioned
  requires_response boolean default false,    -- Likely needs a reply

  -- Extracted intelligence
  extracted_tasks jsonb default '[]',         -- [{task, due_date, priority}]
  extracted_entities jsonb default '{}',      -- {people: [], projects: [], deadlines: []}
  thread_summary text,                        -- For email threads / PR discussions

  -- Source-specific metadata
  metadata jsonb default '{}',

  -- Workspace routing
  workspace_slug text not null,

  -- Run tracking
  run_id uuid references public.assistant_runs(id) on delete cascade,

  -- Timestamps
  created_at timestamptz not null default timezone('utc', now()),

  -- Prevent duplicates within a run
  unique(run_id, source, external_id)
);

-- Indexes for common queries
create index if not exists idx_source_events_run on public.assistant_source_events(run_id);
create index if not exists idx_source_events_workspace on public.assistant_source_events(workspace_slug);
create index if not exists idx_source_events_occurred on public.assistant_source_events(occurred_at desc);
create index if not exists idx_source_events_source on public.assistant_source_events(source);
create index if not exists idx_source_events_requires_response on public.assistant_source_events(requires_response) where requires_response = true;

-- RLS policies
alter table public.assistant_source_events enable row level security;

create policy "Service role full access to source_events"
  on public.assistant_source_events
  for all
  using (true)
  with check (true);

comment on table public.assistant_source_events is 'Normalized events from Gmail, GitHub, Calendar, and Hedy for LLM triage';
comment on column public.assistant_source_events.body is 'Cleaned content, truncated to ~2000 chars for LLM context efficiency';
comment on column public.assistant_source_events.extracted_tasks is 'Tasks extracted by initial pass, e.g. [{task: "Review PR", due_date: "2024-03-20", priority: "high"}]';
