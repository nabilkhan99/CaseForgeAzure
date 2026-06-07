-- 0003 Trend layer (Build Package Section 13). Cross-case development report per candidate.

create table if not exists trend_reports (
    id                    uuid primary key default gen_random_uuid(),
    candidate_id          uuid not null references auth.users(id) on delete cascade,
    "window"              jsonb,  -- quoted: window is a reserved word
    confidence            text check (confidence in ('low', 'medium', 'high')),
    overall_trajectory    text check (overall_trajectory in ('improving', 'static', 'declining')),
    overall_narrative     text,
    recurring_themes      jsonb default '[]'::jsonb,
    style_patterns        jsonb default '[]'::jsonb,
    consistent_strengths  jsonb default '[]'::jsonb,
    next_steps            jsonb default '[]'::jsonb,
    caution               text,
    created_at            timestamptz default now()
);

create index if not exists trend_reports_candidate_idx on trend_reports (candidate_id, created_at desc);

alter table trend_reports enable row level security;

create policy "candidates read own trend"
    on trend_reports for select
    using (candidate_id = auth.uid());
