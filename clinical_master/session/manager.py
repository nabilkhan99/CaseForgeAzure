"""
Session Manager

Manages WebSocket sessions, realtime connections to Azure OpenAI,
transcript capture, and timer enforcement.
"""

import asyncio
import base64
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import WebSocket

from agents.realtime import RealtimeRunner, RealtimeSession

# Handle imports for both package and script modes
try:
    from ..config import settings
    from ..ai_agents.patient import get_patient_agent
    from ..db import SessionRepository
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from clinical_master.config import settings
    from clinical_master.ai_agents.patient import get_patient_agent
    from clinical_master.db import SessionRepository


# ── Azure GA compatibility patch ──────────────────────────────────────────
# The openai-agents SDK was built against the *preview* Realtime API.
# Azure's GA API introduces differences that cause pydantic validation
# failures. This patch normalises raw events before the SDK validates them:
#
#  1. Model names: Azure returns e.g. "gpt-realtime-2025-08-28" which isn't
#     in the SDK's literal list. We map it to "gpt-4o-realtime-preview".
#
#  2. New event types: GA adds events like "conversation.item.done" that
#     don't exist in the SDK's event union. We skip them gracefully.
#
#  3. Content type renaming: GA uses "output_audio" where the preview API
#     used "audio". We rewrite it back to "audio" before validation.

_KNOWN_MODELS = {
    "gpt-4o-realtime-preview", "gpt-4o-realtime-preview-2024-10-01",
    "gpt-4o-realtime-preview-2024-12-17", "gpt-4o-realtime-preview-2025-06-03",
    "gpt-4o-mini-realtime-preview", "gpt-4o-mini-realtime-preview-2024-12-17",
}

# Event types the SDK can actually validate (from its tagged union).
# If an event isn't in this set we skip it to avoid validation crashes.
_SDK_KNOWN_EVENTS = {
    "conversation.created", "conversation.item.created",
    "conversation.item.deleted",
    "conversation.item.input_audio_transcription.completed",
    "conversation.item.input_audio_transcription.delta",
    "conversation.item.input_audio_transcription.failed",
    "conversation.item.retrieved", "conversation.item.truncated",
    "error",
    "input_audio_buffer.cleared", "input_audio_buffer.committed",
    "input_audio_buffer.speech_started", "input_audio_buffer.speech_stopped",
    "rate_limits.updated",
    "response.audio.delta", "response.audio.done",
    "response.audio_transcript.delta", "response.audio_transcript.done",
    "response.content_part.added", "response.content_part.done",
    "response.created", "response.done",
    "response.function_call_arguments.delta",
    "response.function_call_arguments.done",
    "response.output_item.added", "response.output_item.done",
    "response.text.delta", "response.text.done",
    "session.created", "session.updated",
    "transcription_session.updated",
    "output_audio_buffer.started", "output_audio_buffer.stopped",
    "output_audio_buffer.cleared",
    "input_audio_buffer.timeout_triggered",
}

# GA content types that need mapping to preview equivalents
_CONTENT_TYPE_MAP = {
    "output_audio": "audio",
    "output_text": "text",
}

# GA event types that were renamed from the preview API.
# We rewrite them back so the SDK can process them normally.
_EVENT_TYPE_MAP = {
    "response.output_audio.delta":              "response.audio.delta",
    "response.output_audio.done":               "response.audio.done",
    "response.output_audio_transcript.delta":    "response.audio_transcript.delta",
    "response.output_audio_transcript.done":     "response.audio_transcript.done",
    "conversation.item.added":                   "conversation.item.created",
}

_AZURE_PATCH_APPLIED = False


def _normalise_content_types(obj):
    """Recursively rewrite GA content types (output_audio → audio) in dicts/lists."""
    if isinstance(obj, dict):
        if "type" in obj and obj["type"] in _CONTENT_TYPE_MAP:
            obj["type"] = _CONTENT_TYPE_MAP[obj["type"]]
        for v in obj.values():
            _normalise_content_types(v)
    elif isinstance(obj, list):
        for item in obj:
            _normalise_content_types(item)


