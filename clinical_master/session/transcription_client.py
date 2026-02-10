"""
OpenAI Direct Transcription Client

Connects to OpenAI Realtime API with intent=transcription for
aligned user speech transcription using gpt-4o-transcribe.

This runs in parallel with Azure OpenAI Realtime to provide better
alignment between what the conversation model "hears" and the transcript
used for feedback generation.
"""

import asyncio
import base64
import json
import logging
from typing import Callable, Optional

import websockets

logger = logging.getLogger(__name__)


class OpenAITranscriptionClient:
    """
    Parallel transcription client using OpenAI Direct Realtime API.
    
    Receives the same audio as the Azure Realtime session, but uses
    gpt-4o-transcribe for transcription (which Azure doesn't support
    in Realtime sessions).
    """
    
    def __init__(self, api_key: str, model: str = "gpt-4o-transcribe"):
        self.api_key = api_key
        self.model = model
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self._on_transcript_delta: Optional[Callable] = None
        self._on_transcript_done: Optional[Callable] = None
        self._running = False
        self._receive_task: Optional[asyncio.Task] = None
        self._session_id: str = ""
    
    async def connect(
        self,
        session_id: str,
        on_delta: Optional[Callable] = None,
        on_done: Optional[Callable] = None
    ) -> bool:
        """
        Connect to OpenAI Realtime with transcription intent.
        
        Args:
            session_id: Session identifier for logging
            on_delta: Callback for streaming transcript deltas
            on_done: Callback for completed transcripts
            
        Returns:
            True if connected successfully, False otherwise
        """
        self._session_id = session_id
        self._on_transcript_delta = on_delta
        self._on_transcript_done = on_done
        
        # OpenAI Realtime transcription endpoint
        url = f"wss://api.openai.com/v1/realtime?model={self.model}&intent=transcription"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "OpenAI-Beta": "realtime=v1"
        }
        
        try:
            self.ws = await websockets.connect(
                url,
                additional_headers=headers,
                ping_interval=20,
                ping_timeout=60
            )
            self._running = True
            self._receive_task = asyncio.create_task(self._receive_events())
            logger.info(f"Session {session_id}: OpenAI transcription client connected")
            return True
            
        except Exception as e:
            logger.error(f"Session {session_id}: Failed to connect OpenAI transcription - {e}")
            return False
    
    async def send_audio(self, audio_bytes: bytes):
        """
        Send audio chunk to OpenAI for transcription.
        
        Args:
            audio_bytes: PCM16 audio data (same format as Azure Realtime)
        """
        if self.ws and self._running:
            try:
                audio_b64 = base64.b64encode(audio_bytes).decode()
                await self.ws.send(json.dumps({
                    "type": "input_audio_buffer.append",
                    "audio": audio_b64
                }))
            except Exception as e:
                logger.debug(f"Session {self._session_id}: Error sending audio - {e}")
    
    async def commit_audio(self):
        """
        Signal end of current audio turn.
        Call this when VAD detects end of speech.
        """
        if self.ws and self._running:
            try:
                await self.ws.send(json.dumps({
                    "type": "input_audio_buffer.commit"
                }))
            except Exception as e:
                logger.debug(f"Session {self._session_id}: Error committing audio - {e}")
    
    async def _receive_events(self):
        """Process incoming transcription events from OpenAI."""
        try:
            async for message in self.ws:
                if not self._running:
                    break
                    
                event = json.loads(message)
                event_type = event.get("type", "")
                
                # Log transcription events for debugging
                if "transcript" in event_type.lower():
                    logger.debug(f"Session {self._session_id}: OpenAI event - {event_type}")
                
                # Handle transcription delta (streaming text)
                if event_type in (
                    "conversation.item.input_audio_transcription.delta",
                    "input_audio_transcription.delta",
                    "input_audio_buffer.transcription.delta"
                ):
                    delta = event.get("delta", "")
                    if delta and self._on_transcript_delta:
                        try:
                            await self._on_transcript_delta(delta)
                        except Exception as e:
                            logger.debug(f"Error in delta callback: {e}")
                
                # Handle transcription complete
                elif event_type in (
                    "conversation.item.input_audio_transcription.completed",
                    "conversation.item.input_audio_transcription.done",
                    "input_audio_transcription.completed",
                    "input_audio_transcription.done",
                    "input_audio_buffer.transcription.completed",
                    "input_audio_buffer.transcription.done"
                ):
                    transcript = event.get("transcript", "")
                    if transcript and self._on_transcript_done:
                        try:
                            await self._on_transcript_done(transcript)
                        except Exception as e:
                            logger.debug(f"Error in done callback: {e}")
                
                # Handle errors
                elif event_type == "error":
                    error = event.get("error", {})
                    logger.warning(
                        f"Session {self._session_id}: OpenAI transcription error - "
                        f"{error.get('type')}: {error.get('message')}"
                    )
                        
        except websockets.exceptions.ConnectionClosed:
            logger.debug(f"Session {self._session_id}: OpenAI transcription connection closed")
        except Exception as e:
            logger.debug(f"Session {self._session_id}: OpenAI transcription receive error - {e}")
        finally:
            self._running = False
    
    async def disconnect(self):
        """Close the WebSocket connection."""
        self._running = False
        
        if self._receive_task and not self._receive_task.done():
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
        
        if self.ws:
            try:
                await self.ws.close()
            except Exception:
                pass
            self.ws = None
            
        logger.debug(f"Session {self._session_id}: OpenAI transcription client disconnected")
    
    @property
    def is_connected(self) -> bool:
        """Check if the WebSocket is connected and running."""
        return self._running and self.ws is not None
