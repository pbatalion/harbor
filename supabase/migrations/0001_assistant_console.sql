create table if not exists public.assistant_workspaces (
  slug text primary key,
  name text not null,
  description text not null default '',
  sort_order integer not null default 0
);

create table if not exists public.assistant_runs (
  id text primary key,
  status text not null,
  digest_location text not null default '',
  day_plan text not null default '',
  urgent_items jsonb not null default '[]'::jsonb,
  source_counts jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  synced_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.assistant_items (
  id text primary key,
  run_id text not null references public.assistant_runs(id) on delete cascade,
  workspace_slug text not null references public.assistant_workspaces(slug) on delete cascade,
  source text not null,
  item_type text not null,
  external_id text not null,
  title text not null,
  actor text not null default '',
  occurred_at timestamptz not null,
  is_actionable boolean not null default false,
  is_unread boolean not null default false,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.assistant_drafts (
  id text primary key,
  run_id text not null references public.assistant_runs(id) on delete cascade,
  workspace_slug text not null references public.assistant_workspaces(slug) on delete cascade,
  draft_type text not null,
  recipient text not null default '',
  context text not null,
  draft text not null,
  status text not null default 'pending_review',
  created_at timestamptz not null default timezone('utc', now())
);

create index if not exists assistant_runs_synced_at_idx on public.assistant_runs (synced_at desc);
create index if not exists assistant_items_workspace_occurred_idx
  on public.assistant_items (workspace_slug, occurred_at desc);
create index if not exists assistant_drafts_workspace_created_idx
  on public.assistant_drafts (workspace_slug, created_at desc);
