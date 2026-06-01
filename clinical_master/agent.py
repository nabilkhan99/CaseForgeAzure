"""
Clinical Master — LiveKit Voice Agent

LiveKit Agents entrypoint for real-time patient consultation simulator.
Uses STT → LLM → TTS pipeline: Deepgram Nova-3 → OpenAI GPT-4.1-mini → Cartesia Sonic-3.

Replaces the previous FastAPI + ADK Gemini Live implementation.
"""

import asyncio
import json
import logging
from datetime import datetime

from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    CloseEvent,
    JobContext,
    cli,
    inference,
)
from livekit.agents.llm import ChatContext, ChatMessage, function_tool
from livekit.plugins import openai

from ai_agents.patient import build_patient_prompt
from config import settings
from db.session_repository import SessionRepository
from recording import start_session_recording

load_dotenv()

logger = logging.getLogger("clinical-master")
logger.setLevel(logging.INFO)


class PatientAgent(Agent):
    """
    LiveKit voice agent simulating a patient for SCA exam practice.

    Accepts station data to dynamically build a patient persona.
    Manages consultation timer, transcript capture, and feedback generation.
    """

    def __init__(self, station_data: dict | None = None) -> None:
        self._station_data = station_data or {}
        prompt = build_patient_prompt(station_data)

        super().__init__(
            instructions=prompt,
            stt=inference.STT("deepgram/nova-3"),
            llm=openai.LLM(
                model="gpt-4.1-mini",
                temperature=0.3,
            ),
            tts=inference.TTS("cartesia/sonic-3"),
            # Relaxed endpointing so users aren't cut off mid-sentence
            min_endpointing_delay=0.8,
            max_endpointing_delay=3.0,
        )

        # Session metadata — set from entrypoint before session.start
        self._user_id: str | None = None
        self._db_session_id: str | None = None
        self._db_repo: SessionRepository | None = None

        # Timer management
        self._timer_task: asyncio.Task | None = None
        self._consultation_ended = False

        # Per-message timestamps for accurate transcript timing
        self._message_timestamps: list[str] = []

    async def on_enter(self) -> None:
        """Called when the agent starts handling a room."""
        station_title = self._station_data.get("title", "Unknown")
        patient_name = self._station_data.get("patient_name", "Unknown")
        logger.info(f"[PatientAgent] Entering — case: {station_title}, patient: {patient_name}")

        # Update DB session status to 'live'
        if self._db_session_id and self._db_repo:
            try:
                self._db_repo.update_session_status(self._db_session_id, "live")
            except Exception as e:
                logger.error(f"Failed to update session status: {e}")

        # Start consultation timer
        duration = self._station_data.get(
            "consultation_duration_seconds",
            settings.CONSULTATION_DURATION_SECONDS,
        )
        self._timer_task = asyncio.create_task(self._consultation_timer(duration))

    async def on_exit(self) -> None:
        """Called when the agent is being removed from the room."""
        logger.info("[PatientAgent] Exiting")
        if self._timer_task and not self._timer_task.done():
            self._timer_task.cancel()

    async def on_user_turn_completed(
        self, turn_ctx: ChatContext, new_message: ChatMessage
    ) -> None:
        """
        Called after each user turn — we can log the user's transcript here.
        The full history is also available at session close via session.history.
        """
        user_text = new_message.text_content
        if user_text:
            logger.info(f"[Doctor] {user_text[:80]}...")
            self._message_timestamps.append(datetime.now().isoformat())

    @function_tool
    async def request_examination(self, examination_type: str) -> str:
        """Called when the doctor asks to perform a physical examination.
        The patient cooperates and describes findings.

        Args:
            examination_type: The type of examination being requested (e.g. blood pressure, abdominal, neurological)
        """
        logger.info(f"[PatientAgent] Examination requested: {examination_type}")

        # Check if the station script contains examination-relevant information
        script = self._station_data.get("station_script", "")
        candidate_info = self._station_data.get("candidate_instructions", "")
        context = f"{script}\n{candidate_info}".lower()

        # If the station data mentions this examination type, let the LLM use it
        exam_lower = examination_type.lower()
        if any(term in context for term in [exam_lower, exam_lower.replace(" ", "")]):
            return (
                f"The patient cooperates with the {examination_type} examination. "
                "Use the clinical scenario details to describe realistic findings. "
                "Respond as the patient would — describe what you feel, not clinical measurements."
            )

        return (
            f"The patient cooperates with the {examination_type} examination. "
            "There are no significant abnormal findings on this examination. "
            "Respond naturally as the patient."
        )

    @function_tool
    async def end_consultation(self) -> str:
        """Called when the doctor indicates the consultation is ending.
        Triggers feedback generation.
        """
        logger.info("[PatientAgent] Doctor ended consultation via tool call")
        if not self._consultation_ended:
            self._consultation_ended = True
            # Schedule disconnect after goodbye — gives TTS time to finish
            asyncio.create_task(self._delayed_disconnect(delay=8))
        return "Thank you doctor. The consultation has ended. Feedback is being generated."

    # ── Private Helpers ──────────────────────────────────────────

    async def _consultation_timer(self, duration: int) -> None:
        """Timer that ends the consultation after the specified duration."""
        logger.info(f"[PatientAgent] Consultation timer started: {duration}s")
        await asyncio.sleep(duration)
        if not self._consultation_ended:
            self._consultation_ended = True
            logger.info("[PatientAgent] Timer expired — ending consultation")
            # Tell the agent to wrap up, then disconnect
            self.session.generate_reply(
                instructions="The consultation time has ended. "
                "Thank the doctor and say goodbye naturally."
            )
            await self._delayed_disconnect(delay=10)

    async def _delayed_disconnect(self, delay: int = 8) -> None:
        """Wait for TTS to finish, then close the session."""
        await asyncio.sleep(delay)
        try:
            self.session.shutdown(drain=True)
            logger.info("[PatientAgent] Session shutdown after delay")
        except Exception as e:
            logger.warning(f"[PatientAgent] Shutdown error (non-fatal): {e}")


