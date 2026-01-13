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
    from ..agents.patient import get_patient_agent
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from clinical_master.config import settings
    from clinical_master.agents.patient import get_patient_agent

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
    
    async def connect(self, websocket: WebSocket, session_id: str):
        """
        Accept WebSocket connection and start realtime session.
        """
        await websocket.accept()
        self.websockets[session_id] = websocket
        self.transcripts[session_id] = []
        
        logger.info(f"Session {session_id}: Connection accepted")
        
        # Get patient agent
        agent = get_patient_agent()
        runner = RealtimeRunner(agent)
        
        # Build Azure OpenAI WebSocket URL for Realtime API
        # Format: wss://{resource}.openai.azure.com/openai/realtime?api-version={version}&deployment={deployment}
        azure_endpoint = settings.AZURE_OPENAI_ENDPOINT.rstrip('/')
        # Convert https:// to wss://
        if azure_endpoint.startswith('https://'):
            ws_endpoint = azure_endpoint.replace('https://', 'wss://')
        elif azure_endpoint.startswith('http://'):
            ws_endpoint = azure_endpoint.replace('http://', 'ws://')
        else:
            ws_endpoint = f"wss://{azure_endpoint}"
        
        azure_url = (
            f"{ws_endpoint}/openai/realtime"
            f"?api-version={settings.AZURE_OPENAI_API_VERSION}"
            f"&deployment={settings.AZURE_OPENAI_REALTIME_DEPLOYMENT}"
        )
        
        logger.info(f"Session {session_id}: Connecting to Azure OpenAI at {azure_url}")
        
        # Configure for Azure OpenAI with custom URL and headers
        model_config = {
            "url": azure_url,
            "headers": {
                "api-key": settings.AZURE_OPENAI_API_KEY,
            },
            "initial_model_settings": {
                "turn_detection": {
                    "type": "server_vad",
                    "prefix_padding_ms": settings.VAD_PREFIX_PADDING_MS,
                    "silence_duration_ms": settings.VAD_SILENCE_DURATION_MS,
                    "interrupt_response": True,
                    "create_response": True,
                },
                "audio": {
                    "voice": settings.DEFAULT_VOICE,
                },
                # Enable transcription of user's speech
                "input_audio_transcription": {
                    "model": "whisper-1",
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
        
        # Close realtime session
        if session_id in self.session_contexts:
            try:
                await self.session_contexts[session_id].__aexit__(None, None, None)
            except Exception as e:
                logger.error(f"Session {session_id}: Error closing context - {e}")
            del self.session_contexts[session_id]
        
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]
        
        if session_id in self.websockets:
            del self.websockets[session_id]
    
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
    
    async def _on_timer_end(self, session_id: str):
        """Called when timer expires or consultation ends."""
        logger.info(f"Session {session_id}: Consultation ended")
        
        websocket = self.websockets.get(session_id)
        if websocket:
            await websocket.send_text(json.dumps({
                "type": "consultation_ended",
                "message": "Time's up! Generating feedback...",
            }))
        
        # Trigger async feedback generation
        transcript = self.transcripts.get(session_id, [])
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
            pass
            
        elif event.type == "audio_end":
            # Audio streaming finished
            pass
            
        elif event.type == "history_added":
            # Capture transcript
            try:
                item = event.item
                content = self._extract_content(item)
                role = getattr(item, "role", "unknown")
                
                # Log for debugging
                logger.info(f"Session {session_id}: history_added - role={role}, content_length={len(content) if content else 0}")
                
                if content:
                    self.transcripts[session_id].append({
                        "role": role,
                        "content": content,
                        "timestamp": datetime.now().isoformat(),
                    })
                    event_data["item"] = {"role": role, "content": content}
                else:
                    # Still send the event but with empty content
                    event_data["item"] = {"role": role, "content": ""}
            except Exception as e:
                logger.warning(f"Session {session_id}: Could not extract content - {e}")
                
        elif event.type == "history_updated":
            # Content was updated (e.g., transcription completed)
            try:
                item = event.item
                content = self._extract_content(item)
                role = getattr(item, "role", "unknown")
                item_id = getattr(item, "id", None)
                
                logger.info(f"Session {session_id}: history_updated - role={role}, content_length={len(content) if content else 0}")
                
                if content:
                    # Update existing transcript or add new
                    event_data["item"] = {"role": role, "content": content, "id": item_id}
                    # Also append to transcript for feedback
                    self.transcripts[session_id].append({
                        "role": role,
                        "content": content,
                        "timestamp": datetime.now().isoformat(),
                    })
            except Exception as e:
                logger.warning(f"Session {session_id}: history_updated error - {e}")
                
        elif event.type == "raw_model_event":
            # Handle raw OpenAI SDK events for transcription
            try:
                raw_event = event.data
                raw_type = getattr(raw_event, "type", "")
                
                # Handle input audio transcription (user's speech converted to text)
                if raw_type == "input_audio_transcription_completed":
                    transcript_text = getattr(raw_event, "transcript", "")
                    if transcript_text:
                        logger.info(f"Session {session_id}: User transcription: {transcript_text[:100]}...")
                        self.transcripts[session_id].append({
                            "role": "user",
                            "content": transcript_text,
                            "timestamp": datetime.now().isoformat(),
                        })
                        # Send as transcript item to frontend
                        await websocket.send_text(json.dumps({
                            "type": "transcript_update",
                            "item": {"role": "user", "content": transcript_text}
                        }))
                        
                # Handle partial transcript updates (assistant's speech as text)
                elif raw_type == "transcript_delta":
                    delta_text = getattr(raw_event, "delta", "")
                    if delta_text:
                        # Send delta to frontend for real-time display
                        await websocket.send_text(json.dumps({
                            "type": "transcript_delta",
                            "item": {"role": "assistant", "content": delta_text}
                        }))
                        
                # Handle item updates which may contain transcripts
                elif raw_type == "item_updated":
                    item = getattr(raw_event, "item", None)
                    if item:
                        content = self._extract_content(item)
                        role = getattr(item, "role", "unknown")
                        if content and role in ("user", "assistant"):
                            logger.info(f"Session {session_id}: item_updated - role={role}, content={content[:100]}...")
                            self.transcripts[session_id].append({
                                "role": role,
                                "content": content,
                                "timestamp": datetime.now().isoformat(),
                            })
                            await websocket.send_text(json.dumps({
                                "type": "transcript_update",
                                "item": {"role": role, "content": content}
                            }))
                        
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
            event_data["error"] = str(getattr(event, "error", "Unknown error"))
        
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
                        texts.append(part.get("text", ""))
                    elif part.get("type") == "transcript":
                        texts.append(part.get("transcript", ""))
                elif hasattr(part, "text"):
                    texts.append(part.text)
                elif hasattr(part, "transcript"):
                    texts.append(part.transcript)
            return " ".join(texts)
        
        return str(content)
    
    async def _generate_feedback(self, session_id: str, transcript: list[dict]):
        """Generate feedback asynchronously."""
        try:
            from ..agents.feedback import generate_feedback
        except ImportError:
            from clinical_master.agents.feedback import generate_feedback
        
        try:
            logger.info(f"Session {session_id}: Generating feedback...")
            
            # Case brief for context
            case_brief = (
                "Margaret Thompson, 58-year-old retired teacher with 3 days of chest pain. "
                "Key history: hypertension, type 2 diabetes, smoker, family history of MI. "
                "Red flags: pain at rest/night, breathlessness, ankle swelling. "
                "ECG shows ST depression in V4-V6."
            )
            
            feedback = await generate_feedback(transcript, case_brief)
            
            # Store feedback
            self.feedback_results[session_id] = feedback.model_dump()
            
            logger.info(f"Session {session_id}: Feedback generated")
            
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
