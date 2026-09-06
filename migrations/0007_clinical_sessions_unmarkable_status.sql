-- 0007 Add an 'unmarkable' status for a consultation too thin to grade fairly.
--
-- Set by the pre-marking guard in app/services/marking_service.py when a
-- transcript carries fewer than MIN_CANDIDATE_TURNS candidate turns, or under
-- MIN_CANDIDATE_SECONDS between the first and the last of them. The model is
-- never called and no session_results row is written, so the sitting consumes
-- no trial allowance (consumption is counted from result rows).

alter table clinical_sessions drop constraint if exists clinical_sessions_status_check;

alter table clinical_sessions
    add constraint clinical_sessions_status_check
    check (status in ('reading', 'live', 'processing', 'completed', 'abandoned', 'error', 'unmarkable'));
