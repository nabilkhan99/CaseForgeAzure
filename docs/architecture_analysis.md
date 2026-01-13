# Technical Architecture Analysis
## Fourteen Fisherman — Clinical Master

---

## Executive Summary

After reviewing your codebase, documentation, and the OpenAI Agents SDK, here are my thoughts on building Clinical Master — a voice-first medical exam simulator for the RCGP SCA.

**The core challenge:** Create a realtime voice agent that simulates an AI patient for GP trainees to practice clinical consultations, with structured feedback aligned to SCA marking criteria.

---

## Confirmed Requirements

| Question | Answer |
|----------|--------|
| Azure OpenAI `gpt-4o-realtime-preview` access | ✅ Yes |
| Session duration | **2-minute hard cutoff** (not 10 mins — adjusted for testing/demo) |
| Feedback timing | **Immediate but async** — user sees feedback quickly, processing happens in background |
| Case data structure | **Not yet** — needs basic implementation first, will be refined later |
| CaseForgeFrontend status | **Being adapted** — existing codebase, not a fresh start |

---

## Proposed Technology Stack

| Layer | Technology | Rationale |
|-------|------------|-----------|
| **Frontend** | Next.js (React) on Vercel | Already in `CaseForgeFrontend`, well-suited for the dashboard, station library, and feedback UI |
| **Voice Client** | WebSocket to FastAPI backend | Server-side control for tools, transcripts, and timer enforcement |
| **Backend** | FastAPI (Python) on Azure | Orchestrates the agent, manages sessions, relays audio via WebSocket |
| **Realtime API** | Azure OpenAI Foundry (gpt-realtime) | Enterprise deployment, HIPAA-aligned, regional data residency |
| **Agent Framework** | OpenAI Agents SDK (Python) | Native realtime agent support, handoffs, function tools, guardrails |
| **Database** | Supabase / PostgreSQL | Station content, user progress, session history, feedback storage |
| **Auth** | Supabase Auth | Already integrated in your frontend patterns |

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER (Browser)                                 │
│  ┌─────────────────┐    ┌───────────────────┐    ┌───────────────────────┐  │
│  │  Next.js UI     │    │  WebRTC Audio     │    │  Station Library /    │  │
│  │  (Dashboard)    │    │  (Mic + Speaker)  │    │  Feedback Display     │  │
│  └────────┬────────┘    └─────────┬─────────┘    └───────────────────────┘  │
│           │                       │                                          │
│           │ REST/GraphQL          │ WebSocket                                │
│           ▼                       ▼                                          │
└───────────────────────────────────────────────────────────────────────────────
                    │                       │
                    ▼                       ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│                         FASTAPI BACKEND (Azure)                               │
│  ┌─────────────────────────────────────────────────────────────────────────┐  │
│  │                    Session Manager                                       │  │
│  │  • Creates/manages RealtimeSession per user                             │  │
│  │  • Maintains consultation state (timer, phase)                          │  │
│  │  • Stores transcript for feedback generation                            │  │
│  └─────────────────────────────────────────────────────────────────────────┘  │
│                                    │                                          │
│                                    ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────────────┐  │
│  │                    RealtimeRunner (Agents SDK)                           │  │
│  │  ┌─────────────────────────┐    ┌─────────────────────────┐             │  │
│  │  │   Patient Agent         │◄───│   Handoff: Feedback     │             │  │
│  │  │   (Main simulation)     │    │   Agent                 │             │  │
│  │  └─────────────────────────┘    └─────────────────────────┘             │  │
│  │                                                                          │  │
│  │  Tools: timer_check, save_transcript, request_examination, end_consult  │  │
│  └─────────────────────────────────────────────────────────────────────────┘  │
│                                    │                                          │
│                                    ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────────────┐  │
│  │         WebSocket → Azure OpenAI Foundry (gpt-realtime)                 │  │
│  └─────────────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼ Post-consultation
┌───────────────────────────────────────────────────────────────────────────────┐
│                         FEEDBACK PIPELINE (Async)                             │
│  ┌─────────────────┐    ┌─────────────────┐    ┌───────────────────────────┐  │
│  │  Transcript     │ →  │  GPT-4.1 Agent  │ →  │  Structured Feedback      │  │
│  │  + Case Brief   │    │  (Text-based)   │    │  (Domain scores, points)  │  │
│  └─────────────────┘    └─────────────────┘    └───────────────────────────┘  │
└───────────────────────────────────────────────────────────────────────────────┘
```

---

## Key Architectural Decisions

### 1. Dual WebSocket Architecture (Not Direct WebRTC)

**The two connections:**
```
Browser ←──WebSocket──→ FastAPI ←──WebSocket──→ Azure OpenAI
```

**Why not WebRTC directly from browser to OpenAI?**
- WebRTC would bypass the server entirely
- We'd lose the ability to run agent tools, log transcripts, and enforce timers
- No server-side orchestration = no Clinical Master features

**Why WebSocket relay via FastAPI?**
- Server can intercept and process all events
- Enables function tools (examination results, timer checks)
- Captures full transcript for async feedback generation
- Follows the pattern in `openai-agents-python/examples/realtime/app/server.py`

Per the docs:
> "For anything where you are executing the agent server-side... WebSockets will be the better option."

### 2. Speech-to-Speech (Not Chained) Architecture

**Why:** The SCA exam tests how trainees respond to tone, hesitation, and emotional cues. The realtime model's S2S architecture:

- Hears emotion and intent directly (doesn't rely on transcription)
- Responds naturally with appropriate pacing
- Lower latency for fluid conversation

This is exactly what the voice agents docs recommend for "interactive learning experiences."

### 3. Agent Handoffs for Consultation Phases

Based on the SDK examples, use handoffs to transition between consultation phases:

```python
from agents.realtime import RealtimeAgent, realtime_handoff

