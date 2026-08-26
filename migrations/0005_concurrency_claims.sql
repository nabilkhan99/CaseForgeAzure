-- 0005 Concurrency claims: DB-backed guards so marking / trend builds fire once
-- across serverless instances (the in-memory Sets only guard one instance).

-- Atomic claim for mark-consultation: stamped when a marking run is triggered,
-- cleared on failure so a later poll can retry. Doubles as telemetry
-- (marking duration = session_results.created_at - marking_started_at).
alter table clinical_sessions add column if not exists marking_started_at timestamptz;

-- One live trend report per candidate; save_trend upserts on this.
-- Table was empty when applied (every build so far failed), so no dedupe needed.
alter table trend_reports
    add constraint trend_reports_candidate_unique unique (candidate_id);

-- Claim row for generate-trend: winning the insert (or taking over a stale
-- claim) is the licence to call the engine. Service-role only: RLS enabled
-- with no policies.
create table if not exists trend_generation_claims (
    candidate_id uuid primary key references auth.users(id) on delete cascade,
    started_at   timestamptz not null default now()
);
alter table trend_generation_claims enable row level security;
