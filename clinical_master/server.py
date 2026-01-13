"""
Clinical Master - FastAPI Server

WebSocket server for realtime voice agent interactions.
Runs alongside the existing Azure Functions app.
"""

import asyncio
import json
import logging
import struct
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

# Handle imports for both package and script modes
try:
    from .session.manager import SessionManager
except ImportError:
    # Running as script, add parent to path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from clinical_master.session.manager import SessionManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("Clinical Master server starting...")
    yield
    logger.info("Clinical Master server shutting down...")


# Create FastAPI app for Clinical Master
app = FastAPI(
    title="Clinical Master",
    description="Voice agent for SCA exam simulation",
    version="0.1.0",
    lifespan=lifespan,
)

# Add CORS middleware for HTTP requests (WebSockets handle their own origin)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Session manager instance
session_manager = SessionManager()


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "clinical-master"}


@app.websocket("/ws/test")
async def websocket_test(websocket: WebSocket):
    """Simple test WebSocket endpoint."""
    logger.info("Test WebSocket: Accepting connection...")
    await websocket.accept()
    logger.info("Test WebSocket: Connection accepted!")
    await websocket.send_json({"type": "test", "message": "Connected!"})
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_json({"type": "echo", "data": data})
    except Exception as e:
        logger.info(f"Test WebSocket closed: {e}")


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for realtime voice sessions.
    
    Audio Protocol:
    - Client sends: JSON messages with type "audio" containing int16 array
    - Server sends: JSON messages with audio bytes or event data
    """
    logger.info(f"WebSocket connection request for session: {session_id}")
    await session_manager.connect(websocket, session_id)
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message["type"] == "audio":
                # Convert int16 array to bytes
                int16_data = message["data"]
                audio_bytes = struct.pack(f"{len(int16_data)}h", *int16_data)
                await session_manager.send_audio(session_id, audio_bytes)
                
            elif message["type"] == "end_consultation":
                # Client requests to end consultation
                await session_manager.end_consultation(session_id)
                
            elif message["type"] == "interrupt":
                # Client interrupts current response
                await session_manager.interrupt(session_id)
                
    except WebSocketDisconnect:
        logger.info(f"Client disconnected: {session_id}")
        await session_manager.disconnect(session_id)
    except Exception as e:
        logger.error(f"Error in session {session_id}: {e}")
        await session_manager.disconnect(session_id)


@app.get("/feedback/{session_id}")
async def get_feedback(session_id: str):
    """
    Get feedback for a completed session.
    
    Returns 404 if session not found or feedback not ready.
    """
    feedback = session_manager.get_feedback(session_id)
    if feedback is None:
        return {"status": "pending", "message": "Feedback not ready yet"}
    return {"status": "ready", "feedback": feedback}


# Entry point for running standalone
if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "clinical_master.server:app",
        host="0.0.0.0",
        port=8001,  # Different port from Azure Functions
        reload=True,
        h11_max_incomplete_event_size=32768,  # Allow larger headers (cookies)
    )
