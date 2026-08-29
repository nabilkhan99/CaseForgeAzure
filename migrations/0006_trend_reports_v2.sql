-- 0006 Trend report contract version 2.
--
-- v1 stored an audit: recurring_themes + style_patterns (each theme carrying six
-- metadata fields and four quotes), consistent_strengths, next_steps, caution and
-- a confidence rating. v2 stores at most three patterns, each pairing one verbatim
-- quote from the candidate's own consultations with a model line for that same
-- moment. See app/schemas/trend.py.
--
-- Safe to apply ahead of the frontend: the v1 columns stay in place (nulled on the
-- next rebuild, not dropped), so a page still reading them reads empty rather than
-- erroring. Drop them once nothing reads them; the drops are at the bottom,
-- commented out.

-- 1. The v2 payload.
alter table trend_reports add column if not exists version  integer not null default 2;
alter table trend_reports add column if not exists patterns jsonb   default '[]'::jsonb;

-- 2. Trajectory vocabulary: v2 says "steady" where v1 said "static", the same
--    judgement in the register the report is written in. Without this the check
--    constraint rejects every v2 report.
alter table trend_reports drop constraint if exists trend_reports_overall_trajectory_check;
alter table trend_reports add  constraint trend_reports_overall_trajectory_check
    check (overall_trajectory in ('improving', 'steady', 'declining'));

-- 3. One live report per candidate.
--
--    SessionRepository.save_trend has always upserted with on_conflict=candidate_id,
--    and its comment claimed this index was added in 0003. It was not: 0003 creates
--    only the non-unique (candidate_id, created_at) index. PostgREST needs a real
--    unique constraint to resolve on_conflict, so that upsert raises 42P10 against a
--    database built from 0003 alone. This is also the whole of the dedupe story for
--    two rebuilds racing (marking now triggers one after every case): they converge
--    on one row, later write wins, rather than the table growing duplicates.
--
--    On a database migrated through 0005_concurrency_claims this constraint already
--    exists under the same name and the create below is a no-op; this block remains
--    for environments built without it.
--
--    Collapse any pre-existing duplicates first, newest kept, or the index fails.
delete from trend_reports t
    using trend_reports newer
    where t.candidate_id = newer.candidate_id
      and t.created_at   < newer.created_at;

create unique index if not exists trend_reports_candidate_unique
    on trend_reports (candidate_id);

-- 4. Retired v1 columns. Uncomment once no client reads them.
-- alter table trend_reports drop column if exists confidence;
-- alter table trend_reports drop column if exists recurring_themes;
-- alter table trend_reports drop column if exists style_patterns;
-- alter table trend_reports drop column if exists consistent_strengths;
-- alter table trend_reports drop column if exists next_steps;
-- alter table trend_reports drop column if exists caution;
