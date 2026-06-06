"""Author structured mark-scheme indicators for stations (Build Package Phase 2).

For each station that lacks `mark_scheme_structured`, ask the model to convert the
free-text per-domain mark scheme + learning points into a Section 3.3 indicator
set, plus the case_type and which conditional rubrics are in play. Proposals are
written to a review file for clinical sign-off before they are applied.

Usage:
    python -m scripts.author_indicators                # propose -> scripts/indicator_proposals.jsonl
    python -m scripts.author_indicators --apply        # upsert approved proposals to Supabase

The proposal step is deterministic to assemble and is unit-tested; the live run
needs Azure OpenAI + Supabase credentials.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any, Dict, List

from app.schemas.indicators import StationIndicatorProposal

SYSTEM_PROMPT = """You convert a GP SCA station's free-text mark scheme into a structured indicator set for an automated examiner. Read the candidate brief, patient script, the per-domain mark scheme prose, and the learning points. Return ONLY JSON with this shape:
{
  "case_type": "patient_direct" | "third_party",
  "conditional_features": { "safeguarding": bool, "consent_capacity": bool, "complexity": bool, "third_party": bool },
  "mark_scheme_structured": { "domains": [ { "domain": "data_gathering" | "clinical_management" | "relating_to_others", "indicators": [ { "id": "snake_case_id", "label": "Short label", "positive_descriptor": "what achieving the core intent looks like", "negative_descriptor": "what not achieving it looks like" } ] } ] }
}
Rules: one indicator per distinct assessable point; capture the CORE clinical intent, not every sub-element; set conditional_features true only where the case genuinely centres that issue (safeguarding, consent or capacity, multimorbidity or polypharmacy complexity, or a third party speaker); case_type is third_party only when the speaker is a parent, carer, or paramedic, not the patient. No dashes anywhere in your output; use commas or the word "to" for ranges."""


def build_indicator_messages(station: Dict[str, Any]) -> List[Dict[str, str]]:
    """Assemble the [system, user] messages proposing indicators for one station."""
    user = "\n\n".join(
        [
            f"# STATION\nid: {station.get('id')}\ntitle: {station.get('title')}\n"
            f"patient_name: {station.get('patient_name')}\npatient_age: {station.get('patient_age')}\n"
            f"consultation_type: {station.get('consultation_type')}",
            "# CANDIDATE BRIEF\n" + (station.get("candidate_instructions") or ""),
            "# PATIENT SCRIPT\n" + (station.get("station_script") or ""),
            "# MARK SCHEME (data gathering)\n" + (station.get("data_gathering") or ""),
            "# MARK SCHEME (clinical management)\n" + (station.get("clinical_management") or ""),
            "# MARK SCHEME (relating to others)\n" + (station.get("relating_to_others") or ""),
            "# LEARNING POINTS\n" + (station.get("clinical_learning_points") or ""),
            "Return only the JSON proposal.",
        ]
    )
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]


def validate_proposal(data: dict) -> StationIndicatorProposal:
    """Validate a model proposal against the indicator schema."""
    return StationIndicatorProposal(**data)


async def _run(apply: bool) -> None:
    # Imported lazily so the module (and its unit tests) load without credentials.
    from openai import AsyncAzureOpenAI

    from app.config import Settings
    from app.services.marking_service import (
        make_azure_model_call,
        model_supports_temperature,
        parse_model_json,
    )
    from app.services.supabase_client import get_client

    settings = Settings()
    client = AsyncAzureOpenAI(
        azure_endpoint=settings.azure_openai_endpoint,
        api_key=settings.azure_openai_api_key,
        api_version=settings.azure_openai_marking_api_version or settings.azure_openai_api_version,
    )
    deployment = settings.azure_openai_marking_deployment
    temperature = 0.2 if model_supports_temperature(deployment) else None
    model_call = make_azure_model_call(client, deployment, temperature=temperature)
    supabase = get_client(settings)

    rows = (
        supabase.table("stations")
        .select("*")
        .is_("mark_scheme_structured", "null")
        .eq("is_active", True)
        .execute()
        .data
        or []
    )
    print(f"{len(rows)} stations need indicators")

    out_path = "scripts/indicator_proposals.jsonl"
    with open(out_path, "w", encoding="utf-8") as f:
        for station in rows:
            try:
                raw = await model_call(build_indicator_messages(station))
                proposal = validate_proposal(parse_model_json(raw))
            except Exception as exc:  # noqa: BLE001
                print(f"  station {station.get('id')} failed: {exc}")
                continue
            record = {"station_id": station["id"], "title": station.get("title"), "proposal": proposal.model_dump()}
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            if apply:
                supabase.table("stations").update(
                    {
                        "mark_scheme_structured": proposal.mark_scheme_structured.model_dump(),
                        "case_type": proposal.case_type,
                        "conditional_features": proposal.conditional_features.model_dump(),
                    }
                ).eq("id", station["id"]).execute()
            print(f"  {station.get('title')}: ok{' (applied)' if apply else ''}")

    print(f"proposals written to {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Upsert proposals to Supabase")
    args = parser.parse_args()
    asyncio.run(_run(args.apply))


if __name__ == "__main__":
    main()