def _apply_azure_compat_patch():
    """Monkey-patch the SDK to accept Azure GA API responses."""
    global _AZURE_PATCH_APPLIED
    if _AZURE_PATCH_APPLIED:
        return
    _AZURE_PATCH_APPLIED = True

    try:
        from agents.realtime.openai_realtime import OpenAIRealtimeWebSocketModel

        original_handle = OpenAIRealtimeWebSocketModel._handle_ws_event

        async def _patched_handle_ws_event(self, event):
            if not isinstance(event, dict):
                return await original_handle(self, event)

            event_type = event.get("type", "")

            # 0. Rewrite GA event types → preview equivalents
            if event_type in _EVENT_TYPE_MAP:
                new_type = _EVENT_TYPE_MAP[event_type]
                logger.info(f"Azure compat: rewriting event '{event_type}' → '{new_type}'")
                event["type"] = new_type
                event_type = new_type

            # 1. Skip event types the SDK doesn't know about
            if event_type and event_type not in _SDK_KNOWN_EVENTS:
                logger.info(f"Azure compat: skipping unknown event type '{event_type}'")
                return

            # 2. Normalise session.created / session.updated
            if event_type in ("session.created", "session.updated"):
                session = event.get("session", {})
                # 2a. Model name
                model = session.get("model", "")
                if model and model not in _KNOWN_MODELS:
                    session["model"] = "gpt-4o-realtime-preview"
                    logger.info(f"Azure compat: normalised model '{model}' → 'gpt-4o-realtime-preview'")
                # 2b. Audio format — GA uses nested audio.output.format instead of
                #     output_audio_format. Ensure the SDK field is populated so the
                #     ModelAudioTracker doesn't crash with missing _format.
                if not session.get("output_audio_format"):
                    session["output_audio_format"] = "pcm16"
                    logger.info("Azure compat: set default output_audio_format='pcm16'")

            # 3. Normalise GA content types (output_audio → audio, etc.)
            _normalise_content_types(event)

            return await original_handle(self, event)

        OpenAIRealtimeWebSocketModel._handle_ws_event = _patched_handle_ws_event
        logger.info("Azure OpenAI GA compatibility patch applied")
    except Exception as e:
        logger.warning(f"Failed to apply Azure compat patch: {e}")

