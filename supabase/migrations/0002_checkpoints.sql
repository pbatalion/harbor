-- Checkpoint storage for Supabase-first architecture
create table if not exists public.assistant_checkpoints (
  source text primary key,
  high_watermark timestamptz not null,
  updated_at timestamptz not null default timezone('utc', now())
);
