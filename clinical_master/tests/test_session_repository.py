"""
Tests for SessionRepository database operations.

Pure unit tests — the Supabase client is mocked, so no network or credentials
are required.
"""

from unittest import mock

from db.session_repository import SessionRepository


def _make_repo():
    """Build a SessionRepository backed by a mock Supabase client.

    Returns (repo, client_mock).
    """
    client = mock.MagicMock()
    with mock.patch(
        "db.session_repository.get_supabase_client", return_value=client
    ):
        repo = SessionRepository()
    return repo, client


def test_save_recording_path_writes_columns():
    """save_recording_path updates the two recording columns by session id."""
    repo, client = _make_repo()

    ok = repo.save_recording_path("sid", "recordings/sid.ogg", "eg_123")

    assert ok is True
    client.table.assert_called_with("clinical_sessions")
    update = client.table.return_value.update
    update.assert_called_once_with({
        "recording_path": "recordings/sid.ogg",
        "recording_egress_id": "eg_123",
    })
    update.return_value.eq.assert_called_once_with("id", "sid")
    update.return_value.eq.return_value.execute.assert_called_once()


def test_save_recording_path_returns_false_on_error():
    """A database error is swallowed and reported as False, never raised."""
    repo, client = _make_repo()
    client.table.return_value.update.return_value.eq.return_value.execute.side_effect = (
        RuntimeError("db down")
    )

    ok = repo.save_recording_path("sid", "recordings/sid.ogg", "eg_123")

    assert ok is False