def _extract_transcript(
    session: AgentSession, message_timestamps: list[str] | None = None
) -> list[dict]:
    """
    Extract a clean transcript from the AgentSession history.
    Converts LiveKit chat items into our SCA transcript format.
    Uses pre-recorded timestamps where available.
    """
    transcript: list[dict] = []
    ts_list = message_timestamps or []
    msg_idx = 0
    for item in session.history.items:
        if item.type == "message":
            content = item.text_content
            if content and content.strip():
                role = "user" if item.role == "user" else "assistant"
                # Use pre-recorded timestamp if available, else fallback
                ts = ts_list[msg_idx] if msg_idx < len(ts_list) else datetime.now().isoformat()
                transcript.append({
                    "role": role,
                    "content": content.strip(),
                    "timestamp": ts,
                })
                msg_idx += 1
    return transcript





# ── Startup Cleanup ─────────────────────────────────────────────

def _cleanup_stale_sessions() -> None:
    """Mark any sessions stuck in live/processing as abandoned on startup."""
    try:
        repo = SessionRepository()
        repo.cleanup_stale_sessions(max_age_hours=2)
    except Exception as e:
        logger.warning(f"Stale session cleanup failed (non-fatal): {e}")

_cleanup_stale_sessions()


# ── LiveKit Server Setup ─────────────────────────────────────────

server = AgentServer()


