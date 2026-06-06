# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Product

**Fourteen Fisherman** — medical education SaaS for GP trainees preparing for the SCA exam. This repo is the **Portfolio tool** backend: an Azure Functions API for RCGP portfolio CCR generation.

> The Clinical Master **voice** agent used to live here (`clinical_master/`, LiveKit) but was removed — the browser now talks directly to Azure `gpt-realtime` from the frontend (`../CaseForgeFrontend`). See tag `pre-gpt-realtime-migration` for the last state that included it.

## Commands

**Azure Functions API (root):**
```bash
pip install -r requirements.txt
func start                          # Requires Azure Functions Core Tools v4
```

## Architecture

### Azure Functions API (root)

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

## Environment Variables

**Root (Azure Functions)** — `local.settings.json`:
```
AZURE_OPENAI_API_KEY
AZURE_OPENAI_ENDPOINT
AZURE_OPENAI_DEPLOYMENT       # gpt-4.1-mini
AZURE_OPENAI_API_VERSION      # 2025-01-01-preview
```

## Deployment

CI/CD via GitHub Actions:
- `.github/workflows/main_caseforge2025.yml` — Azure Functions API

## Frontend Dependency

The Next.js frontend lives in a sibling repo at `../CaseForgeFrontend/`. It proxies the 6 portfolio `/api/*` endpoints to `localhost:8000` during local dev.
