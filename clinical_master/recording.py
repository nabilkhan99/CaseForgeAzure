"""
Session audio recording via LiveKit Cloud Room Composite Egress.

Records the full consultation — both the trainee/doctor and the AI patient — as a
single mixed, audio-only OGG file and uploads it directly to a private Supabase
Storage bucket (S3 gateway). For internal use only.

Best-effort by design: any failure is logged and swallowed so that recording can
never break a live consultation. Egress runs server-side on LiveKit Cloud and
auto-finalises when the room empties, so there is nothing to stop explicitly.
"""

import logging

from livekit import api

from config import settings

logger = logging.getLogger("clinical-master")


def _recording_configured() -> bool:
    """True only when every S3 setting needed to upload is present."""
    return bool(
        settings.SUPABASE_S3_ENDPOINT
        and settings.SUPABASE_S3_REGION
        and settings.SUPABASE_S3_ACCESS_KEY_ID
        and settings.SUPABASE_S3_SECRET_ACCESS_KEY
        and settings.RECORDING_BUCKET
    )


async def start_session_recording(
    room_name: str, session_id: str
) -> tuple[str, str] | None:
    """Start a Room Composite Egress recording for a consultation.

    Captures both participants as one mixed audio-only OGG file uploaded to
    ``recordings/<session_id>.ogg`` in the configured Supabase Storage bucket.

    Args:
        room_name: LiveKit room to record (e.g. ``clinical-<session_id>``).
        session_id: Clinical session UUID — used as the storage object key.

    Returns:
        ``(filepath, egress_id)`` on success, or ``None`` if recording is not
        configured or the egress request fails. Never raises.
    """
    if not _recording_configured():
        logger.warning(
            "Recording enabled but Supabase S3 storage is not configured — "
            "skipping egress for session %s",
            session_id,
        )
        return None

    filepath = f"recordings/{session_id}.ogg"
    lkapi: api.LiveKitAPI | None = None
    try:
        request = api.RoomCompositeEgressRequest(
            room_name=room_name,
            audio_only=True,
            file_outputs=[
                api.EncodedFileOutput(
                    file_type=api.EncodedFileType.OGG,
                    filepath=filepath,
                    s3=api.S3Upload(
                        bucket=settings.RECORDING_BUCKET,
                        region=settings.SUPABASE_S3_REGION,
                        access_key=settings.SUPABASE_S3_ACCESS_KEY_ID,
                        secret=settings.SUPABASE_S3_SECRET_ACCESS_KEY,
                        endpoint=settings.SUPABASE_S3_ENDPOINT,
                        force_path_style=True,
                    ),
                )
            ],
        )
        # LiveKitAPI() reads LIVEKIT_URL / LIVEKIT_API_KEY / LIVEKIT_API_SECRET from env.
        lkapi = api.LiveKitAPI()
        result = await lkapi.egress.start_room_composite_egress(request)
        logger.info(
            "Egress started for session %s → %s (egress %s)",
            session_id,
            filepath,
            result.egress_id,
        )
        return filepath, result.egress_id
    except Exception as e:  # best-effort: never propagate
        logger.error("Failed to start session recording: %s: %s", type(e).__name__, e)
        return None
    finally:
        if lkapi is not None:
            await lkapi.aclose()


async def stop_session_recording(egress_id: str) -> bool:
    """Stop an active egress so the recording finalises and uploads.

    Room Composite Egress only writes the file to storage when it *ends*, and it
    does not reliably auto-stop when a consultation finishes — the LiveKit room
    can linger (empty-timeout / lingering participants), leaving the egress
    running indefinitely (billing the whole time) and never uploading. So we stop
    it explicitly when the agent job shuts down.

    Args:
        egress_id: The egress to stop (from ``start_session_recording``).

    Returns:
        True if the stop request was sent, False otherwise. Never raises.
    """
    if not egress_id:
        return False

    lkapi: api.LiveKitAPI | None = None
    try:
        lkapi = api.LiveKitAPI()
        await lkapi.egress.stop_egress(api.StopEgressRequest(egress_id=egress_id))
        logger.info("Stopped egress %s", egress_id)
        return True
    except Exception as e:  # best-effort: never propagate
        logger.error("Failed to stop egress %s: %s: %s", egress_id, type(e).__name__, e)
        return False
    finally:
        if lkapi is not None:
            await lkapi.aclose()
