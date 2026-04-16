"""
Clinical Master Configuration

Environment-based settings for LiveKit voice agent and session management.
Feedback generation runs in a Supabase Edge Function, not this process.
"""

from pathlib import Path

from pydantic_settings import BaseSettings

# Resolve .env relative to this file (clinical_master/.env),
# not relative to the CWD which may be the parent monorepo dir.
_ENV_FILE = Path(__file__).parent / ".env"


class ClinicalMasterSettings(BaseSettings):
    """Settings loaded from environment variables."""

    # --- Session ---
    CONSULTATION_DURATION_SECONDS: int = 480  # 8 minutes default
    READING_TIME_SECONDS: int = 180  # 3 minutes reading time

    # --- Database (Supabase) ---
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""

    # --- LiveKit (read automatically by LiveKit SDK from env) ---
    # LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET
    # These don't need to be in this settings class — the SDK reads them directly.

    class Config:
        env_file = str(_ENV_FILE)
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = ClinicalMasterSettings()
