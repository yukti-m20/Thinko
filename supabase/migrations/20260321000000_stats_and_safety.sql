-- Migration: session stats + emergency stops + delete-child helper

-- ---------------------------------------------------------------------------
-- Session statistics (mood, problems solved, subjects, topics needing help)
-- ---------------------------------------------------------------------------

create table public.session_stats (
  id            uuid primary key default gen_random_uuid(),
  session_id    uuid not null references public.sessions (id)  on delete cascade,
  child_id      uuid not null references public.children (id)  on delete cascade,
  mood_counts   jsonb not null default '{}',
  problems_solved int not null default 0,
  subjects      jsonb not null default '{}',
  topics_needing_help jsonb not null default '{}',
  week_of       date not null,
  created_at    timestamptz not null default now()
);

create index session_stats_child_week_idx on public.session_stats (child_id, week_of desc);
create index session_stats_session_id_idx on public.session_stats (session_id);

alter table public.session_stats enable row level security;

create policy "session_stats_select_own"
  on public.session_stats for select
  using (public.parent_owns_child(child_id));

-- ---------------------------------------------------------------------------
-- Emergency stops (full conversation transcript)
-- ---------------------------------------------------------------------------

create table public.emergency_stops (
  id           uuid primary key default gen_random_uuid(),
  child_id     uuid not null references public.children (id)  on delete cascade,
  session_id   uuid references public.sessions (id)           on delete set null,
  transcript   text not null default '',
  triggered_at timestamptz not null default now()
);

create index emergency_stops_child_id_idx on public.emergency_stops (child_id, triggered_at desc);

alter table public.emergency_stops enable row level security;

create policy "emergency_stops_select_own"
  on public.emergency_stops for select
  using (public.parent_owns_child(child_id));

-- Allow service role inserts (Python agent + Next.js API route both use service role)
-- RLS is bypassed for service role automatically.

-- ---------------------------------------------------------------------------
-- Weekly aggregate view (used by dashboard stats page)
-- ---------------------------------------------------------------------------

create or replace view public.weekly_subject_stats as
select
  child_id,
  week_of,
  sum(problems_solved)                             as total_solved,
  -- Merge all subjects jsonb across sessions in the week
  (
    select jsonb_object_agg(key, val)
    from (
      select key, sum(value::int) as val
      from public.session_stats ss2
      cross join lateral jsonb_each_text(ss2.subjects)
      where ss2.child_id = ss.child_id
        and ss2.week_of  = ss.week_of
      group by key
    ) agg
  )                                                as subjects_weekly
from public.session_stats ss
group by child_id, week_of;

-- ---------------------------------------------------------------------------
-- Delete all data for a child (called from parent dashboard)
-- ---------------------------------------------------------------------------

create or replace function public.delete_child_data(cid uuid)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  -- Verify the caller owns this child
  if not public.parent_owns_child(cid) then
    raise exception 'not authorised';
  end if;

  -- Cascade-delete everything linked to the child.
  -- Most tables already have ON DELETE CASCADE from children.id,
  -- but we also need to clear child_stats (no cascade — it's a 1-1 keyed table).
  delete from public.child_stats     where child_id = cid;
  delete from public.mastery_scores  where child_id = cid;
  delete from public.mastery_events  where child_id = cid;
  delete from public.emergency_stops where child_id = cid;
  delete from public.session_stats   where child_id = cid;
  -- sessions → turns cascade automatically
  delete from public.sessions        where child_id = cid;

  -- Re-insert blank child_stats row so the trigger doesn't need to fire again
  insert into public.child_stats (child_id) values (cid)
  on conflict (child_id) do nothing;
end;
$$;
