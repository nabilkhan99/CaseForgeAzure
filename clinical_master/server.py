"""
Clinical Master - FastAPI Server

WebSocket + REST API server for ADK Gemini Live voice-to-voice.
Handles realtime voice sessions, transcript capture, and feedback generation.
"""

import asyncio
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
    logger.info("Clinical Master starting (ADK Gemini Live)")
    logger.info(f"  Model: {settings.GEMINI_LIVE_MODEL}")
    logger.info(f"  Voice: {settings.DEFAULT_VOICE}")
    logger.info(f"  Consultation duration: {settings.CONSULTATION_DURATION_SECONDS}s")
    yield
    logger.info("Clinical Master shutting down")


from starlette.types import ASGIApp, Receive, Scope, Send


class WSDebugMiddleware:
    """Temporary debug middleware to log WebSocket connection details."""
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] == "websocket":
            from starlette.datastructures import Headers
            headers = Headers(scope=scope)
            origin = headers.get("origin", "NO-ORIGIN")
            path = scope.get("path", "?")
            logger.info(f"WS DEBUG: path={path} origin={origin}")
        await self.app(scope, receive, send)


app = FastAPI(
    title="Clinical Master",
    description="SCA Consultation Voice Simulator - ADK Gemini Live",
    version="3.0.0",
    lifespan=lifespan,
)

# Debug middleware runs first (outermost)
app.add_middleware(WSDebugMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Health Check ---
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "clinical-master",
        "mode": "gemini-live",
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
    The session manager handles the full bidirectional streaming loop
    using ADK's Runner.run_live() + LiveRequestQueue pattern.
    
    Events sent to client:
    - session_started: Session is ready with duration info
    - audio: Base64-encoded PCM16 audio from patient agent
    - transcript_delta: Incremental transcript text (user or assistant)
    - history_added: Completed transcript entry
    - audio_interrupted: Signal to clear audio playback buffer
    - consultation_ended: Time's up, feedback generation starting
    - feedback_ready: Structured feedback available
    """
    try:
        # connect() blocks for the full session duration —
        # it runs upstream + downstream tasks concurrently
        await session_manager.connect(websocket, session_id, user_id, station_id)
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
    
    # Check if feedback is already being generated (by _on_timer_end)
    if session_id in session_manager.feedback_generating:
        return {
            "status": "processing",
            "session_id": session_id,
            "message": "Feedback generation already in progress",
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
        # Resolve ws session_id → db session_id for database lookup
        db_session_id = session_manager.get_db_session_id(session_id) or session_id
        
        # Check database
        try:
            repo = SessionRepository()
            session_data = repo.get_session_with_results(db_session_id)
            if session_data and session_data.get("session_results"):
                results = session_data["session_results"]
                # Handle both list and single-object shapes from Supabase
                if isinstance(results, list) and results:
                    row = results[0]
                elif isinstance(results, dict):
                    row = results
                else:
                    row = None
                if row:
                    station_info = session_data.get("stations") or {}
                    return {
                        "status": "ready",
                        "feedback": _normalize_db_feedback(
                            row,
                            station_title=station_info.get("title"),
                            overall_score=session_data.get("overall_score"),
                        ),
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


def _normalize_db_feedback(row: dict, station_title: str = None, overall_score: int = None) -> dict:
    """Transform flat DB session_results row into nested ConsultationFeedback shape."""
    def _domain(name: str, score_key: str, feedback_key: str) -> dict:
        fb = row.get(feedback_key) or {}
        return {
            "domain": name,
            "score": row.get(score_key, 0),
            "strengths": fb.get("strengths", []),
            "improvements": fb.get("improvements", []),
        }

    result = {
        "data_gathering": _domain("Data Gathering", "data_gathering_score", "data_gathering_feedback"),
        "clinical_management": _domain("Clinical Management", "clinical_management_score", "clinical_management_feedback"),
        "interpersonal_skills": _domain("Interpersonal Skills", "interpersonal_skills_score", "interpersonal_skills_feedback"),
        "overall_summary": row.get("overall_summary", ""),
        "key_learning_points": row.get("key_learning_points", []),
    }
    if station_title:
        result["station_title"] = station_title
    if overall_score is not None:
        result["overall_score"] = overall_score
    return result


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
        ws="wsproto",
    )
