# SCA feedback engine migrations

These SQL files migrate Supabase from the old 0 to 100 / 3-score feedback schema
to the spec schema (FF SCA Feedback Engine Build Package, Section 12 + Section 13).

**Not auto-applied.** Applying `0001` is DESTRUCTIVE: it archives the existing
`session_results` rows to `session_results_legacy`, then rebuilds the table with
incompatible column types (integer 0 to 100 scores become CP/P/F/CF grades inside
`domains`). It also breaks the currently deployed feedback page until the frontend
(Phase 5) ships. Apply at go-live, in order, after the frontend is ready.

Apply order:
1. `0001_sca_session_results_rewrite.sql`  (archive + rebuild session_results)
2. `0002_sca_stations_indicators.sql`      (structured indicators + flags on stations)
3. `0003_sca_trend_reports.sql`            (trend layer table)
4. `0004_clinical_sessions_error_status.sql` (add 'error' to the status check)
5. `0005_concurrency_claims.sql`           (marking/trend build claims + the unique
   candidate_id constraint the trend upsert needs — applied to prod 26 Aug 2026)
6. `0006_trend_reports_v2.sql`              (trend contract v2: patterns + version,
   the "steady" trajectory value; recreates the unique candidate_id index where
   0005 was never applied)
7. `0007_clinical_sessions_unmarkable_status.sql` (add 'unmarkable' to the status
   check, for a consultation the pre-marking guard refuses to grade)

Apply via the Supabase SQL editor or `supabase db push`. Review `session_results_legacy`
is populated before dropping it manually later.
