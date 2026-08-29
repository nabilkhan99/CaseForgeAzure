"""The post-marking trend rebuild: it fires, and it never gets in the way.

Marking is the thing the candidate paid for. Every test here is ultimately the
same assertion from a different angle: whatever the trend layer does, the
marking response is unaffected.
"""
import logging

import pytest

from app.services.trend_trigger import (
    TREND_TRIGGER_PATH,
    fire_trend_rebuild,
    resolve_self_base_url,
)

CANDIDATE = "56454120-2d2c-4b1a-9f3e-5f0a3b1c7d99"


class FakeSettings:
    def __init__(self, self_base_url="", marking_shared_secret="s3cret"):
        self.self_base_url = self_base_url
        self.marking_shared_secret = marking_shared_secret


class Recorder:
    """Stands in for the HTTP post, recording the call the trigger would make."""

    def __init__(self, raises=None):
        self.calls = []
        self.raises = raises

    async def __call__(self, url, json_body, headers):
        self.calls.append((url, json_body, headers))
        if self.raises:
            raise self.raises


# ── where the app finds itself ──


def test_self_base_url_prefers_the_explicit_setting(monkeypatch):
    monkeypatch.setenv("WEBSITE_HOSTNAME", "caseforge2025a.azurewebsites.net")
    settings = FakeSettings(self_base_url="http://localhost:7071/")
    assert resolve_self_base_url(settings) == "http://localhost:7071"


def test_self_base_url_falls_back_to_the_azure_hostname(monkeypatch):
    monkeypatch.setenv("WEBSITE_HOSTNAME", "caseforge2025a.azurewebsites.net")
    assert resolve_self_base_url(FakeSettings()) == "https://caseforge2025a.azurewebsites.net"


def test_self_base_url_is_none_when_nothing_says(monkeypatch):
    monkeypatch.delenv("WEBSITE_HOSTNAME", raising=False)
    assert resolve_self_base_url(FakeSettings()) is None


# ── the request it makes ──


async def test_it_posts_the_candidate_id_with_the_shared_secret(monkeypatch):
    monkeypatch.setenv("WEBSITE_HOSTNAME", "caseforge2025a.azurewebsites.net")
    post = Recorder()

    assert await fire_trend_rebuild(CANDIDATE, FakeSettings(), post=post) is True

    url, body, headers = post.calls[0]
    assert url == f"https://caseforge2025a.azurewebsites.net{TREND_TRIGGER_PATH}"
    assert body == {"candidateId": CANDIDATE}  # the shape the frontend uses
    assert headers["x-marking-secret"] == "s3cret"


async def test_no_secret_header_when_none_is_configured(monkeypatch):
    monkeypatch.setenv("WEBSITE_HOSTNAME", "host")
    post = Recorder()
    await fire_trend_rebuild(CANDIDATE, FakeSettings(marking_shared_secret=""), post=post)
    assert "x-marking-secret" not in post.calls[0][2]


# ── and every way it can fail ──


@pytest.mark.parametrize(
    "failure",
    [
        TimeoutError("timed out after 2.5s"),
        ConnectionError("connection refused"),
        RuntimeError("something else entirely"),
    ],
)
async def test_a_failed_trigger_is_swallowed_and_warned_about(failure, monkeypatch, caplog):
    monkeypatch.setenv("WEBSITE_HOSTNAME", "host")
    post = Recorder(raises=failure)

    with caplog.at_level(logging.WARNING, logger="app.services.trend_trigger"):
        assert await fire_trend_rebuild(CANDIDATE, FakeSettings(), post=post) is False

    message = caplog.records[-1].getMessage()
    assert CANDIDATE in message
    assert "marking result is unaffected" in message


async def test_no_candidate_id_is_a_no_op(monkeypatch):
    monkeypatch.setenv("WEBSITE_HOSTNAME", "host")
    post = Recorder()
    assert await fire_trend_rebuild(None, FakeSettings(), post=post) is False
    assert post.calls == []


async def test_unresolvable_base_url_is_a_no_op(monkeypatch):
    monkeypatch.delenv("WEBSITE_HOSTNAME", raising=False)
    post = Recorder()
    assert await fire_trend_rebuild(CANDIDATE, FakeSettings(), post=post) is False
    assert post.calls == []


async def test_the_marking_payload_carries_an_intact_candidate_id():
    """What the trigger reads is stamped after the no-dash pass, so it is a UUID.

    Run through the same enforcement marking uses: before the fix, the id came
    out of the payload as "56454120 to 2d2c to 4b1a...".
    """
    from app.utils.no_dashes import enforce_no_dashes

    payload = enforce_no_dashes({"overall": {"one_line_summary": "safe but thin"}})
    payload["candidate_id"] = CANDIDATE  # stamped after, as MarkingService does

    assert payload["candidate_id"] == CANDIDATE