patient_agent = RealtimeAgent(
    name="Patient",
    instructions=PATIENT_PROMPT,  # Case-specific personality, presenting complaint
    tools=[request_examination, share_results],
    handoffs=[end_consultation_agent]
)

end_consultation_agent = RealtimeAgent(
    name="Consultation End Handler",
    instructions="Wrap up the consultation naturally when the trainee indicates they're done.",
    handoffs=[]  # Terminal state
)
```

### 4. Session State Management

The SDK's `server.py` example shows the pattern:

```python
class RealtimeWebSocketManager:
    def __init__(self):
        self.active_sessions: dict[str, RealtimeSession] = {}
        self.websockets: dict[str, WebSocket] = {}
```

You'll need to extend this to track:
- Current station/case
- Consultation timer (2 minutes for testing)
- Reading phase completion
- Transcript buffer for feedback

### 5. Prompt Architecture for AI Patients

Following the realtime prompting guide, structure prompts with clear sections:

```markdown
# Identity
You are {patient_name}, a {age}-year-old {occupation} presenting with {chief_complaint}.

# Personality & Demeanor
- Speaking style: {brief/verbose/anxious/stoic}
- Affect: {worried/calm/frustrated}
- Health literacy: {low/medium/high}

# Medical History (revealed progressively)
- Present complaint: {symptoms, duration, triggers}
- Past medical history: {relevant conditions}
- Medications: {current medications}
- Red flags to WITHHOLD unless specifically asked: {critical findings}

# Conversation Flow
1. GREETING: State your reason for visit naturally
2. HISTORY: Answer questions honestly but don't volunteer everything
3. EXAMINATION: Report findings when examination tool is called
4. CLOSURE: React to the management plan

# Critical Rules
- NEVER diagnose yourself
- NEVER suggest treatments
- If the trainee misses a red flag, do NOT mention it
- Stay in character throughout
```

---

## Data Flow: Complete Consultation Cycle

### Phase 1: Station Selection (REST)
```
Frontend → GET /api/stations/{domain} → Supabase → Station list
Frontend → GET /api/stations/{id}/brief → Candidate brief for reading
```

### Phase 2: Reading Time (Timer only, no voice)
```
Frontend: Display brief, start 2-minute timer, notepad active
```

### Phase 3: Live Consultation (WebSocket + Realtime)
```
1. Frontend opens WebSocket to /ws/{session_id}
2. Backend creates RealtimeRunner with Patient Agent
3. Backend configures Azure OpenAI session with:
   - Patient prompt (from station data)
   - Voice: appropriate for patient persona
   - VAD: server_vad with semantic detection
4. Audio flows bidirectionally:
   Browser Mic → WS → Backend → Azure → Backend → WS → Browser Speaker
