-- 0001 SCA session_results rewrite (DESTRUCTIVE, gated; see migrations/README.md)
-- Archives the old 0 to 100 / 3-score rows, then rebuilds session_results to the
-- spec single-case schema (Build Package Section 12).

-- 1. Archive existing rows verbatim (keep until verified, drop manually later).
create table if not exists session_results_legacy as table session_results;

-- 2. Rebuild.
drop table if exists session_results cascade;

create table session_results (
    id                      uuid primary key default gen_random_uuid(),
    session_id              uuid not null unique references clinical_sessions(id) on delete cascade,
    verdict                 text check (verdict in ('Pass', 'Bare Pass', 'Bare Fail', 'Fail')),
    weighted_score          numeric(3, 1),
    max_score               numeric(3, 1) default 10.5,
    one_line_summary        text,
    tier3_override_applied  boolean default false,
    domains                 jsonb default '[]'::jsonb,
    timing                  jsonb,
    focus_areas             jsonb default '[]'::jsonb,
    capability_links        text[] default '{}',
    confidence              jsonb,
    evidence_map            jsonb default '[]'::jsonb,
    conditional_features    jsonb,
    created_at              timestamptz default now()
);

-- 3. RLS: candidates read their own results; service role (marking) bypasses RLS.
alter table session_results enable row level security;

create policy "candidates read own results"
    on session_results for select
    using (
        exists (
            select 1 from clinical_sessions s
            where s.id = session_results.session_id
              and s.user_id = auth.uid()
        )
    );
