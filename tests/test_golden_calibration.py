"""Golden calibration tests, the marking model's acceptance gate.

Reproduces the three worked examples from the Build Package against the live
marking deployment. Skipped unless RUN_GOLDEN=1 (needs Azure OpenAI creds), so
the normal suite stays offline. This is the Phase 9 gate: if the configured
marking model (e.g. gpt-5.4-mini) cannot hit these anchors, escalate the model.

    RUN_GOLDEN=1 .venv/bin/python -m pytest tests/test_golden_calibration.py -v
"""
import json
import os

import pytest

from app.services.marking_service import (
    MarkingService,
    make_azure_model_call,
    model_supports_temperature,
)
from app.utils.no_dashes import find_dashes

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_GOLDEN") != "1",
    reason="set RUN_GOLDEN=1 with Azure OpenAI creds to run the calibration gate",
)


class FixtureRepo:
    def __init__(self, station, session):
        self.station, self.session = station, session

    def get_session(self, sid):
        return self.session if self.session["id"] == sid else None

    def get_station(self, stid):
        return self.station if self.station["id"] == stid else None

    def save_results(self, sid, payload):
        self.saved = payload

    def mark_completed(self, sid, score):
        self.completed = score

    def mark_errored(self, sid):
        self.errored = sid


def _load(name):
    path = os.path.join(os.path.dirname(__file__), "golden", f"{name}.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _make_service(repo):
    from openai import AsyncAzureOpenAI

    from app.config import Settings

    s = Settings()
    client = AsyncAzureOpenAI(
        azure_endpoint=s.azure_openai_endpoint,
        api_key=s.azure_openai_api_key,
        api_version=s.azure_openai_marking_api_version or s.azure_openai_api_version,
    )
    dep = s.azure_openai_marking_deployment
    temp = 0.2 if model_supports_temperature(dep) else None
    return MarkingService(repo, make_azure_model_call(client, dep, temperature=temp))


@pytest.mark.parametrize("name", ["sophie_miller", "sophie_wright", "faduma_hassan"])
async def test_golden_case(name):
    fx = _load(name)
    repo = FixtureRepo(fx["station"], fx["session"])
    service = _make_service(repo)

    result = await service.mark(fx["session"]["id"])
    expected = fx["expected"]
    grades = {d["domain"]: d["grade"] for d in result["domains"]}

    # Headline verdict and the Tier 3 cap are the load-bearing anchors.
    assert result["overall"]["verdict"] == expected["verdict"], (
        f"{name}: got {result['overall']['verdict']} ({grades}), expected {expected['verdict']}"
    )
    assert result["overall"]["tier3_override_applied"] == expected["tier3_override_applied"]
    # Clinical Management grade is the weighted, decisive domain in all three cases.
    assert grades.get("clinical_management") == expected["grades"]["clinical_management"], (
        f"{name}: CM grade {grades.get('clinical_management')}, expected {expected['grades']['clinical_management']}"
    )
    # House rule holds end to end.
    assert not find_dashes(result), f"{name}: dashes present in output"
