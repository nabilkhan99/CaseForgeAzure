"""
Clinical Master - FastAPI Server

WebSocket + REST API server for Azure OpenAI Realtime voice-to-voice.
Handles realtime voice sessions, transcript capture, and feedback generation.
"""

import asyncio
import base64
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional

# Handle imports for both package and script modes
try:
    from .config import settings
    from .session import SessionManager
    from .db import SessionRepository
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from clinical_master.config import settings
    from clinical_master.session import SessionManager
    from clinical_master.db import SessionRepository


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


# --- App Lifecycle ---
session_manager = SessionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    logger.info("Clinical Master starting (Azure OpenAI Realtime)")
    logger.info(f"  Realtime deployment: {settings.AZURE_OPENAI_REALTIME_DEPLOYMENT}")
    logger.info(f"  Voice: {settings.DEFAULT_VOICE}")
    logger.info(f"  Turn detection: {settings.TURN_DETECTION_TYPE}")
    logger.info(f"  Consultation duration: {settings.CONSULTATION_DURATION_SECONDS}s")
    yield
    logger.info("Clinical Master shutting down")


app = FastAPI(
    title="Clinical Master",
    description="SCA Consultation Voice Simulator - Azure OpenAI Realtime",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Health Check ---
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "clinical-master",
        "mode": "azure-realtime",
    }


# --- Test Client ---
@app.get("/test", response_class=HTMLResponse)
async def test_client():
    """Serve test client HTML page."""
    test_file = Path(__file__).parent / "tests" / "test_client.html"
    if not test_file.exists():
        raise HTTPException(status_code=404, detail="Test client not found")
    return HTMLResponse(content=test_file.read_text(), status_code=200)


# --- WebSocket Endpoint ---
@app.websocket("/ws/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
    user_id: str | None = None,
    station_id: str | None = None,
):
    """
    WebSocket endpoint for realtime voice sessions.
    
    The client sends binary audio frames (PCM16) and text commands.
    The server proxies audio to Azure OpenAI Realtime and sends back:
    - Audio responses (base64-encoded PCM16)
    - Transcript updates (history_added, transcript_delta, transcript_update)
    - Session lifecycle events (session_started, consultation_ended, feedback_ready)
    """
    await session_manager.connect(websocket, session_id, user_id, station_id)
    
    try:
        while True:
            message = await websocket.receive()
            
            if message.get("type") == "websocket.disconnect":
                break
            
            if "bytes" in message:
                # Binary audio data from browser microphone
                await session_manager.send_audio(session_id, message["bytes"])
                
            elif "text" in message:
                import json
                try:
                    data = json.loads(message["text"])
                    msg_type = data.get("type", "")
                    
                    if msg_type == "interrupt":
                        await session_manager.interrupt(session_id)
                    elif msg_type == "end_consultation":
                        await session_manager.end_consultation(session_id)
                        break
                    elif msg_type == "audio":
                        # Base64-encoded audio from browser
                        audio_b64 = data.get("audio", "")
                        if audio_b64:
                            audio_bytes = base64.b64decode(audio_b64)
                            await session_manager.send_audio(session_id, audio_bytes)
                except json.JSONDecodeError:
                    logger.warning(f"Session {session_id}: Invalid JSON message")
                    
    except WebSocketDisconnect:
        logger.info(f"Session {session_id}: Client disconnected")
    except Exception as e:
        logger.error(f"Session {session_id}: WebSocket error - {e}")
    finally:
        await session_manager.disconnect(session_id)


# --- REST Endpoints ---

class CompleteSessionRequest(BaseModel):
    """Request body for completing a session."""
    station_id: Optional[str] = None
    transcript: Optional[list] = None


@app.post("/session/{session_id}/complete")
async def complete_session(session_id: str, request: CompleteSessionRequest):
    """
    Complete a session and trigger feedback generation.
    
    Called by the frontend when the consultation ends (either by timer or manual end).
    The transcript should already be saved by the WebSocket session manager, but
    the frontend can also pass a fallback transcript.
    """
    logger.info(f"REST: Complete session {session_id}")
    
    # Check if the session manager already has transcript/feedback
    existing_feedback = session_manager.get_feedback(session_id)
    if existing_feedback:
        return {
            "status": "feedback_ready",
            "session_id": session_id,
            "feedback": existing_feedback,
        }
    
    # Check if we have a transcript from the WebSocket session
    ws_transcript = session_manager.transcripts.get(session_id)
    transcript = ws_transcript if ws_transcript else (request.transcript or [])
    
    if not transcript:
        return {
            "status": "no_transcript",
            "session_id": session_id,
            "message": "No transcript available for feedback generation",
        }
    
    # Trigger feedback generation if not already running
    asyncio.create_task(
        session_manager._generate_feedback(session_id, transcript)
    )
    
    return {
        "status": "processing",
        "session_id": session_id,
        "message": "Feedback generation started",
    }


@app.get("/feedback/{session_id}")
async def get_feedback(session_id: str):
    """Poll for feedback results."""
    feedback = session_manager.get_feedback(session_id)
    
    if feedback is None:
        # Check database
        try:
            repo = SessionRepository()
            session_data = repo.get_session_with_results(session_id)
            if session_data and session_data.get("session_results"):
                results = session_data["session_results"]
                if isinstance(results, list) and results:
                    return {
                        "status": "ready",
                        "feedback": results[0],
                        "source": "database",
                    }
        except Exception as e:
            logger.error(f"Error fetching feedback from database: {e}")
        
        raise HTTPException(
            status_code=404, 
            detail="Feedback not ready yet. Please try again."
        )
    
    if "error" in feedback:
        raise HTTPException(
            status_code=500,
            detail=f"Feedback generation failed: {feedback['error']}",
        )
    
    return {
        "status": "ready",
        "feedback": feedback,
        "source": "session_manager",
    }


@app.get("/session/{session_id}")
async def get_session(session_id: str):
    """Get session details from database."""
    try:
        repo = SessionRepository()
        session_data = repo.get_session_with_results(session_id)
        if not session_data:
            raise HTTPException(status_code=404, detail="Session not found")
        return session_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- Entry Point ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "clinical_master.server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
