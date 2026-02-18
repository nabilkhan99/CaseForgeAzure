"""
Clinical Master Configuration

Environment-based settings for ADK Gemini Live voice agent,
feedback generation, and session management.
"""

from pathlib import Path

from pydantic_settings import BaseSettings

# Resolve .env relative to this file (clinical_master/.env),
# not relative to the CWD which may be the parent monorepo dir.
_ENV_FILE = Path(__file__).parent / ".env"


class ClinicalMasterSettings(BaseSettings):
    """Settings loaded from environment variables."""

    # --- Gemini AI ---
    GOOGLE_API_KEY: str = ""
    GOOGLE_GENAI_USE_VERTEXAI: str = "0"

    # Model for real-time voice patient agent (native audio)
    GEMINI_LIVE_MODEL: str = "gemini-2.5-flash-native-audio-preview-12-2025"

    # Model for text-based feedback generation
    GEMINI_FEEDBACK_MODEL: str = "gemini-2.5-flash"

    # Voice preset for the patient agent
    DEFAULT_VOICE: str = "Kore"

    # --- Session ---
    CONSULTATION_DURATION_SECONDS: int = 480  # 8 minutes default
    READING_TIME_SECONDS: int = 180  # 3 minutes reading time

    # --- Database (Supabase) ---
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""

    class Config:
        env_file = str(_ENV_FILE)
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = ClinicalMasterSettings()