logger = logging.getLogger(__name__)


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
    Manages realtime voice sessions.
    
    Follows the pattern from openai-agents-python/examples/realtime/app/server.py
    """
    
    def __init__(self):
        _apply_azure_compat_patch()
        self.active_sessions: dict[str, RealtimeSession] = {}
        self.session_contexts: dict[str, Any] = {}
        self.websockets: dict[str, WebSocket] = {}
        self.transcripts: dict[str, list[dict]] = {}
        self.timers: dict[str, ConsultationTimer] = {}
        self.feedback_results: dict[str, dict] = {}
        # Database session info: { session_id: { db_session_id, user_id, station_id, station_data } }
        self.db_sessions: dict[str, dict] = {}
        # Track seen item_ids per session for deduplication (SDK pattern)
        self.seen_item_ids: dict[str, set[str]] = {}
        # Map item_id to transcript content for updates
        self.item_transcripts: dict[str, dict[str, dict]] = {}
        # Delta accumulator buffers for streaming transcripts
        self.delta_buffers: dict[str, dict[str, str]] = {}
        # Initialize repository (will be lazy-loaded to avoid startup errors)
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
    
    async def connect(self, websocket: WebSocket, session_id: str, user_id: str | None = None, station_id: str | None = None):
        """
        Accept WebSocket connection and start realtime session.
        
        Args:
            websocket: WebSocket connection
            session_id: Client session identifier
            user_id: Authenticated user's ID (optional, for database persistence)
            station_id: Station to load (optional, defaults to first available station)
        """
        await websocket.accept()
        self.websockets[session_id] = websocket
        self.transcripts[session_id] = []
        self.seen_item_ids[session_id] = set()
        self.item_transcripts[session_id] = {}
        self.delta_buffers[session_id] = {"user": "", "assistant": ""}
        
        logger.info(f"Session {session_id}: Connection accepted")
        
        # Load station and create database session if repository is available
        station_data = None
        db_session_id = None
        if self.db_repo:
            try:
                # Get station from database
                if station_id:
                    station_data = self.db_repo.get_station(station_id)
                else:
                    station_data = self.db_repo.get_first_station()
                
                if station_data:
                    logger.info(f"Session {session_id}: Loaded station '{station_data.get('title')}'")
                    
                    # Create database session record if user is authenticated
                    if user_id:
                        db_session = self.db_repo.create_session(user_id, station_data['id'])
                        if db_session:
                            db_session_id = db_session['id']
                            logger.info(f"Session {session_id}: Created DB session {db_session_id}")
                else:
                    logger.warning(f"Session {session_id}: No station found in database")
            except Exception as e:
                logger.error(f"Session {session_id}: Database error - {e}")
        
        # Store database session info
        self.db_sessions[session_id] = {
            'db_session_id': db_session_id,
            'user_id': user_id,
            'station_id': station_data['id'] if station_data else None,
            'station_data': station_data
        }
        
        # Get patient agent with station-specific prompt
        agent = get_patient_agent(station_data)
        runner = RealtimeRunner(agent)
        
        # Build Azure OpenAI WebSocket URL for Realtime API
        # GA Format: wss://{resource}.openai.azure.com/openai/v1/realtime?model={deployment}
        # (No api-version needed for GA models like gpt-realtime)
        azure_endpoint = settings.AZURE_OPENAI_ENDPOINT.rstrip('/')
        # Convert https:// to wss://
        if azure_endpoint.startswith('https://'):
            ws_endpoint = azure_endpoint.replace('https://', 'wss://')
        elif azure_endpoint.startswith('http://'):
            ws_endpoint = azure_endpoint.replace('http://', 'ws://')
        else:
            ws_endpoint = f"wss://{azure_endpoint}"
        
        # Use GA endpoint format (no api-version, model as query param)
        azure_url = (
            f"{ws_endpoint}/openai/v1/realtime"
            f"?model={settings.AZURE_OPENAI_REALTIME_DEPLOYMENT}"
        )
        
        logger.info(f"Session {session_id}: Connecting to Azure OpenAI at {azure_url}")
        
        # Configure for Azure OpenAI with custom URL and headers
        model_config = {
            "url": azure_url,
            "headers": {
                "api-key": settings.AZURE_OPENAI_API_KEY,
            },
            "initial_model_settings": {
                "modalities": ["audio"],
                "voice": settings.DEFAULT_VOICE,
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "input_audio_transcription": {
                    "model": "whisper-1",
                },
                "turn_detection": {
                    "type": settings.TURN_DETECTION_TYPE,
                    "create_response": True,
                    "interrupt_response": True,
                },
                "input_audio_noise_reduction": {
                    "type": settings.NOISE_REDUCTION_TYPE
                },
            },
        }
        
        try:
            session_context = await runner.run(model_config=model_config)
            session = await session_context.__aenter__()
            self.active_sessions[session_id] = session
            self.session_contexts[session_id] = session_context
            
            logger.info(f"Session {session_id}: Realtime session started")
            
            # Use station-specific or global consultation duration
            duration = settings.CONSULTATION_DURATION_SECONDS
            if station_data and station_data.get('consultation_duration_seconds'):
                duration = station_data['consultation_duration_seconds']
            
            # Start timer
            timer = ConsultationTimer(duration)
            timer.start(lambda: self._on_timer_end(session_id))
            self.timers[session_id] = timer
            
            # Notify client that session is ready
            await websocket.send_text(json.dumps({
                "type": "session_started",
                "duration_seconds": duration,
            }))
            
            # Start event processing
            asyncio.create_task(self._process_events(session_id))
            
        except Exception as e:
            logger.error(f"Session {session_id}: Failed to start - {e}")
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": f"Failed to start session: {str(e)}",
            }))
            await websocket.close()
    
    async def disconnect(self, session_id: str):
        """Clean up session resources."""
        logger.info(f"Session {session_id}: Disconnecting")
        
        # Cancel timer
        if session_id in self.timers:
            self.timers[session_id].cancel()
            del self.timers[session_id]
        
        # Close realtime session
        context = self.session_contexts.pop(session_id, None)
        if context:
            try:
                await context.__aexit__(None, None, None)
            except Exception as e:
                logger.error(f"Session {session_id}: Error closing context - {e}")
        
        # Clean up all session data
        self.active_sessions.pop(session_id, None)
        self.websockets.pop(session_id, None)
        self.seen_item_ids.pop(session_id, None)
        self.item_transcripts.pop(session_id, None)
        self.delta_buffers.pop(session_id, None)
    
    async def send_audio(self, session_id: str, audio_bytes: bytes):
        """Send audio data to the realtime session."""
        session = self.active_sessions.get(session_id)
        if session:
            await session.send_audio(audio_bytes)
    
    async def interrupt(self, session_id: str):
        """Interrupt current model response."""
        session = self.active_sessions.get(session_id)
        if session:
            await session.interrupt()
    
    async def end_consultation(self, session_id: str):
        """End the consultation early (before timer)."""
        await self._on_timer_end(session_id)
    
    def _flush_delta_buffer(self, session_id: str, role: str):
        """Flush accumulated delta buffer for a role to transcripts list."""
        if session_id not in self.delta_buffers:
            return
        
        buffer = self.delta_buffers[session_id]
        content = buffer.get(role, "").strip()
        
        if content:
            logger.info(f"Session {session_id}: Flushing {role} buffer: {content[:50]}...")
            self.transcripts[session_id].append({
                "role": role,
                "content": content,
                "timestamp": datetime.now().isoformat(),
            })
            buffer[role] = ""
    
    def _flush_all_delta_buffers(self, session_id: str):
        """Flush all remaining delta buffers before saving."""
        self._flush_delta_buffer(session_id, "user")
        self._flush_delta_buffer(session_id, "assistant")
    
    async def _on_timer_end(self, session_id: str):
        """Called when timer expires or consultation ends."""
        logger.info(f"Session {session_id}: Consultation ended")
        
        websocket = self.websockets.get(session_id)
        if websocket:
            await websocket.send_text(json.dumps({
                "type": "consultation_ended",
                "message": "Time's up! Generating feedback...",
            }))
        
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
        
        # Disconnect the realtime session
        await self.disconnect(session_id)
    
    async def _process_events(self, session_id: str):
        """Process events from the realtime session."""
        try:
            session = self.active_sessions.get(session_id)
            websocket = self.websockets.get(session_id)
            
            if not session or not websocket:
                return
            
            async for event in session:
                await self._handle_event(session_id, event, websocket)
                
        except Exception as e:
            logger.error(f"Session {session_id}: Error processing events - {e}")
    
    async def _handle_event(self, session_id: str, event, websocket: WebSocket):
        """Handle a single event from the realtime session."""
        event_data: dict[str, Any] = {"type": event.type}
        
        if event.type == "audio":
            # Send audio to browser
            event_data["audio"] = base64.b64encode(event.audio.data).decode("utf-8")
            logger.info(f"Session {session_id}: Audio chunk {len(event.audio.data)} bytes")
            
        elif event.type == "audio_interrupted":
            # Audio was interrupted by user speech
            event_data["type"] = "audio_interrupted"
            
        elif event.type == "history_added":
            # Single new item added (RealtimeHistoryAdded — has .item)
            item = event.item
            await self._process_history_item(session_id, item, websocket)
            return
        
        elif event.type == "history_updated":
            # Full history list (RealtimeHistoryUpdated — .history is list[RealtimeItem])
            for item in event.history:
                await self._process_history_item(session_id, item, websocket)
            return
        
        elif event.type == "audio_transcript_delta":
            # Streaming transcript delta from the model
            delta = getattr(event, "delta", "")
            if delta:
                self.delta_buffers.setdefault(session_id, {"user": "", "assistant": ""})
                self.delta_buffers[session_id]["assistant"] += delta
                
                event_data = {
                    "type": "transcript_delta",
                    "item": {"role": "assistant", "content": delta}
                }
                try:
                    await websocket.send_text(json.dumps(event_data))
                except Exception:
                    pass
            return
            
        elif event.type == "input_audio_transcript_delta":
            # Streaming user transcript delta (from whisper-1)
            delta = getattr(event, "delta", "")
            if delta:
                self.delta_buffers.setdefault(session_id, {"user": "", "assistant": ""})
                self.delta_buffers[session_id]["user"] += delta
                
                event_data = {
                    "type": "transcript_delta",
                    "item": {"role": "user", "content": delta}
                }
                try:
                    await websocket.send_text(json.dumps(event_data))
                except Exception:
                    pass
            return
        
        else:
            # Other events (e.g. tool calls, errors) - skip for now
            return
        
        # Send event to client
        await websocket.send_text(json.dumps(event_data))
    
    async def _process_history_item(self, session_id: str, item, websocket: WebSocket):
        """Process a single RealtimeItem from history events."""
        item_id = getattr(item, "item_id", None)
        role = getattr(item, "role", None)
        
        if not item_id or not role:
            return
        
        # Check if already processed
        if item_id in self.seen_item_ids.get(session_id, set()):
            # Check for transcript updates (e.g. whisper-1 filling in user audio)
            new_content = self._extract_transcript_from_item(item)
            prev = self.item_transcripts.get(session_id, {}).get(item_id, {})
            if new_content and new_content != prev.get("content"):
                # Updated transcript (e.g. whisper-1 result arrived)
                self.item_transcripts[session_id][item_id] = {
                    "role": role, "content": new_content
                }
                # Update in-place in transcript list
                for t in self.transcripts.get(session_id, []):
                    if t.get("item_id") == item_id:
                        t["content"] = new_content
                        break
                
                event_data = {
                    "type": "transcript_update",
                    "item": {"role": role, "content": new_content}
                }
                try:
                    await websocket.send_text(json.dumps(event_data))
                except Exception:
                    pass
            return
        
        self.seen_item_ids[session_id].add(item_id)
        
        content = self._extract_transcript_from_item(item)
        if not content:
            content = self._extract_content(item)
        
        if content:
            self.item_transcripts[session_id][item_id] = {
                "role": role, "content": content
            }
            self.transcripts[session_id].append({
                "role": role,
                "content": content,
                "timestamp": datetime.now().isoformat(),
                "item_id": item_id,
            })
            
            event_data = {
                "type": "history_added",
                "item": {"role": role, "content": content}
            }
            try:
                await websocket.send_text(json.dumps(event_data))
            except Exception:
                pass
    
    def _extract_content(self, item) -> str:
        """Extract text content from a history item."""
        content = getattr(item, "content", None)
        if not content:
            return ""
        
        if isinstance(content, str):
            return content
        
        if isinstance(content, list):
            texts = []
            for part in content:
                if isinstance(part, dict):
                    if part.get("type") == "text":
                        text = part.get("text")
                        if text:
                            texts.append(text)
                    elif part.get("type") == "transcript":
                        transcript = part.get("transcript")
                        if transcript:
                            texts.append(transcript)
                elif hasattr(part, "text") and part.text:
                    texts.append(part.text)
                elif hasattr(part, "transcript") and part.transcript:
                    texts.append(part.transcript)
            return " ".join(t for t in texts if t)
        
        return str(content)
    
    def _extract_transcript_from_item(self, item) -> str:
        """Extract transcript content from a RealtimeItem following SDK pattern.
        
        Looks for the 'transcript' field in content parts (InputAudio, AssistantAudio types).
        Falls back to _extract_content for text-based content.
        """
        content = getattr(item, "content", None)
        if not content:
            return ""
        
        if isinstance(content, list):
            transcripts = []
            for part in content:
                if hasattr(part, "transcript") and part.transcript:
                    transcripts.append(part.transcript)
                elif isinstance(part, dict):
                    transcript = part.get("transcript")
                    if transcript:
                        transcripts.append(transcript)
                    elif part.get("type") in ("text", "input_text"):
                        text = part.get("text")
                        if text:
                            transcripts.append(text)
                elif hasattr(part, "text") and part.text:
                    transcripts.append(part.text)
            
            if transcripts:
                return " ".join(t for t in transcripts if t)
        
        return self._extract_content(item)
    
    async def _generate_feedback(self, session_id: str, transcript: list[dict]):
        """Generate feedback asynchronously."""
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
                            'improvements': feedback_dict.get('data_gathering', {}).get('areas_for_improvement', [])
                        },
                        'clinical_management': {
                            'score': feedback_dict.get('clinical_management', {}).get('score', 0),
                            'strengths': feedback_dict.get('clinical_management', {}).get('strengths', []),
                            'improvements': feedback_dict.get('clinical_management', {}).get('areas_for_improvement', [])
                        },
                        'interpersonal_skills': {
                            'score': feedback_dict.get('relating_to_others', {}).get('score', 0),
                            'strengths': feedback_dict.get('relating_to_others', {}).get('strengths', []),
                            'improvements': feedback_dict.get('relating_to_others', {}).get('areas_for_improvement', [])
                        },
                        'overall_summary': feedback_dict.get('summary', ''),
                        'key_learning_points': feedback_dict.get('key_learning_points', [])
                    }
                    self.db_repo.save_feedback(db_info['db_session_id'], db_feedback)
                    
                    # Update domain progress if station has a domain
                    station_data = db_info.get('station_data', {})
                    if db_info.get('user_id') and station_data.get('domain_id'):
                        overall_score = (
                            db_feedback['data_gathering']['score'] +
                            db_feedback['clinical_management']['score'] +
                            db_feedback['interpersonal_skills']['score']
                        ) // 3
                        passed = all([
                            db_feedback['data_gathering']['score'] >= 60,
                            db_feedback['clinical_management']['score'] >= 60,
                            db_feedback['interpersonal_skills']['score'] >= 60
                        ])
                        self.db_repo.update_domain_progress(
                            db_info['user_id'],
                            station_data['domain_id'],
                            overall_score,
                            passed
                        )
                except Exception as e:
                    logger.error(f"Session {session_id}: Failed to save feedback to database - {e}")
            
            # Try to notify client if still connected
            websocket = self.websockets.get(session_id)
            if websocket:
                await websocket.send_text(json.dumps({
                    "type": "feedback_ready",
                    "feedback": feedback.model_dump(),
                }))
                
        except Exception as e:
            logger.error(f"Session {session_id}: Feedback generation failed - {e}")
            self.feedback_results[session_id] = {
                "error": str(e),
                "transcript": transcript,
            }
    
    def get_feedback(self, session_id: str) -> dict | None:
        """Get feedback for a session if available."""
        return self.feedback_results.get(session_id)
