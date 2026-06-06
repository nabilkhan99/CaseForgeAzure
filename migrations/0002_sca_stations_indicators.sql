-- 0002 Structured indicators + conditional flags on stations (Build Package 3.3, 4.10).
-- Additive and safe. Populated by scripts/author_indicators.py (Phase 2).

alter table stations
    add column if not exists mark_scheme_structured jsonb,
    add column if not exists case_type text
        check (case_type in ('patient_direct', 'third_party')),
    add column if not exists conditional_features jsonb;

comment on column stations.mark_scheme_structured is
    'Section 3.3 indicator set: {domains:[{domain, indicators:[{id,label,positive_descriptor,negative_descriptor}]}]}';
comment on column stations.case_type is
    'patient_direct or third_party (parent/carer/paramedic), inferred from brief + script';
comment on column stations.conditional_features is
    'Which standing rubrics are in play: {safeguarding, consent_capacity, complexity, third_party} booleans';
