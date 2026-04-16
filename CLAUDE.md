# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Product

**Fourteen Fisherman** — medical education SaaS for GP trainees preparing for the SCA exam. This repo contains two independent Python services sharing no code.

## Commands

**Azure Functions API (root):**
```bash
pip install -r requirements.txt
func start                          # Requires Azure Functions Core Tools v4
```

**Clinical Master voice agent:**
```bash
cd clinical_master
uv sync                             # Install deps (or: pip install -r requirements.txt)
uv run python agent.py start        # Start LiveKit voice agent
pytest                              # Run all tests
pytest tests/test_patient_prompt.py # Single test file
```

## Architecture

### 1. Azure Functions API (root)

Portfolio CCR (case commentary review) generation using RCGP guidelines. Has active users.

- **Entrypoint:** `function_app.py` — registers 6 HTTP-triggered functions, anonymous auth
- **Route prefix:** `/api/` (configured in `host.json`)
- **Core logic:** `app/services/portfolio_service.py` → Azure OpenAI GPT-4.1-mini
- **Config:** `app/config.py` (~68KB) — full RCGP system prompts, capability definitions, few-shot examples. **Edit with extreme care.**
- **Text parsing:** `app/utils/text_processing.py` — parses raw LLM output into structured sections
- **CORS:** Allowed origins in `host.json` — `localhost:3000`, `fourteenfisherman.com`, Vercel preview URLs

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/capabilities` | GET | All RCGP capabilities |
| `/api/generate-review` | POST | Full CCR from case + 1–3 capabilities |
| `/api/improve-review` | POST | Iteratively improve review |
| `/api/improve-section` | POST | Improve single section |
| `/api/select-capabilities` | POST | AI-select capabilities from case |
| `/api/select-experience-groups` | POST | AI-select experience groups |

### 2. Clinical Master Voice Agent (`clinical_master/`)

LiveKit voice agent simulating a patient for SCA consultation practice. Python 3.11+, managed with `uv`.

**Pipeline:** STT (Deepgram Nova-3) → LLM (GPT-4.1-mini) → TTS (Cartesia Sonic-3)

**Key files:**
- `agent.py` — `PatientAgent(Agent)` subclass. Entrypoint, timer management, transcript capture
- `ai_agents/patient.py` — Builds patient system prompt from Supabase station data. Strips stage directions before TTS.
- `ai_agents/feedback.py` — Post-consultation feedback via Gemini 2.5-flash. Returns `ConsultationFeedback` Pydantic model scored on 3 SCA domains (data_gathering, clinical_management, interpersonal_skills)
- `db/session_repository.py` + `db/supabase_client.py` — All Supabase CRUD
- `config.py` — `pydantic_settings.BaseSettings`, loads from `clinical_master/.env`
- `tests/` — pytest tests (dev dependency: `pytest`, `pytest-asyncio`)

**Session lifecycle:**
1. Frontend creates session in Supabase → redirects to session page
2. Frontend requests LiveKit token → room created with session metadata
3. LiveKit dispatches `agent.py` into room
4. `on_enter()` → loads station from Supabase, sets session status "live", starts consultation timer (default 8 min)
5. Consultation runs; transcript accumulated per turn
6. `on_session_end()` → sends transcript to Gemini → `ConsultationFeedback` saved to Supabase

**Supabase tables:**
- `stations` — case definitions (patient_name, age, script, consultation_duration_seconds)
- `clinical_sessions` — session state (reading → live → completed)
- `domains` — SCA marking domains

## Environment Variables

**Root (Azure Functions)** — `local.settings.json`:
```
AZURE_OPENAI_API_KEY
AZURE_OPENAI_ENDPOINT
AZURE_OPENAI_DEPLOYMENT       # gpt-4.1-mini
AZURE_OPENAI_API_VERSION      # 2025-01-01-preview
```

**Clinical Master** — `clinical_master/.env` (see `.env.example`):
```
GOOGLE_API_KEY                # Gemini
GEMINI_FEEDBACK_MODEL         # gemini-2.5-flash
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
LIVEKIT_URL
LIVEKIT_API_KEY
LIVEKIT_API_SECRET
```

## Deployment

CI/CD via GitHub Actions:
- `.github/workflows/main_caseforge2025.yml` — Azure Functions API
- `.github/workflows/deploy-clinical-master.yml` — Clinical Master Docker image (`Dockerfile.clinical-master`)

## Frontend Dependency

The Next.js frontend lives in a sibling repo at `../CaseForgeFrontend/`. It proxies `/api/*` to `localhost:8000` during local dev.
