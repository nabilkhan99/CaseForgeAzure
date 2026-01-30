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
from agents.realtime.config import RealtimeUserInputMessage

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
        self.seen_item_ids[session_id] = set()  # Track seen item_ids for deduplication
        self.item_transcripts[session_id] = {}  # Map item_id -> transcript data
        
        # Delta accumulator buffers for streaming transcripts
        # Each role accumulates text until a turn boundary
        self.delta_buffers = getattr(self, 'delta_buffers', {})
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
        # Preview Format: wss://{resource}.openai.azure.com/openai/realtime?api-version={version}&deployment={deployment}
        azure_endpoint = settings.AZURE_OPENAI_ENDPOINT.rstrip('/')
        # Convert https:// to wss://
        if azure_endpoint.startswith('https://'):
            ws_endpoint = azure_endpoint.replace('https://', 'wss://')
        elif azure_endpoint.startswith('http://'):
            ws_endpoint = azure_endpoint.replace('http://', 'ws://')
        else:
            ws_endpoint = f"wss://{azure_endpoint}"
        
        # Use GA endpoint format (no api-version required)
        azure_url = (
            f"{ws_endpoint}/openai/v1/realtime"
            f"?model={settings.AZURE_OPENAI_REALTIME_DEPLOYMENT}"
        )
        
        logger.info(f"Session {session_id}: Connecting to Azure OpenAI at {azure_url}")
        
        # Configure for Azure OpenAI with custom URL and headers
        # Using openai-agents SDK with Azure OpenAI
        model_config = {
            "url": azure_url,
            "headers": {
                "api-key": settings.AZURE_OPENAI_API_KEY,
            },
            "initial_model_settings": {
                # Azure OpenAI only supports ['audio'] or ['text'], not both together
                "modalities": ["audio"],
                "voice": settings.DEFAULT_VOICE,
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "input_audio_transcription": {
                    "model": "whisper-1",
                },
                "turn_detection": {
                    "type": settings.TURN_DETECTION_TYPE,  # semantic_vad recommended
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
            
            # Start timer
            timer = ConsultationTimer(settings.CONSULTATION_DURATION_SECONDS)
            timer.start(lambda: self._on_timer_end(session_id))
            self.timers[session_id] = timer
            
            # Notify client that session is ready
            await websocket.send_text(json.dumps({
                "type": "session_started",
                "duration_seconds": settings.CONSULTATION_DURATION_SECONDS,
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
        
        # Close realtime session - use pop to avoid race conditions
        context = self.session_contexts.pop(session_id, None)
        if context:
            try:
                await context.__aexit__(None, None, None)
            except Exception as e:
                logger.error(f"Session {session_id}: Error closing context - {e}")
        
        # Clean up all session data using pop() to avoid KeyErrors on double-disconnect
        self.active_sessions.pop(session_id, None)
        self.websockets.pop(session_id, None)
        self.seen_item_ids.pop(session_id, None)
        self.item_transcripts.pop(session_id, None)
        if hasattr(self, 'delta_buffers'):
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
            # Clear the buffer
            buffer[role] = ""
    
    def _flush_all_delta_buffers(self, session_id: str):
        """Flush all remaining delta buffers before saving."""
        # Flush user first, then assistant (typical conversation order)
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
        for i, t in enumerate(transcript[:5]):  # Log first 5 items
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
            
        elif event.type == "audio_interrupted":
            # Audio was interrupted by user speech
            # Per docs: send conversation.item.truncate to remove unplayed audio from conversation
            session = self.active_sessions.get(session_id)
            if session:
                try:
                    item_id = getattr(event, 'item_id', None)
                    audio_end_ms = getattr(event, 'audio_end_ms', None)
                    if item_id and audio_end_ms is not None:
                        truncate_event = {
                            "type": "conversation.item.truncate",
                            "item_id": item_id,
                            "content_index": 0,
                            "audio_end_ms": audio_end_ms
                        }
                        # Send truncate event to API
                        await session.send_event(truncate_event)
                        logger.debug(f"Session {session_id}: Sent truncate event for item {item_id}")
                except Exception as e:
                    logger.debug(f"Session {session_id}: Could not send truncate event - {e}")
            
        elif event.type == "audio_end":
            # Audio streaming finished
            pass
            
        elif event.type == "history_added":
            # Capture transcript - SDK authoritative source for new items
            # Uses item_id-based deduplication following SDK best practices
            try:
                item = event.item
                item_id = getattr(item, "item_id", None)
                role = getattr(item, "role", "unknown")
                
                # Extract transcript from content parts (SDK pattern)
                content = self._extract_transcript_from_item(item)
                
                # Log for debugging
                logger.info(f"Session {session_id}: history_added - item_id={item_id}, role={role}, content_length={len(content) if content else 0}")
                
                # Only process if we haven't seen this item_id before
                if item_id and item_id not in self.seen_item_ids[session_id]:
                    self.seen_item_ids[session_id].add(item_id)
                    
                    if content:
                        # Store in item_transcripts for potential updates
                        self.item_transcripts[session_id][item_id] = {
                            "role": role,
                            "content": content,
                            "timestamp": datetime.now().isoformat(),
                        }
                        # Add to final transcripts list
                        self.transcripts[session_id].append(self.item_transcripts[session_id][item_id])
                        event_data["item"] = {"role": role, "content": content, "id": item_id}
                    else:
                        # Item exists but no transcript yet - track it for later update
                        self.item_transcripts[session_id][item_id] = {
                            "role": role,
                            "content": "",
                            "timestamp": datetime.now().isoformat(),
                        }
                        event_data["item"] = {"role": role, "content": "", "id": item_id}
                elif item_id:
                    # Item already seen, just update event_data for frontend
                    existing = self.item_transcripts[session_id].get(item_id, {})
                    event_data["item"] = {"role": role, "content": existing.get("content", ""), "id": item_id}
                    
            except Exception as e:
                logger.warning(f"Session {session_id}: Could not extract content in history_added - {e}")
                
        elif event.type == "history_updated":
            # Content was updated (e.g., transcription completed)
            # Update existing item by item_id - don't create duplicates
            try:
                item = getattr(event, 'item', None)
                if item is None:
                    return
                
                # history_updated contains full history list, not single item
                # Extract the updated items from the history
                history = getattr(event, 'history', None)
                if history:
                    # Process each item in history for transcript updates
                    for hist_item in history:
                        item_id = getattr(hist_item, "item_id", None)
                        if not item_id:
                            continue
                            
                        role = getattr(hist_item, "role", "unknown")
                        content = self._extract_transcript_from_item(hist_item)
                        
                        if content and item_id in self.item_transcripts[session_id]:
                            # Update existing transcript if content changed
                            existing = self.item_transcripts[session_id][item_id]
                            if existing.get("content") != content:
                                logger.info(f"Session {session_id}: history_updated - updating item_id={item_id}, role={role}")
                                existing["content"] = content
                                # Find and update in transcripts list
                                for t in self.transcripts[session_id]:
                                    if t.get("content") == "" and t.get("role") == role:
                                        t["content"] = content
                                        break
                        elif content and item_id not in self.seen_item_ids[session_id]:
                            # New item from history_updated (shouldn't normally happen)
                            self.seen_item_ids[session_id].add(item_id)
                            self.item_transcripts[session_id][item_id] = {
                                "role": role,
                                "content": content,
                                "timestamp": datetime.now().isoformat(),
                            }
                            self.transcripts[session_id].append(self.item_transcripts[session_id][item_id])
                    
                    # Send update to frontend
                    event_data["history"] = [{"role": getattr(h, "role", "unknown"), 
                                              "content": self._extract_transcript_from_item(h),
                                              "id": getattr(h, "item_id", None)} 
                                             for h in history if hasattr(h, "role")]
                                
            except Exception as e:
                logger.debug(f"Session {session_id}: history_updated - {e}")
                
        elif event.type == "raw_model_event":
            # Handle raw OpenAI SDK events for real-time streaming to frontend
            # Also save COMPLETED transcripts for feedback generation (with deduplication)
            try:
                raw_event = event.data
                raw_type = getattr(raw_event, "type", "")
                
                # Log all raw event types for debugging
                if raw_type and "transcript" in raw_type.lower():
                    logger.info(f"Session {session_id}: raw_model_event type={raw_type}")
                
                # Handle input audio transcription (user's speech converted to text)
                if raw_type in ("input_audio_transcription_completed", 
                               "conversation.item.input_audio_transcription.completed"):
                    transcript_text = getattr(raw_event, "transcript", "")
                    item_id = getattr(raw_event, "item_id", None)
                    if transcript_text:
                        logger.info(f"Session {session_id}: User transcription: {transcript_text[:50]}...")
                        # Send to frontend for real-time display
                        await websocket.send_text(json.dumps({
                            "type": "transcript_update",
                            "item": {"role": "user", "content": transcript_text}
                        }))
                        # Save for feedback - dedupe by item_id if available, else by content
                        dedupe_key = item_id or f"user:{transcript_text[:50]}"
                        if dedupe_key not in self.seen_item_ids.get(session_id, set()):
                            self.seen_item_ids.setdefault(session_id, set()).add(dedupe_key)
                            self.transcripts[session_id].append({
                                "role": "user",
                                "content": transcript_text,
                                "timestamp": datetime.now().isoformat(),
                            })
                
                # Handle streaming input transcription delta (GA API) - display only, no save
                elif raw_type == "conversation.item.input_audio_transcription.delta":
                    delta_text = getattr(raw_event, "delta", "")
                    if delta_text:
                        await websocket.send_text(json.dumps({
                            "type": "transcript_delta",
                            "item": {"role": "user", "content": delta_text}
                        }))
                        # Accumulate user delta
                        if session_id in self.delta_buffers:
                            # If assistant was speaking, flush their buffer first
                            if self.delta_buffers[session_id]["assistant"]:
                                self._flush_delta_buffer(session_id, "assistant")
                            self.delta_buffers[session_id]["user"] += delta_text
                        
                # Handle partial transcript updates (assistant's speech as text)
                elif raw_type in ("transcript_delta", "response.output_audio_transcript.delta"):
                    delta_text = getattr(raw_event, "delta", "")
                    if delta_text:
                        await websocket.send_text(json.dumps({
                            "type": "transcript_delta",
                            "item": {"role": "assistant", "content": delta_text}
                        }))
                        # Accumulate assistant delta
                        if session_id in self.delta_buffers:
                            # If user was speaking, flush their buffer first
                            if self.delta_buffers[session_id]["user"]:
                                self._flush_delta_buffer(session_id, "user")
                            self.delta_buffers[session_id]["assistant"] += delta_text
                
                # Handle completed assistant transcript (GA API event name)
                elif raw_type == "response.output_audio_transcript.done":
                    transcript_text = getattr(raw_event, "transcript", "")
                    item_id = getattr(raw_event, "item_id", None)
                    if transcript_text:
                        logger.info(f"Session {session_id}: Assistant transcript: {transcript_text[:50]}...")
                        # Send to frontend for real-time display
                        await websocket.send_text(json.dumps({
                            "type": "transcript_update",
                            "item": {"role": "assistant", "content": transcript_text}
                        }))
                        # Save for feedback - dedupe by item_id if available, else by content
                        dedupe_key = item_id or f"assistant:{transcript_text[:50]}"
                        if dedupe_key not in self.seen_item_ids.get(session_id, set()):
                            self.seen_item_ids.setdefault(session_id, set()).add(dedupe_key)
                            self.transcripts[session_id].append({
                                "role": "assistant",
                                "content": transcript_text,
                                "timestamp": datetime.now().isoformat(),
                            })
                        
            except Exception as e:
                logger.debug(f"Session {session_id}: raw_model_event processing - {e}")
                
        elif event.type == "agent_start":
            event_data["agent"] = event.agent.name
            
        elif event.type == "agent_end":
            event_data["agent"] = event.agent.name
            
        elif event.type == "tool_start":
            event_data["tool"] = event.tool.name
            
        elif event.type == "tool_end":
            event_data["tool"] = event.tool.name
            event_data["output"] = str(event.output)
            
        elif event.type == "error":
            # Extract a meaningful error message
            error_obj = getattr(event, "error", None)
            if error_obj and hasattr(error_obj, "message"):
                error_message = error_obj.message
            else:
                error_message = str(error_obj) if error_obj else "Unknown error"
            
            logger.error(f"Session {session_id}: Error event received - {error_message}")
            logger.error(f"Session {session_id}: Full error event: {event}")
            
            # Don't send recoverable errors to frontend - they cause unnecessary UI disruption
            recoverable_errors = ["Audio content", "already shorter", "truncate"]
            is_recoverable = any(phrase in error_message for phrase in recoverable_errors)
            
            if not is_recoverable:
                event_data["error"] = error_message
            else:
                logger.warning(f"Session {session_id}: Recoverable error ignored for UI: {error_message}")
                return  # Don't send to frontend
        
        # Send event to client
        await websocket.send_text(json.dumps(event_data))
    
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
            # Filter out any None values before joining
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
                # Check for transcript field (SDK InputAudio/AssistantAudio pattern)
                if hasattr(part, "transcript") and part.transcript:
                    transcripts.append(part.transcript)
                elif isinstance(part, dict):
                    transcript = part.get("transcript")
                    if transcript:
                        transcripts.append(transcript)
                    # Also check for text fallback
                    elif part.get("type") in ("text", "input_text"):
                        text = part.get("text")
                        if text:
                            transcripts.append(text)
                # Check for text-based content as fallback
                elif hasattr(part, "text") and part.text:
                    transcripts.append(part.text)
            
            if transcripts:
                return " ".join(t for t in transcripts if t)
        
        # Fallback to regular content extraction
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
                    # Transform feedback to match database schema
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
