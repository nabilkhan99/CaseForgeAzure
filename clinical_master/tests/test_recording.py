"""
Tests for session audio recording (LiveKit Egress → Supabase Storage).

The LiveKit API is mocked — no network, credentials, or real egress needed.
Requires: livekit-agents installed (`uv sync`).
"""

import asyncio
from unittest import mock

import pytest

try:
    import recording
    from livekit import api
    HAS_LIVEKIT = True
except ImportError:
    HAS_LIVEKIT = False

pytestmark = pytest.mark.skipif(not HAS_LIVEKIT, reason="livekit-agents not installed")


@pytest.fixture
def configured(monkeypatch):
    """Populate valid S3 settings so recording is considered configured."""
    monkeypatch.setattr(recording.settings, "RECORDING_ENABLED", True)
    monkeypatch.setattr(
        recording.settings,
        "SUPABASE_S3_ENDPOINT",
        "https://proj.storage.supabase.co/storage/v1/s3",
    )
    monkeypatch.setattr(recording.settings, "SUPABASE_S3_REGION", "eu-west-2")
    monkeypatch.setattr(recording.settings, "SUPABASE_S3_ACCESS_KEY_ID", "akid")
    monkeypatch.setattr(recording.settings, "SUPABASE_S3_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setattr(recording.settings, "RECORDING_BUCKET", "consultation-recordings")


def _fake_api(egress_id="eg_123", error=None):
    """Build a mock LiveKitAPI with an async egress client."""
    fake = mock.Mock()
    fake.egress.start_room_composite_egress = mock.AsyncMock(
        return_value=mock.Mock(egress_id=egress_id),
        side_effect=error,
    )
    fake.aclose = mock.AsyncMock()
    return fake


def test_start_session_recording_builds_correct_request(configured):
    """A successful start returns (filepath, egress_id) and builds an
    audio-only OGG egress targeting the configured Supabase S3 bucket."""
    fake = _fake_api(egress_id="eg_abc")

    with mock.patch.object(recording.api, "LiveKitAPI", return_value=fake):
        result = asyncio.run(recording.start_session_recording("clinical-sid", "sid"))

    assert result == ("recordings/sid.ogg", "eg_abc")
    fake.aclose.assert_awaited_once()

    req = fake.egress.start_room_composite_egress.call_args.args[0]
    assert req.room_name == "clinical-sid"
    assert req.audio_only
    assert len(req.file_outputs) == 1

    out = req.file_outputs[0]
    assert out.file_type == api.EncodedFileType.OGG
    assert out.filepath == "recordings/sid.ogg"
    assert out.s3.bucket == "consultation-recordings"
    assert out.s3.region == "eu-west-2"
    assert out.s3.access_key == "akid"
    assert out.s3.secret == "secret"
    assert out.s3.endpoint == "https://proj.storage.supabase.co/storage/v1/s3"
    assert out.s3.force_path_style


def test_returns_none_when_not_configured(monkeypatch):
    """With S3 credentials missing, no egress is attempted."""
    monkeypatch.setattr(recording.settings, "SUPABASE_S3_ACCESS_KEY_ID", "")

    with mock.patch.object(recording.api, "LiveKitAPI") as lkapi:
        result = asyncio.run(recording.start_session_recording("clinical-sid", "sid"))

    assert result is None
    lkapi.assert_not_called()


def test_returns_none_on_api_error(configured):
    """An egress failure is swallowed (returns None) and the client is closed."""
    fake = _fake_api(error=RuntimeError("egress unavailable"))

    with mock.patch.object(recording.api, "LiveKitAPI", return_value=fake):
        result = asyncio.run(recording.start_session_recording("clinical-sid", "sid"))

    assert result is None
    fake.aclose.assert_awaited_once()
