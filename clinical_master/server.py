"""
Clinical Master - FastAPI Server

REST API server for ElevenLabs Conversational AI integration.
Handles session lifecycle, transcript retrieval, and feedback generation.
"""

import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

# Handle imports for both package and script modes
try:
    from .config import settings
    from .db.session_repository import SessionRepository
    from .ai_agents.feedback import generate_feedback
except ImportError:
    # Running as script, add parent to path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from clinical_master.config import settings
    from clinical_master.db.session_repository import SessionRepository
    from clinical_master.ai_agents.feedback import generate_feedback

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# In-memory feedback cache (session_id -> feedback dict)
_feedback_cache: dict[str, dict] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("Clinical Master server starting (ElevenLabs mode)...")
    yield
    logger.info("Clinical Master server shutting down...")


# Create FastAPI app
app = FastAPI(
    title="Clinical Master",
    description="REST API for ElevenLabs-based SCA exam simulation",
    version="0.2.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database repository
repo = SessionRepository()


# ── Request Models ──────────────────────────────────────────────────────────

class CompleteSessionRequest(BaseModel):
    """Request body for completing a session."""
    conversation_id: Optional[str] = None
    station_id: Optional[str] = None
    transcript: Optional[list[dict]] = None


# ── Endpoints ───────────────────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "clinical-master", "mode": "elevenlabs"}


@app.post("/session/{session_id}/complete")
async def complete_session(session_id: str, request: CompleteSessionRequest):
    """
    Complete a session after ElevenLabs conversation ends.
    
    Fetches the transcript from ElevenLabs API (or accepts it from frontend),
    generates feedback using the existing feedback agent, and saves to Supabase.
    
    The feedback is cached in-memory and can be polled via GET /feedback/{session_id}.
    """
    logger.info(f"Completing session {session_id}, conversation_id={request.conversation_id}")
    
    try:
        # 1. Get the transcript
        transcript = request.transcript
        
        if not transcript and request.conversation_id:
            # Fetch transcript from ElevenLabs API
            transcript = await _fetch_elevenlabs_transcript(request.conversation_id)
        
        if not transcript:
            logger.warning(f"No transcript available for session {session_id}")
            transcript = []
        
        # 2. Get station data for the case brief
        station_data = None
        if request.station_id:
            station_data = repo.get_station(request.station_id)
        
        # 3. Save transcript to Supabase
        repo.save_transcript(session_id, transcript)
        repo.update_session_status(session_id, "processing")
        
        # 4. Generate feedback asynchronously
        asyncio.create_task(
            _generate_and_save_feedback(session_id, transcript, station_data)
        )
        
        return {"status": "processing", "message": "Feedback generation started"}
        
    except Exception as e:
        logger.error(f"Error completing session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/feedback/{session_id}")
async def get_feedback(session_id: str):
    """
    Get feedback for a completed session.
    
    Returns cached in-memory feedback, or checks Supabase if not cached.
    Frontend polls this endpoint until feedback is ready.
    """
    # Check in-memory cache first
    if session_id in _feedback_cache:
        return {"status": "ready", "feedback": _feedback_cache[session_id]}
    
    # Check Supabase for already-generated feedback
    session = repo.get_session_with_results(session_id)
    if session and session.get("session_results"):
        results = session["session_results"]
        if isinstance(results, list) and len(results) > 0:
            result = results[0]
            feedback = {
                "data_gathering": {
                    "domain": "Data Gathering",
                    "score": result.get("data_gathering_score", 0),
                    **result.get("data_gathering_feedback", {}),
                },
                "clinical_management": {
                    "domain": "Clinical Management",
                    "score": result.get("clinical_management_score", 0),
                    **result.get("clinical_management_feedback", {}),
                },
                "interpersonal_skills": {
                    "domain": "Interpersonal Skills",
                    "score": result.get("interpersonal_skills_score", 0),
                    **result.get("interpersonal_skills_feedback", {}),
                },
                "overall_summary": result.get("overall_summary", ""),
                "key_learning_points": result.get("key_learning_points", []),
            }
            _feedback_cache[session_id] = feedback
            return {"status": "ready", "feedback": feedback}
    
    return {"status": "pending", "message": "Feedback not ready yet"}


# ── Internal Helpers ────────────────────────────────────────────────────────

async def _fetch_elevenlabs_transcript(conversation_id: str) -> list[dict]:
    """Fetch transcript from ElevenLabs Conversations API."""
    import httpx
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.elevenlabs.io/v1/convai/conversations/{conversation_id}",
                headers={
                    "xi-api-key": settings.ELEVENLABS_API_KEY,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            
            logger.info(f"ElevenLabs API response keys: {list(data.keys())}")
            
            # Parse ElevenLabs transcript - try multiple possible locations
            transcript = []
            
            # Try data.transcript (array of entries)
            el_transcript = data.get("transcript", [])
            
            if not el_transcript:
                # Try data.conversation.transcript
                conversation_data = data.get("conversation", {})
                el_transcript = conversation_data.get("transcript", [])
            
            if not el_transcript:
                # Try data.analysis.transcript_summary or similar
                analysis = data.get("analysis", {})
                el_transcript = analysis.get("transcript", [])
            
            logger.info(f"ElevenLabs transcript has {len(el_transcript)} entries, type: {type(el_transcript)}")
            if el_transcript and len(el_transcript) > 0:
                logger.info(f"First transcript entry keys: {list(el_transcript[0].keys()) if isinstance(el_transcript[0], dict) else type(el_transcript[0])}")
            
            for entry in el_transcript:
                if isinstance(entry, dict):
                    # Try multiple field name conventions
                    role = entry.get("role", entry.get("speaker", "unknown"))
                    content = entry.get("message", entry.get("text", entry.get("content", "")))
                    timestamp = entry.get("time_in_call_secs", entry.get("timestamp", 0))
                    
                    if content and content != "None":
                        transcript.append({
                            "role": role,
                            "content": content,
                            "timestamp": timestamp,
                        })
            
            logger.info(f"Parsed {len(transcript)} transcript entries from ElevenLabs")
            return transcript
            
    except Exception as e:
        logger.error(f"Failed to fetch ElevenLabs transcript: {e}")
        return []


async def _generate_and_save_feedback(
    session_id: str,
    transcript: list[dict],
    station_data: dict | None,
):
    """Generate feedback and save to Supabase (runs as background task)."""
    try:
        if not transcript or not any(entry.get("content") for entry in transcript):
            logger.warning(f"Session {session_id}: Empty transcript, skipping feedback")
            return
        
        # Build case brief from station data (including marking criteria)
        case_brief = ""
        if station_data:
            case_brief = f"Station: {station_data.get('title', 'Unknown')}\n"
            case_brief += f"Patient: {station_data.get('patient_name', 'Unknown')}, Age: {station_data.get('patient_age', 'Unknown')}\n"
            case_brief += f"Consultation Type: {station_data.get('consultation_type', 'face-to-face')}\n"
            case_brief += f"Case Background: {station_data.get('station_script', 'N/A')}\n"
            
            # Inject station-specific marking criteria
            if station_data.get('data_gathering'):
                case_brief += f"\n## Data Gathering Marking Criteria\n{station_data['data_gathering']}\n"
            
            if station_data.get('clinical_management'):
                case_brief += f"\n## Clinical Management Marking Criteria\n{station_data['clinical_management']}\n"
            
            if station_data.get('relating_to_others'):
                case_brief += f"\n## Interpersonal Skills Marking Criteria\n{station_data['relating_to_others']}\n"
            
            if station_data.get('clinical_learning_points'):
                case_brief += f"\n## Clinical Learning Points (Ideal Management)\n{station_data['clinical_learning_points']}\n"
        
        # Generate feedback using existing agent (expects List[dict])
        logger.info(f"Generating feedback for session {session_id}...")
        feedback = await generate_feedback(transcript, case_brief)
        
        if feedback:
            feedback_dict = feedback.model_dump()
            
            # Cache in memory for immediate poll access
            _feedback_cache[session_id] = feedback_dict
            
            # Save to Supabase
            repo.save_feedback(session_id, feedback_dict)
            
            # Update domain progress if station data available
            if station_data:
                domain = station_data.get("domains")
                if domain:
                    domain_id = domain.get("id") if isinstance(domain, dict) else None
                    if domain_id:
                        overall_score = (
                            feedback_dict.get("data_gathering", {}).get("score", 0) +
                            feedback_dict.get("clinical_management", {}).get("score", 0) +
                            feedback_dict.get("interpersonal_skills", {}).get("score", 0)
                        ) // 3
                        passed = overall_score >= 60
                        repo.update_domain_progress(
                            session_id, domain_id, overall_score, passed
                        )
            
            logger.info(f"Feedback generated and saved for session {session_id}")
        else:
            logger.error(f"Failed to generate feedback for session {session_id}")
            
    except Exception as e:
        logger.error(f"Error generating feedback for session {session_id}: {e}")


# Entry point for running standalone
if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "clinical_master.server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