5. Backend logs all transcript events
6. Timer triggers auto-end at 2 minutes
7. End consultation tool triggers session close
```

### Phase 4: Feedback Generation (Immediate + Async)
```
1. Session ends → immediately queue feedback job
2. Backend sends full transcript + case brief to text-based Agent
3. Agent analyzes against SCA domains:
   - Data Gathering: Did they ask about X, Y, Z?
   - Clinical Management: Was safety-netting addressed?
   - Interpersonal Skills: Tone, empathy markers
4. Structured output stored to Supabase
5. Frontend polls/websocket for feedback readiness
6. Display feedback as soon as available
```

---

## Function Tools for Patient Agent

```python
@function_tool
async def request_examination(examination_type: str) -> str:
    """
    Trainee requests a physical examination.
    Returns the examination findings for this case.
    
    Args:
        examination_type: Type of examination (e.g., "cardiovascular", "abdominal")
    """
    # Lookup findings from case data
    return case_data.examinations.get(examination_type, "No abnormality detected.")

@function_tool
async def get_investigation_result(investigation: str) -> str:
    """
    Trainee requests an investigation result.
    Returns the result if available for this case.
    
    Args:
        investigation: Type of investigation (e.g., "blood pressure", "ECG")
    """
    return case_data.investigations.get(investigation, "Result pending.")

@function_tool
async def check_timer() -> str:
    """Check remaining consultation time."""
    remaining = session.end_time - datetime.now()
    return f"{remaining.seconds} seconds remaining"

@function_tool
async def end_consultation() -> str:
    """Trainee indicates they want to end the consultation."""
    session.mark_complete()
    return "Consultation ended. The patient thanks you and leaves."
```

---

## Key Technical Considerations

### 1. Azure OpenAI Foundry Configuration

You'll need to configure the SDK to use Azure endpoints:

```python
from agents.realtime.model import RealtimeModelConfig

model_config: RealtimeModelConfig = {
    "api_type": "azure",
    "api_base": "https://your-resource.openai.azure.com/",
    "api_version": "2024-10-01-preview",
    "deployment_name": "gpt-4-realtime-preview",
    "initial_model_settings": {
        "turn_detection": {"type": "semantic_vad"},
        "audio": {"voice": "marin"}
    }
}
```

### 2. Audio Handling

The SDK handles most audio complexity, but note:
- Input: 24kHz PCM16 mono
- Output: Configurable (PCM16 or μ-law for telephony)
- Browser needs `getUserMedia` permissions

### 3. Transcript Storage

For feedback generation, you need the full transcript. The SDK emits `history_updated` and `history_added` events. Buffer these:

```python
transcript_items = []

async for event in session:
    if event.type == "history_added":
        transcript_items.append(event.item)
```

### 4. Latency Considerations

- **WebSocket to Azure:** Choose Azure region closest to users (UK South for UK trainees)
- **VAD settings:** `prefix_padding_ms: 300`, `silence_duration_ms: 500` (per SDK examples)
- **Frontend buffering:** Minimize audio buffer size for responsiveness

### 5. Error Handling & Recovery

The SDK provides `error` events. Handle:
- Network disconnection (reconnect logic)
- Session timeout (60 min max per OpenAI)
- Model errors (fallback messaging)

---

## SDK Source Reference

Key files in `openai-agents-python/src/agents/realtime/`:

| File | Purpose |
|------|---------|
| `agent.py` | `RealtimeAgent` class definition |
| `runner.py` | `RealtimeRunner` orchestration |
| `session.py` | `RealtimeSession` state management (37KB — the core logic) |
| `openai_realtime.py` | OpenAI API integration (53KB) |
| `config.py` | Configuration types including `RealtimeModelConfig` |
| `events.py` | Event types emitted by the session |
| `handoffs.py` | Handoff utilities for agent transitions |
| `items.py` | Conversation item types |

---

## Summary

Clinical Master will use:

1. **Next.js frontend** (adapted from CaseForgeFrontend) on Vercel
2. **FastAPI backend** with OpenAI Agents SDK on Azure
3. **Azure OpenAI Foundry** for `gpt-4o-realtime-preview` via WebSocket
4. **Speech-to-speech architecture** for natural patient simulation
5. **Agent handoffs** for consultation phase management
6. **Async feedback pipeline** with immediate delivery using GPT-4.1

The architecture leverages the patterns from the SDK examples you provided, particularly the FastAPI WebSocket manager from `examples/realtime/app/server.py`.
