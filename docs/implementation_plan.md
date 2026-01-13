# Implementation Plan: Clinical Master Agent
## Backend Development (No Frontend)

---

## Overview

This plan covers building the Python FastAPI backend with OpenAI Agents SDK for realtime voice-based patient simulation. The frontend is out of scope — we'll use a minimal test client for validation.

**Target:** A working voice agent that simulates a patient consultation with 2-minute timer and async feedback generation.

---

## Phase 1: Project Setup

### 1.1 Directory Structure

```
CaseForgeAzure/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app entry point
│   ├── config.py            # Environment config
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── patient.py       # Patient RealtimeAgent
│   │   └── feedback.py      # Text-based feedback Agent
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── examination.py   # Examination request tool
│   │   ├── investigation.py # Investigation results tool
│   │   └── timer.py         # Timer check tool
│   ├── session/
│   │   ├── __init__.py
│   │   └── manager.py       # WebSocket session management
│   └── models/
│       ├── __init__.py
│       ├── case.py          # Case/station data models
│       └── feedback.py      # Feedback output schema
├── tests/
│   ├── test_client.html     # Minimal browser test client
│   └── test_agent.py        # Agent unit tests
├── requirements.txt
├── pyproject.toml
└── .env.example
```

### 1.2 Dependencies

```txt
# requirements.txt
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
websockets>=12.0
openai-agents>=0.1.0
python-dotenv>=1.0.0
pydantic>=2.0.0
```

### 1.3 Environment Configuration

```python
# app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Azure OpenAI
    AZURE_OPENAI_ENDPOINT: str
    AZURE_OPENAI_API_KEY: str
    AZURE_OPENAI_DEPLOYMENT: str = "gpt-4o-realtime-preview"
    AZURE_OPENAI_API_VERSION: str = "2024-10-01-preview"
    
    # Session
    CONSULTATION_DURATION_SECONDS: int = 120  # 2 minutes
    
    class Config:
        env_file = ".env"

settings = Settings()
```

---

## Phase 2: Basic Voice Loop

### 2.1 FastAPI WebSocket Server

```python
# app/main.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from app.session.manager import SessionManager

app = FastAPI(title="Clinical Master API")
session_manager = SessionManager()

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await session_manager.connect(websocket, session_id)
    try:
        while True:
            data = await websocket.receive_bytes()
            await session_manager.handle_audio(session_id, data)
    except WebSocketDisconnect:
        await session_manager.disconnect(session_id)
```

### 2.2 Session Manager (Following SDK Pattern)

```python
# app/session/manager.py
from agents.realtime import RealtimeRunner, RealtimeSession
from app.agents.patient import get_patient_agent
from app.config import settings

class SessionManager:
    def __init__(self):
        self.active_sessions: dict[str, RealtimeSession] = {}
        self.websockets: dict[str, WebSocket] = {}
        self.transcripts: dict[str, list] = {}
    
    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.websockets[session_id] = websocket
        self.transcripts[session_id] = []
        
        # Create patient agent and start session
        agent = get_patient_agent()
        runner = RealtimeRunner(agent)
        
        model_config = {
            "api_type": "azure",
            "api_base": settings.AZURE_OPENAI_ENDPOINT,
            "api_key": settings.AZURE_OPENAI_API_KEY,
            "deployment_name": settings.AZURE_OPENAI_DEPLOYMENT,
            "initial_model_settings": {
                "turn_detection": {
                    "type": "server_vad",
                    "silence_duration_ms": 500,
                },
                "audio": {"voice": "marin"}
            }
        }
        
        session_context = await runner.run(model_config=model_config)
        session = await session_context.__aenter__()
        self.active_sessions[session_id] = session
        
        # Start event processing
        asyncio.create_task(self._process_events(session_id))
```

---

## Phase 3: Patient Agent

### 3.1 Agent Definition

```python
# app/agents/patient.py
from agents.realtime import RealtimeAgent
from app.tools.examination import request_examination
from app.tools.investigation import get_investigation_result

PATIENT_PROMPT = """
# Identity
You are Margaret Thompson, a 58-year-old retired teacher presenting with chest pain.

# Personality & Demeanor
- Speaking style: Slightly anxious, provides moderate detail
- Affect: Worried but cooperative
- Health literacy: Medium

# Presenting Complaint
You've had chest pain for the last 3 days. It's worse when you climb stairs.
The pain is central, feels like pressure, and sometimes goes to your left arm.

# Medical History (reveal when asked)
- Hypertension (on amlodipine 5mg)
- Type 2 diabetes (on metformin 500mg twice daily)
- Father had heart attack at age 62
- Smoker: 10 cigarettes/day for 30 years

# Red Flags (ONLY reveal if specifically asked)
- Pain woke you up last night
- Occasional breathlessness at rest
- Ankles slightly swollen

# Critical Rules
- NEVER diagnose yourself
- NEVER suggest you might have a heart problem
- If the trainee misses red flags, do NOT volunteer them
- Stay in character as an anxious patient
"""

def get_patient_agent() -> RealtimeAgent:
    return RealtimeAgent(
        name="Patient",
        instructions=PATIENT_PROMPT,
        tools=[request_examination, get_investigation_result],
    )
```