@server.rtc_session()
async def entrypoint(ctx: JobContext) -> None:
    """
    Called when a participant joins a LiveKit room.

    Room metadata should contain JSON with:
      - station_id: UUID of the station case
      - user_id: UUID of the authenticated user
      - session_id: (optional) pre-created clinical session ID
    """
    ctx.log_context_fields = {
        "room_name": ctx.room.name,
    }

    # Parse metadata for station/user info
    # Priority: job dispatch metadata > room metadata > participant metadata
    room_metadata: dict = {}
    raw_metadata = ctx.job.metadata or ctx.room.metadata or ""
    if raw_metadata:
        try:
            room_metadata = json.loads(raw_metadata)
        except json.JSONDecodeError:
            logger.warning(f"Could not parse metadata as JSON: {raw_metadata[:100]}")

    station_id = room_metadata.get("station_id")
    user_id = room_metadata.get("user_id")
    session_id = room_metadata.get("session_id")

    logger.info(
        f"Room joined — station_id={station_id}, user_id={user_id}, session_id={session_id}"
    )

    # Load station data from Supabase
    station_data = None
    db_session_id = session_id
    db_repo = None

    try:
        db_repo = SessionRepository()

        if station_id:
            station_data = db_repo.get_station(station_id)
        else:
            station_data = db_repo.get_first_station()

        if station_data:
            logger.info(f"Loaded station: {station_data.get('title')}")

            # Ensure the DB session exists — create with the frontend's UUID if needed
            if db_session_id:
                # Frontend provided a session ID — upsert to ensure it exists in DB
                # user_id can be None for guest/anonymous sessions
                db_repo.upsert_session(db_session_id, user_id, station_data["id"])
                logger.info(f"Ensured DB session exists: {db_session_id} (user={user_id or 'guest'})")
            elif user_id:
                # No session ID from frontend — create a new one (authenticated only)
                db_session = db_repo.create_session(user_id, station_data["id"])
                if db_session:
                    db_session_id = db_session["id"]
                    logger.info(f"Created DB session: {db_session_id}")
        else:
            logger.warning("No station found in database — using default patient")

    except Exception as e:
        logger.error(f"Database setup error: {e}")

    # Create patient agent with station data
    agent = PatientAgent(station_data=station_data)
    agent._user_id = user_id
    agent._db_session_id = db_session_id
    agent._db_repo = db_repo

    # Start the voice session
    session = AgentSession(
        min_endpointing_delay=0.8,
        max_endpointing_delay=3.0,
    )

    await session.start(
        agent=agent,
        room=ctx.room,
    )

    # Best-effort full-consultation audio recording (internal use only).
    # Runs server-side via LiveKit Egress → Supabase Storage and auto-finalises
    # when the room empties. Never allowed to break the consultation.
    if settings.RECORDING_ENABLED and db_session_id:
        try:
            recording_result = await start_session_recording(ctx.room.name, db_session_id)
            if recording_result and db_repo:
                rec_path, rec_egress_id = recording_result
                db_repo.save_recording_path(db_session_id, rec_path, rec_egress_id)
        except Exception as e:
            logger.warning(f"Recording setup failed (non-fatal): {e}")

    # Brief delay for WebRTC track negotiation to complete
    await asyncio.sleep(0.5)

    # The patient speaks first, but with a GREETING ONLY. Speaking first masks
    # STT init latency and signals readiness (avoiding the awkward "say hello
    # twice" / dead-air problem) — but the patient must NOT reveal why they're
    # here yet. The doctor opens the consultation; the patient discloses the
    # presenting complaint on a later turn, once asked. That follow-up is
    # governed by the system prompt (build_patient_prompt → "Opening — TWO steps").
    await session.generate_reply(
        instructions=(
            "The consultation is just beginning and you are the first to speak. "
            "Say a short, natural greeting ONLY — for example \"Hello\" or \"Hi, doctor\". "
            "Do NOT say why you are here, do NOT mention any symptom, problem, or reason for "
            "your visit, and do NOT ask any questions. After greeting, wait for the doctor to "
            "respond and ask what they can help you with. "
            "Keep it to a few words. "
            "Output ONLY the words you would say out loud — no stage directions, no parenthetical "
            "actions, no asterisks, no physical descriptions."
        )
    )

    # Register close handler — save transcript and set status to "processing".
    # Feedback generation is handled by the frontend API route (agent process
    # is killed by LiveKit after 10s, too short for Gemini feedback calls).
    @session.on("close")
    def on_close(ev: CloseEvent) -> None:
        logger.info(f"Session closed, reason: {ev.reason}")

        transcript = _extract_transcript(session, agent._message_timestamps)
        logger.info(f"Extracted {len(transcript)} transcript entries")

        if not db_repo or not db_session_id:
            logger.warning("No DB repo/session — skipping transcript save")
        else:
            try:
                db_repo.save_transcript(db_session_id, transcript)
                db_repo.update_session_status(db_session_id, "processing")
                logger.info("Transcript saved, status set to 'processing'")
            except Exception as e:
                logger.error(f"Failed to save transcript: {e}")

        # Release memory — drop references to large objects
        agent._station_data = {}
        agent._message_timestamps.clear()
        agent._db_repo = None


if __name__ == "__main__":
    cli.run_app(server)
