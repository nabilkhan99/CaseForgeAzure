-- 0004 Add an 'error' status so a failed marking run is visible (not stuck in 'processing').

alter table clinical_sessions drop constraint if exists clinical_sessions_status_check;

alter table clinical_sessions
    add constraint clinical_sessions_status_check
    check (status in ('reading', 'live', 'processing', 'completed', 'abandoned', 'error'));
