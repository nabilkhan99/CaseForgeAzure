"""
Clinical Master — LiveKit Voice Agent

LiveKit Agents entrypoint for real-time patient consultation simulator.
Uses STT → LLM → TTS pipeline: Deepgram Nova-3 → Cerebras Llama 4 Scout → Cartesia Sonic-3.

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

from ai_agents.feedback import generate_feedback
from ai_agents.patient import build_patient_prompt
from config import settings
from db.session_repository import SessionRepository

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
            llm=openai.LLM.with_cerebras(
                model="gpt-oss-120b",
                temperature=0.7,
            ),
            tts=inference.TTS("cartesia/sonic-3"),
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
        return (
            f"The patient cooperates with the {examination_type} examination. "
            "Please describe what you would find based on the clinical scenario."
        )

    @function_tool
    async def end_consultation(self) -> str:
        """Called when the doctor indicates the consultation is ending.
        Triggers feedback generation.
        """
        logger.info("[PatientAgent] Doctor ended consultation via tool call")
        if not self._consultation_ended:
            self._consultation_ended = True
        return "Thank you doctor. The consultation has ended. Feedback is being generated."

    # ── Private Helpers ──────────────────────────────────────────

    async def _consultation_timer(self, duration: int) -> None:
        """Timer that ends the consultation after the specified duration."""
        logger.info(f"[PatientAgent] Consultation timer started: {duration}s")
        await asyncio.sleep(duration)
        if not self._consultation_ended:
            self._consultation_ended = True
            logger.info("[PatientAgent] Timer expired — ending consultation")
            # Tell the agent to wrap up
            self.session.generate_reply(
                instructions="The consultation time has ended. "
                "Thank the doctor and say goodbye naturally."
            )


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


def _build_case_brief(station_data: dict | None) -> str:
    """Build a case brief string from station data for feedback context."""
    if station_data:
        return (
            f"{station_data.get('patient_name', 'Unknown')}, "
            f"{station_data.get('patient_age', 'Unknown')}-year-old. "
            f"{station_data.get('candidate_instructions', '') or ''}"
        )
    return (
        "Clinical consultation case. Assess the candidate's "
        "data gathering, clinical management, and interpersonal skills."
    )


def _build_marking_criteria(station_data: dict | None) -> str | None:
    """Extract case-specific marking criteria from station data."""
    if not station_data:
        return None

    sections: list[str] = []
    if station_data.get("data_gathering"):
        sections.append(f"## Data Gathering Criteria\n{station_data['data_gathering']}")
    if station_data.get("clinical_management"):
        sections.append(f"## Clinical Management Criteria\n{station_data['clinical_management']}")
    if station_data.get("relating_to_others"):
        sections.append(f"## Interpersonal Skills Criteria\n{station_data['relating_to_others']}")

    return "\n\n".join(sections) if sections else None


async def _generate_and_save_feedback(
    db_repo: SessionRepository,
    db_session_id: str,
    transcript: list[dict],
    station_data: dict | None,
    user_id: str | None,
) -> None:
    """Async helper: generate feedback and persist to Supabase."""
    try:
        case_brief = _build_case_brief(station_data)
        marking_criteria = _build_marking_criteria(station_data)
        feedback = await generate_feedback(transcript, case_brief, marking_criteria)
        feedback_dict = feedback.model_dump()
        logger.info("Feedback generated successfully")

        db_repo.save_feedback(db_session_id, feedback_dict)

        # Update domain progress
        if user_id and station_data and station_data.get("domain_id"):
            overall_score = round(
                (
                    feedback_dict["data_gathering"]["score"]
                    + feedback_dict["clinical_management"]["score"]
                    + feedback_dict["interpersonal_skills"]["score"]
                )
                / 3
            )
            passed = all(
                feedback_dict[d]["score"] >= 60
                for d in ["data_gathering", "clinical_management", "interpersonal_skills"]
            )
            db_repo.update_domain_progress(
                user_id,
                station_data["domain_id"],
                overall_score,
                passed,
            )

    except Exception as e:
        logger.error(f"Feedback generation failed: {e}")


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

            # Create DB session if not pre-created
            if user_id and not db_session_id:
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
    session = AgentSession()

    await session.start(
        agent=agent,
        room=ctx.room,
    )

    # Make the agent speak first — fixes the "say hello twice" issue.
    # The patient greets, which masks STT init latency and signals readiness.
    opening = agent._station_data.get("station_script", "")
    if "Opening Sentence:" in opening:
        # Station has a defined opening — let the LLM paraphrase it
        await session.generate_reply(
            instructions="The doctor has just entered the room and greeted you. "
            "Deliver your opening line naturally — paraphrase it, don't recite it word-for-word. "
            "Keep it to 1-2 sentences maximum. "
            "IMPORTANT: Output ONLY spoken words. No stage directions, no parenthetical actions, "
            "no asterisks, no physical descriptions. Just what you would SAY out loud."
        )
    else:
        # No specific opening — generic patient greeting
        await session.generate_reply(
            instructions="The doctor has just entered the room. "
            "Greet them briefly and state why you're here in 1-2 sentences. "
            "Be natural and conversational. "
            "IMPORTANT: Output ONLY spoken words. No stage directions, no actions, no asterisks."
        )

    # Shared event so the entrypoint can wait for feedback to finish
    feedback_done = asyncio.Event()

    # Register close handler for transcript capture + feedback generation
    # NOTE: LiveKit `.on()` requires SYNC callbacks — use create_task inside
    @session.on("close")
    def on_close(ev: CloseEvent) -> None:
        logger.info(f"Session closed, reason: {ev.reason}")

        # Extract transcript from session history (with pre-recorded timestamps)
        transcript = _extract_transcript(session, agent._message_timestamps)
        logger.info(f"Extracted {len(transcript)} transcript entries")

        if not db_repo or not db_session_id:
            logger.warning("No DB repo/session — skipping persistence")
            feedback_done.set()
            return

        # Save transcript (sync DB calls)
        try:
            db_repo.save_transcript(db_session_id, transcript)
            db_repo.update_session_status(db_session_id, "processing")
        except Exception as e:
            logger.error(f"Failed to save transcript: {e}")

        async def _do_feedback() -> None:
            try:
                await _generate_and_save_feedback(
                    db_repo, db_session_id, transcript, station_data, user_id
                )
            finally:
                feedback_done.set()

        asyncio.create_task(_do_feedback())

    # Keep the entrypoint alive until session closes AND feedback finishes
    await feedback_done.wait()


if __name__ == "__main__":
    cli.run_app(server)
