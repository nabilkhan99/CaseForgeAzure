"""
Session Manager — ADK Gemini Live

Manages real-time voice consultation sessions using Google ADK's
bidirectional streaming (Runner.run_live + LiveRequestQueue).

Architecture:
  WebSocket ←→ [upstream task] → LiveRequestQueue → Runner.run_live() → [downstream task] → WebSocket
                                                                            ↓
                                                                    TranscriptAccumulation
                                                                    ConsultationTimer
                                                                    FeedbackGeneration
                                                                    DatabasePersistence
"""

import asyncio
import base64
import json
import logging
from datetime import datetime
from typing import Any

from fastapi import WebSocket
from google.adk.agents.live_request_queue import LiveRequestQueue
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

try:
    from ..ai_agents.patient import get_patient_agent
    from ..config import settings
    from ..db.session_repository import SessionRepository
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from clinical_master.ai_agents.patient import get_patient_agent
    from clinical_master.config import settings
    from clinical_master.db.session_repository import SessionRepository

logger = logging.getLogger(__name__)

APP_NAME = "clinical-master"


class ConsultationTimer:
    """Timer for consultation duration with hard cutoff."""

    def __init__(self, duration_seconds: int):
        self.duration = duration_seconds
        self.start_time: datetime | None = None
        self._task: asyncio.Task | None = None
        self._on_end_callback = None

    def start(self, on_end_callback):
        """Start the timer with a callback for when it expires."""
        self.start_time = datetime.now()
        self._on_end_callback = on_end_callback
        self._task = asyncio.create_task(self._countdown())

    async def _countdown(self):
        """Wait for duration then trigger callback."""
        await asyncio.sleep(self.duration)
        if self._on_end_callback:
            await self._on_end_callback()

    def remaining_seconds(self) -> int:
        """Get remaining seconds in consultation."""
        if not self.start_time:
            return self.duration
        elapsed = (datetime.now() - self.start_time).total_seconds()
        return max(0, int(self.duration - elapsed))

    def cancel(self):
        """Cancel the timer."""
        if self._task and not self._task.done():
            self._task.cancel()