### 3.2 Examination Tool

```python
# app/tools/examination.py
from agents import function_tool

EXAMINATION_FINDINGS = {
    "cardiovascular": "Blood pressure 165/95. Heart sounds: regular, no murmurs. Mild bilateral ankle oedema.",
    "respiratory": "Chest clear. No wheeze or crackles.",
    "abdominal": "Soft, non-tender. No organomegaly.",
}

@function_tool
async def request_examination(examination_type: str) -> str:
    """
    The trainee requests to examine the patient.
    Returns the examination findings.
    
    Args:
        examination_type: Type of examination (cardiovascular, respiratory, abdominal, etc.)
    """
    finding = EXAMINATION_FINDINGS.get(
        examination_type.lower(), 
        "No abnormality detected."
    )
    return f"Examination findings ({examination_type}): {finding}"
```

### 3.3 Investigation Tool

```python
# app/tools/investigation.py
from agents import function_tool

INVESTIGATION_RESULTS = {
    "ecg": "Sinus rhythm. ST depression in leads V4-V6. T wave inversion in lead aVL.",
    "blood_pressure": "165/95 mmHg",
    "pulse": "88 bpm, regular",
    "oxygen_saturation": "97% on room air",
    "blood_glucose": "8.2 mmol/L (random)",
}

@function_tool
async def get_investigation_result(investigation: str) -> str:
    """
    The trainee requests an investigation result.
    
    Args:
        investigation: Type of investigation (ECG, blood pressure, pulse, etc.)
    """
    result = INVESTIGATION_RESULTS.get(
        investigation.lower().replace(" ", "_"),
        "Result not available."
    )
    return f"{investigation}: {result}"
```

---

## Phase 4: Session Management

### 4.1 Timer Implementation

```python
# app/tools/timer.py
import asyncio
from datetime import datetime, timedelta
from agents import function_tool

class ConsultationTimer:
    def __init__(self, duration_seconds: int = 120):
        self.duration = duration_seconds
        self.start_time: datetime | None = None
        self.end_callback = None
    
    def start(self, on_end_callback):
        self.start_time = datetime.now()
        self.end_callback = on_end_callback
        asyncio.create_task(self._countdown())
    
    async def _countdown(self):
        await asyncio.sleep(self.duration)
        if self.end_callback:
            await self.end_callback()
    
    def remaining_seconds(self) -> int:
        if not self.start_time:
            return self.duration
        elapsed = (datetime.now() - self.start_time).total_seconds()
        return max(0, int(self.duration - elapsed))

# Global timer reference (will be set per session)
_session_timers: dict[str, ConsultationTimer] = {}

@function_tool
async def check_timer() -> str:
    """Check remaining consultation time."""
    # Note: session_id would need to be injected via context
    remaining = 60  # Placeholder
    if remaining <= 30:
        return f"WARNING: Only {remaining} seconds remaining. Please wrap up the consultation."
    return f"{remaining} seconds remaining."
```

### 4.2 Transcript Capture

```python
# In session/manager.py - extend _process_events

async def _process_events(self, session_id: str):
    session = self.active_sessions[session_id]
    websocket = self.websockets[session_id]
    
    async for event in session:
        # Capture transcript
        if event.type == "history_added":
            self.transcripts[session_id].append({
                "role": event.item.role,
                "content": self._extract_content(event.item),
                "timestamp": datetime.now().isoformat()
            })
        
        # Relay audio to browser
        if event.type == "audio":
            await websocket.send_bytes(event.audio.data)
        
        # Handle session end
        if event.type == "agent_end":
            await self._trigger_feedback(session_id)
```

---

## Phase 5: Feedback Pipeline

### 5.1 Feedback Agent (Text-Based)

