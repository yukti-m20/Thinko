-- Thinko parent dashboard schema (local Supabase → hosted-ready)
-- Future: mood_samples (child_id, mood, created_at) once mood_tracker.py exists.

create extension if not exists "pgcrypto";

-- ---------------------------------------------------------------------------
-- Identity
-- ---------------------------------------------------------------------------

create table public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  role text not null default 'parent' check (role in ('parent', 'child')),
  display_name text not null default '',
  created_at timestamptz not null default now()
);

create table public.children (
  id uuid primary key default gen_random_uuid(),
  parent_id uuid not null references public.profiles (id) on delete cascade,
  display_name text not null,
  created_at timestamptz not null default now()
);

create index children_parent_id_idx on public.children (parent_id);

-- Stub for future ESP32 / device ingest
create table public.devices (
  id uuid primary key default gen_random_uuid(),
  child_id uuid not null references public.children (id) on delete cascade,
  label text not null default 'local',
  api_key_hash text,
  created_at timestamptz not null default now()
);

create index devices_child_id_idx on public.devices (child_id);

-- ---------------------------------------------------------------------------
-- Activity / sessions
-- ---------------------------------------------------------------------------

create table public.sessions (
  id uuid primary key default gen_random_uuid(),
  child_id uuid not null references public.children (id) on delete cascade,
  started_at timestamptz not null default now(),
  ended_at timestamptz,
  turn_count int not null default 0,
  primary_mode text not null default 'walkthrough',
  topic text,
  duration_seconds int
);

create index sessions_child_id_idx on public.sessions (child_id);
create index sessions_started_at_idx on public.sessions (started_at desc);

create table public.turns (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.sessions (id) on delete cascade,
  idx int not null,
  role text not null check (role in ('user', 'assistant')),
  content text not null default '',
  mode text,
  phase text,
  tool text,
  topic text,
  created_at timestamptz not null default now(),
  unique (session_id, idx)
);

create index turns_session_id_idx on public.turns (session_id);

-- ---------------------------------------------------------------------------
-- Mastery / progression
-- ---------------------------------------------------------------------------

create table public.mastery_scores (
  child_id uuid not null references public.children (id) on delete cascade,
  topic text not null,
  score double precision not null default 0
    check (score >= 0 and score <= 1),
  updated_at timestamptz not null default now(),
  primary key (child_id, topic)
);

create table public.mastery_events (
  id uuid primary key default gen_random_uuid(),
  child_id uuid not null references public.children (id) on delete cascade,
  session_id uuid references public.sessions (id) on delete set null,
  event text not null,
  topic text not null,
  score double precision,
  created_at timestamptz not null default now()
);

create index mastery_events_child_id_idx on public.mastery_events (child_id, created_at desc);

-- ---------------------------------------------------------------------------
-- Motivation (lightweight v1)
-- ---------------------------------------------------------------------------

create table public.child_stats (
  child_id uuid primary key references public.children (id) on delete cascade,
  current_streak_days int not null default 0,
  longest_streak_days int not null default 0,
  sessions_completed int not null default 0,
  last_session_on date
);

create or replace function public.handle_new_child_stats()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.child_stats (child_id)
  values (new.id)
  on conflict (child_id) do nothing;
  return new;
end;
$$;

create trigger on_child_created_stats
  after insert on public.children
  for each row execute function public.handle_new_child_stats();

-- ---------------------------------------------------------------------------
-- Auto-create profile on signup
-- ---------------------------------------------------------------------------

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, role, display_name)
  values (
    new.id,
    'parent',
    coalesce(new.raw_user_meta_data->>'display_name', split_part(new.email, '@', 1), 'Parent')
  );
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ---------------------------------------------------------------------------
-- RLS
-- ---------------------------------------------------------------------------

alter table public.profiles enable row level security;
alter table public.children enable row level security;
alter table public.devices enable row level security;
alter table public.sessions enable row level security;
alter table public.turns enable row level security;
alter table public.mastery_scores enable row level security;
alter table public.mastery_events enable row level security;
alter table public.child_stats enable row level security;

-- Parents can read/update their own profile
create policy "profiles_select_own"
  on public.profiles for select
  using (id = auth.uid());

create policy "profiles_update_own"
  on public.profiles for update
  using (id = auth.uid());

-- Children belonging to the parent
create policy "children_select_own"
  on public.children for select
  using (parent_id = auth.uid());

create policy "children_insert_own"
  on public.children for insert
  with check (parent_id = auth.uid());

create policy "children_update_own"
  on public.children for update
  using (parent_id = auth.uid());

create policy "children_delete_own"
  on public.children for delete
  using (parent_id = auth.uid());

-- Helper: child owned by current parent
create or replace function public.parent_owns_child(cid uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.children c
    where c.id = cid and c.parent_id = auth.uid()
  );
$$;

create policy "devices_select_own"
  on public.devices for select
  using (public.parent_owns_child(child_id));

create policy "sessions_select_own"
  on public.sessions for select
  using (public.parent_owns_child(child_id));

create policy "turns_select_own"
  on public.turns for select
  using (
    exists (
      select 1
      from public.sessions s
      join public.children c on c.id = s.child_id
      where s.id = turns.session_id and c.parent_id = auth.uid()
    )
  );

create policy "mastery_scores_select_own"
  on public.mastery_scores for select
  using (public.parent_owns_child(child_id));

create policy "mastery_events_select_own"
  on public.mastery_events for select
  using (public.parent_owns_child(child_id));

create policy "child_stats_select_own"
  on public.child_stats for select
  using (public.parent_owns_child(child_id));

-- Service role bypasses RLS for agent writes (local + hosted).