class SessionManager:
    """
    Manages real-time voice consultation sessions using ADK Gemini Live.

    Each session creates:
      - An ADK Agent (patient persona from station data)
      - An ADK Runner + LiveRequestQueue for bidirectional streaming
      - A ConsultationTimer for enforcing time limits
      - Transcript accumulation and database persistence
    """

    def __init__(self):
        # ADK session service (in-memory — each consultation is independent)
        self.session_service = InMemorySessionService()

        # Per-session state
        self.websockets: dict[str, WebSocket] = {}
        self.transcripts: dict[str, list[dict]] = {}
        self.timers: dict[str, ConsultationTimer] = {}
        self.feedback_results: dict[str, dict] = {}
        self.feedback_generating: set[str] = set()
        self.live_queues: dict[str, LiveRequestQueue] = {}
        self._gather_tasks: dict[str, asyncio.Task] = {}
        # Track if session ended to prevent double end
        self._ended: set[str] = set()

        # Database session info: { session_id: { db_session_id, user_id, station_id, station_data } }
        self.db_sessions: dict[str, dict] = {}

        # Delta accumulator buffers for streaming transcripts
        self.delta_buffers: dict[str, dict[str, str]] = {}

        # Initialize repository (lazy-loaded)
        self._db_repo: SessionRepository | None = None

    @property
    def db_repo(self) -> SessionRepository | None:
        """Lazy-load database repository."""
        if self._db_repo is None:
            try:
                self._db_repo = SessionRepository()
            except Exception as e:
                logger.warning(f"Could not initialize database repository: {e}")
        return self._db_repo

    async def connect(self, websocket: WebSocket, session_id: str,
                      user_id: str | None = None, station_id: str | None = None):
        """
        Accept WebSocket connection, initialise ADK session, and run the
        bidirectional streaming loop until the consultation ends or
        the client disconnects.

        This method blocks for the entire duration of the consultation.
        """
        await websocket.accept()
        self.websockets[session_id] = websocket
        self.transcripts[session_id] = []
        self.delta_buffers[session_id] = {"user": "", "assistant": ""}

        logger.info(f"Session {session_id}: Connection accepted")

        # ── Load station & create DB record ──────────────────────
        station_data = None
        db_session_id = None
        if self.db_repo:
            try:
                if station_id:
                    station_data = self.db_repo.get_station(station_id)
                else:
                    station_data = self.db_repo.get_first_station()

                if station_data:
                    logger.info(f"Session {session_id}: Loaded station '{station_data.get('title')}'")
                    if user_id:
                        db_session = self.db_repo.create_session(user_id, station_data['id'])
                        if db_session:
                            db_session_id = db_session['id']
                            logger.info(f"Session {session_id}: Created DB session {db_session_id}")
                else:
                    logger.warning(f"Session {session_id}: No station found in database")
            except Exception as e:
                logger.error(f"Session {session_id}: Database error - {e}")

        self.db_sessions[session_id] = {
            'db_session_id': db_session_id,
            'user_id': user_id,
            'station_id': station_data['id'] if station_data else None,
            'station_data': station_data,
        }

        # ── Create ADK Agent + Runner ────────────────────────────
        agent = get_patient_agent(station_data)
        runner = Runner(
            app_name=APP_NAME,
            agent=agent,
            session_service=self.session_service,
        )

        # Ensure ADK session exists
        adk_user_id = user_id or "anonymous"
        adk_session = await self.session_service.get_session(
            app_name=APP_NAME, user_id=adk_user_id, session_id=session_id,
        )
        if not adk_session:
            await self.session_service.create_session(
                app_name=APP_NAME, user_id=adk_user_id, session_id=session_id,
            )

        live_request_queue = LiveRequestQueue()
        self.live_queues[session_id] = live_request_queue

        # ── RunConfig for native audio model ─────────────────────
        run_config = RunConfig(
            streaming_mode=StreamingMode.BIDI,
            response_modalities=["AUDIO"],
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=settings.DEFAULT_VOICE,
                    )
                )
            ),
        )

        # ── Start consultation timer ─────────────────────────────
        duration = settings.CONSULTATION_DURATION_SECONDS
        if station_data and station_data.get('consultation_duration_seconds'):
            duration = station_data['consultation_duration_seconds']

        timer = ConsultationTimer(duration)
        timer.start(lambda: self._on_timer_end(session_id))
        self.timers[session_id] = timer

        # Notify client that session is ready
        try:
            await websocket.send_text(json.dumps({
                "type": "session_started",
                "duration_seconds": duration,
            }))
        except Exception:
            pass

        logger.info(f"Session {session_id}: ADK live session started (model={agent.model}, voice={settings.DEFAULT_VOICE}, duration={duration}s)")

        # ── Concurrent upstream / downstream tasks ───────────────
        async def upstream_task():
            """Forward client WebSocket audio/text to ADK via LiveRequestQueue."""
            try:
                while True:
                    message = await websocket.receive()

                    if "bytes" in message:
                        audio_data = message["bytes"]
                        audio_blob = types.Blob(
                            mime_type="audio/pcm;rate=16000",
                            data=audio_data,
                        )
                        live_request_queue.send_realtime(audio_blob)

                    elif "text" in message:
                        text_data = message["text"]
                        try:
                            json_message = json.loads(text_data)
                            msg_type = json_message.get("type", "")

                            if msg_type == "end_consultation":
                                logger.info(f"Session {session_id}: Client requested end")
                                await self._on_timer_end(session_id)
                                break

                            elif msg_type == "text":
                                content = types.Content(
                                    parts=[types.Part(text=json_message.get("text", ""))]
                                )
                                live_request_queue.send_content(content)
                        except json.JSONDecodeError:
                            logger.warning(f"Session {session_id}: Invalid JSON from client")

            except Exception as e:
                if "disconnect" not in str(e).lower():
                    logger.error(f"Session {session_id}: Upstream error - {e}")

        async def downstream_task():
            """Process ADK events and forward to client WebSocket."""
            try:
                async for event in runner.run_live(
                    user_id=adk_user_id,
                    session_id=session_id,
                    live_request_queue=live_request_queue,
                    run_config=run_config,
                ):
                    await self._handle_adk_event(session_id, event, websocket)
            except Exception as e:
                if "disconnect" not in str(e).lower():
                    logger.error(f"Session {session_id}: Downstream error - {e}")

        # Run both tasks concurrently — exception in either cancels both
        try:
            gather_task = asyncio.gather(upstream_task(), downstream_task())
            self._gather_tasks[session_id] = gather_task
            await gather_task
        except Exception as e:
            if "disconnect" not in str(e).lower():
                logger.error(f"Session {session_id}: Session loop error - {e}")
        finally:
            live_request_queue.close()
            self.live_queues.pop(session_id, None)
            self._gather_tasks.pop(session_id, None)

    async def disconnect(self, session_id: str):
        """Clean up session resources."""
        transcript = self.transcripts.get(session_id, [])
        logger.info(f"Session {session_id}: Disconnecting (transcript={len(transcript)} items)")

        # Cancel timer
        if session_id in self.timers:
            self.timers[session_id].cancel()
            del self.timers[session_id]

        # Close live queue if still open
        queue = self.live_queues.pop(session_id, None)
        if queue:
            queue.close()

        # Cancel gather task
        task = self._gather_tasks.pop(session_id, None)
        if task and not task.done():
            task.cancel()

        # Clean up session data
        self.websockets.pop(session_id, None)
        self.delta_buffers.pop(session_id, None)

    # ── ADK Event Handling ───────────────────────────────────────
    async def _handle_adk_event(self, session_id: str, event, websocket: WebSocket):
        """
        Process a single ADK event and forward relevant data to the client.

        ADK events are generic; we map them to the Clinical Master
        frontend event types:
          - audio            →  base64 audio chunk for playback
          - transcript_delta →  incremental transcript text
          - audio_interrupted → signal to clear playback buffer
          - history_added    →  completed transcript entry
        """
        try:
            # Check for content parts in the event
            if hasattr(event, 'content') and event.content and hasattr(event.content, 'parts'):
                for part in event.content.parts:
                    # Audio data from model
                    if hasattr(part, 'inline_data') and part.inline_data:
                        audio_b64 = base64.b64encode(part.inline_data.data).decode("utf-8")
                        await self._ws_send(websocket, {
                            "type": "audio",
                            "audio": audio_b64,
                        })

                    # Text from model (assistant transcript)
                    elif hasattr(part, 'text') and part.text:
                        text = part.text
                        self.delta_buffers.setdefault(session_id, {"user": "", "assistant": ""})
                        self.delta_buffers[session_id]["assistant"] += text
                        await self._ws_send(websocket, {
                            "type": "transcript_delta",
                            "item": {"role": "assistant", "content": text},
                        })

            # Transcription of user's audio input
            if hasattr(event, 'transcription') and event.transcription:
                transcription = event.transcription
                if hasattr(transcription, 'text') and transcription.text:
                    user_text = transcription.text
                    logger.info(f"Session {session_id}: User transcription: {user_text[:80]}...")
                    self.transcripts.setdefault(session_id, []).append({
                        "role": "user",
                        "content": user_text,
                        "timestamp": datetime.now().isoformat(),
                    })
                    await self._ws_send(websocket, {
                        "type": "transcript_delta",
                        "item": {"role": "user", "content": user_text},
                    })

            # Server content with model turn (check for model_turn audio transcription)
            if hasattr(event, 'server_content') and event.server_content:
                sc = event.server_content
                # Model turn contains output audio transcription
                if hasattr(sc, 'model_turn') and sc.model_turn:
                    for part in (sc.model_turn.parts or []):
                        if hasattr(part, 'inline_data') and part.inline_data:
                            audio_b64 = base64.b64encode(part.inline_data.data).decode("utf-8")
                            await self._ws_send(websocket, {
                                "type": "audio",
                                "audio": audio_b64,
                            })
                        elif hasattr(part, 'text') and part.text:
                            self.delta_buffers.setdefault(session_id, {"user": "", "assistant": ""})
                            self.delta_buffers[session_id]["assistant"] += part.text
                            await self._ws_send(websocket, {
                                "type": "transcript_delta",
                                "item": {"role": "assistant", "content": part.text},
                            })

                # Output audio transcription (separate from inline parts)
                if hasattr(sc, 'output_transcription') and sc.output_transcription:
                    t = sc.output_transcription
                    if hasattr(t, 'text') and t.text:
                        self.delta_buffers.setdefault(session_id, {"user": "", "assistant": ""})
                        self.delta_buffers[session_id]["assistant"] += t.text
                        await self._ws_send(websocket, {
                            "type": "transcript_delta",
                            "item": {"role": "assistant", "content": t.text},
                        })

                # Input transcription (user side from server)
                if hasattr(sc, 'input_transcription') and sc.input_transcription:
                    t = sc.input_transcription
                    if hasattr(t, 'text') and t.text:
                        logger.info(f"Session {session_id}: Input transcription: {t.text[:80]}...")
                        self.transcripts.setdefault(session_id, []).append({
                            "role": "user",
                            "content": t.text,
                            "timestamp": datetime.now().isoformat(),
                        })
                        await self._ws_send(websocket, {
                            "type": "transcript_delta",
                            "item": {"role": "user", "content": t.text},
                        })

                # Turn complete — flush assistant buffer
                if hasattr(sc, 'turn_complete') and sc.turn_complete:
                    self._flush_delta_buffer(session_id, "assistant")
                    await self._ws_send(websocket, {
                        "type": "history_added",
                        "item": {"role": "assistant", "content": "[turn complete]"},
                    })

                # Interrupted — signal client to clear audio
                if hasattr(sc, 'interrupted') and sc.interrupted:
                    self._flush_delta_buffer(session_id, "assistant")
                    await self._ws_send(websocket, {
                        "type": "audio_interrupted",
                    })

            # Also check top-level interrupted flag
            if hasattr(event, 'interrupted') and event.interrupted:
                self._flush_delta_buffer(session_id, "assistant")
                await self._ws_send(websocket, {
                    "type": "audio_interrupted",
                })

            # Check for partial result / turn_complete at event level
            if hasattr(event, 'turn_complete') and event.turn_complete:
                self._flush_delta_buffer(session_id, "assistant")

        except Exception as e:
            if "disconnect" not in str(e).lower():
                logger.error(f"Session {session_id}: Error handling ADK event - {e}")

    async def _ws_send(self, websocket: WebSocket, data: dict):
        """Send JSON to WebSocket with error handling."""
        try:
            await websocket.send_text(json.dumps(data))
        except Exception:
            pass

    # ── Transcript buffer management ─────────────────────────────

    def _flush_delta_buffer(self, session_id: str, role: str):
        """Flush accumulated delta buffer for a role to transcripts list."""
        if session_id not in self.delta_buffers:
            return

        buffer = self.delta_buffers[session_id]
        content = buffer.get(role, "").strip()

        if content:
            logger.info(f"Session {session_id}: Flushing {role} buffer: {content[:50]}...")
            self.transcripts.setdefault(session_id, []).append({
                "role": role,
                "content": content,
                "timestamp": datetime.now().isoformat(),
            })
            buffer[role] = ""

    def _flush_all_delta_buffers(self, session_id: str):
        """Flush all remaining delta buffers before saving."""
        self._flush_delta_buffer(session_id, "user")
        self._flush_delta_buffer(session_id, "assistant")

    # ── Timer & Consultation End ─────────────────────────────────

    async def _on_timer_end(self, session_id: str):
        """Called when timer expires or consultation ends manually."""
        # Guard against double invocation
        if session_id in self._ended:
            return
        self._ended.add(session_id)

        logger.info(f"Session {session_id}: Consultation ended")

        websocket = self.websockets.get(session_id)
        if websocket:
            await self._ws_send(websocket, {
                "type": "consultation_ended",
                "message": "Time's up! Generating feedback...",
            })

        # Cancel timer
        if session_id in self.timers:
            self.timers[session_id].cancel()

        # Flush any remaining delta buffers before saving
        self._flush_all_delta_buffers(session_id)

        # Save transcript to database
        transcript = self.transcripts.get(session_id, [])
        logger.info(f"Session {session_id}: Transcript has {len(transcript)} items")
        for i, t in enumerate(transcript[:5]):
            logger.info(f"Session {session_id}: Transcript[{i}] role={t.get('role')}, content={t.get('content', '')[:50]}...")

        db_info = self.db_sessions.get(session_id, {})
        if db_info.get('db_session_id') and self.db_repo:
            try:
                self.db_repo.save_transcript(db_info['db_session_id'], transcript)
                self.db_repo.update_session_status(db_info['db_session_id'], 'processing')
            except Exception as e:
                logger.error(f"Session {session_id}: Failed to save transcript - {e}")

        # Trigger async feedback generation
        asyncio.create_task(self._generate_feedback(session_id, transcript))

        # Close the live queue to end streaming
        queue = self.live_queues.get(session_id)
        if queue:
            queue.close()

    # ── Feedback Generation ──────────────────────────────────────

    async def _generate_feedback(self, session_id: str, transcript: list[dict]):
        """Generate feedback asynchronously."""
        # Guard against duplicate generation
        if session_id in self.feedback_generating:
            logger.info(f"Session {session_id}: Feedback already being generated, skipping")
            return
        if session_id in self.feedback_results:
            logger.info(f"Session {session_id}: Feedback already exists, skipping")
            return
        self.feedback_generating.add(session_id)

        try:
            from ..ai_agents.feedback import generate_feedback
        except ImportError:
            from clinical_master.ai_agents.feedback import generate_feedback

        try:
            logger.info(f"Session {session_id}: Generating feedback...")

            # Get case brief from station data if available
            db_info = self.db_sessions.get(session_id, {})
            station_data = db_info.get('station_data', {})

            if station_data:
                case_brief = (
                    f"{station_data.get('patient_name', 'Unknown')}, "
                    f"{station_data.get('patient_age', 'Unknown')}-year-old. "
                    f"{station_data.get('candidate_instructions', '')[:500]}..."
                )
            else:
                case_brief = (
                    "Clinical consultation case. Assess the candidate's "
                    "data gathering, clinical management, and interpersonal skills."
                )

            feedback = await generate_feedback(transcript, case_brief)

            # Store feedback locally
            feedback_dict = feedback.model_dump()
            self.feedback_results[session_id] = feedback_dict

            logger.info(f"Session {session_id}: Feedback generated")

            # Save feedback to database
            db_info = self.db_sessions.get(session_id, {})
            if db_info.get('db_session_id') and self.db_repo:
                try:
                    db_feedback = {
                        'data_gathering': {
                            'score': feedback_dict.get('data_gathering', {}).get('score', 0),
                            'strengths': feedback_dict.get('data_gathering', {}).get('strengths', []),
                            'improvements': feedback_dict.get('data_gathering', {}).get('improvements', []),
                        },
                        'clinical_management': {
                            'score': feedback_dict.get('clinical_management', {}).get('score', 0),
                            'strengths': feedback_dict.get('clinical_management', {}).get('strengths', []),
                            'improvements': feedback_dict.get('clinical_management', {}).get('improvements', []),
                        },
                        'interpersonal_skills': {
                            'score': feedback_dict.get('interpersonal_skills', {}).get('score', 0),
                            'strengths': feedback_dict.get('interpersonal_skills', {}).get('strengths', []),
                            'improvements': feedback_dict.get('interpersonal_skills', {}).get('improvements', []),
                        },
                        'overall_summary': feedback_dict.get('overall_summary', ''),
                        'key_learning_points': feedback_dict.get('key_learning_points', []),
                    }
                    self.db_repo.save_feedback(db_info['db_session_id'], db_feedback)

                    # Update domain progress if station has a domain
                    station_data = db_info.get('station_data', {})
                    if db_info.get('user_id') and station_data.get('domain_id'):
                        overall_score = round((
                            db_feedback['data_gathering']['score'] +
                            db_feedback['clinical_management']['score'] +
                            db_feedback['interpersonal_skills']['score']
                        ) / 3)
                        passed = all([
                            db_feedback['data_gathering']['score'] >= 60,
                            db_feedback['clinical_management']['score'] >= 60,
                            db_feedback['interpersonal_skills']['score'] >= 60,
                        ])
                        self.db_repo.update_domain_progress(
                            db_info['user_id'],
                            station_data['domain_id'],
                            overall_score,
                            passed,
                        )
                except Exception as e:
                    logger.error(f"Session {session_id}: Failed to save feedback to database - {e}")

            # Try to notify client if still connected
            websocket = self.websockets.get(session_id)
            if websocket:
                await self._ws_send(websocket, {
                    "type": "feedback_ready",
                    "feedback": feedback.model_dump(),
                })

        except Exception as e:
            logger.error(f"Session {session_id}: Feedback generation failed - {e}")
            self.feedback_results[session_id] = {
                "error": str(e),
                "transcript": transcript,
            }

    # ── Public helpers ───────────────────────────────────────────

    def get_db_session_id(self, session_id: str) -> str | None:
        """Resolve WebSocket session_id to database session_id."""
        db_info = self.db_sessions.get(session_id, {})
        return db_info.get('db_session_id')

    def get_feedback(self, session_id: str) -> dict | None:
        """Get feedback for a session if available."""
        return self.feedback_results.get(session_id)