```python
# app/agents/feedback.py
from agents import Agent, Runner
from pydantic import BaseModel

class DomainScore(BaseModel):
    domain: str
    score: int  # 0-100
    strengths: list[str]
    improvements: list[str]

class ConsultationFeedback(BaseModel):
    data_gathering: DomainScore
    clinical_management: DomainScore
    interpersonal_skills: DomainScore
    overall_summary: str
    key_learning_points: list[str]

FEEDBACK_PROMPT = """
You are an RCGP SCA examiner providing feedback on a GP trainee's consultation.

Analyze the transcript against these domains:
1. Data Gathering - History taking, systematic questioning, red flag identification
2. Clinical Management - Diagnosis, treatment plan, safety-netting, follow-up
3. Interpersonal Skills - Rapport, empathy, patient-centered approach, communication

For this case (Margaret Thompson, 58, chest pain):
- Key history points: Duration, character, radiation, exacerbating factors, cardiac risk factors
- Red flags: Pain at rest, waking from sleep, breathlessness, ankle swelling
- Expected management: Urgent referral, ECG, cardiac enzymes, safety-net advice

Provide specific, actionable feedback with timestamps where relevant.
"""

feedback_agent = Agent(
    name="Feedback Examiner",
    instructions=FEEDBACK_PROMPT,
    output_type=ConsultationFeedback,
)

async def generate_feedback(transcript: list[dict], case_brief: str) -> ConsultationFeedback:
    transcript_text = "\n".join([
        f"[{t['timestamp']}] {t['role']}: {t['content']}" 
        for t in transcript
    ])
    
    result = await Runner.run(
        feedback_agent,
        input=f"Case: {case_brief}\n\nTranscript:\n{transcript_text}"
    )
    return result.final_output
```

### 5.2 Async Feedback Trigger

```python
# In session/manager.py

async def _trigger_feedback(self, session_id: str):
    """Called when consultation ends - triggers async feedback generation."""
    transcript = self.transcripts.get(session_id, [])
    
    # Fire and forget - feedback generates in background
    asyncio.create_task(self._generate_and_store_feedback(session_id, transcript))
    
    # Notify client that consultation ended
    websocket = self.websockets.get(session_id)
    if websocket:
        await websocket.send_json({
            "type": "consultation_ended",
            "message": "Generating feedback..."
        })

async def _generate_and_store_feedback(self, session_id: str, transcript: list):
    from app.agents.feedback import generate_feedback
    
    feedback = await generate_feedback(transcript, CASE_BRIEF)
    
    # Store feedback (would go to Supabase in production)
    self.feedback_results[session_id] = feedback
    
    # Notify client feedback is ready
    websocket = self.websockets.get(session_id)
    if websocket:
        await websocket.send_json({
            "type": "feedback_ready",
            "feedback": feedback.model_dump()
        })
```

---

## Phase 6: Test Client

### 6.1 Minimal Browser Test Client

```html
<!-- tests/test_client.html -->
<!DOCTYPE html>
<html>
<head>
    <title>Clinical Master Test</title>
</head>
<body>
    <h1>Clinical Master - Voice Test</h1>
    <button id="connect">Connect</button>
    <button id="disconnect" disabled>Disconnect</button>
    <div id="status">Disconnected</div>
    <div id="transcript"></div>
    
    <script>
        let ws;
        let audioContext;
        let mediaStream;
        
        document.getElementById('connect').onclick = async () => {
            const sessionId = crypto.randomUUID();
            ws = new WebSocket(`ws://localhost:8000/ws/${sessionId}`);
            
            ws.onopen = async () => {
                document.getElementById('status').textContent = 'Connected';
                document.getElementById('connect').disabled = true;
                document.getElementById('disconnect').disabled = false;
                
                // Start audio capture
                mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
                // ... audio processing code
            };
            
            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                if (data.type === 'feedback_ready') {
                    document.getElementById('transcript').innerHTML = 
                        `<pre>${JSON.stringify(data.feedback, null, 2)}</pre>`;
                }
            };
        };
    </script>
</body>
</html>
```

---

## Milestones & Validation

| Phase | Milestone | Validation |
|-------|-----------|------------|
| 1 | Project compiles | `uvicorn app.main:app` starts without errors |
| 2 | Voice loop works | Can hear audio response from hardcoded greeting |
| 3 | Patient responds | Can have basic conversation with patient |
| 4 | Timer enforces | Session auto-ends at 2 minutes |
| 5 | Feedback generates | Receive structured feedback JSON after session |
| 6 | End-to-end | Complete consultation + feedback via test client |

---

## Out of Scope (For Now)

- Frontend UI (using test client only)
- Database persistence (in-memory for now)
- Multiple cases (single hardcoded case)
- User authentication
- Production deployment configuration
