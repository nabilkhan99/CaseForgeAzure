"""
Clinical Master Configuration

Environment variables for Azure OpenAI (Realtime + Chat/feedback) and session settings.
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import Optional


# Find the .env file relative to this config file
_config_dir = Path(__file__).parent
_env_file = _config_dir / ".env"
if not _env_file.exists():
    # Fallback to parent directory
    _env_file = _config_dir.parent / ".env"


class ClinicalMasterSettings(BaseSettings):
    """Configuration for the Clinical Master service."""
    
    # Azure OpenAI - Shared endpoint & key
    AZURE_OPENAI_ENDPOINT: str = ""
    AZURE_OPENAI_API_KEY: str = ""
    
    # Azure OpenAI - Realtime (patient voice agent) — uses GA endpoint format (no api-version needed)
    AZURE_OPENAI_REALTIME_DEPLOYMENT: str = "gpt-realtime"
    DEFAULT_VOICE: str = "shimmer"
    TURN_DETECTION_TYPE: str = "semantic_vad"
    NOISE_REDUCTION_TYPE: str = "far_field"
    TURN_DETECTION_EAGERNESS: str = "low"
    
    # Azure OpenAI - Chat Completions (feedback generation)
    AZURE_OPENAI_CHAT_DEPLOYMENT: str = "gpt-4.1"
    AZURE_OPENAI_CHAT_API_VERSION: str = "2024-12-01-preview"
    AZURE_OPENAI_CHAT_API_KEY: Optional[str] = None  # Falls back to AZURE_OPENAI_API_KEY
    
    # Session settings
    CONSULTATION_DURATION_SECONDS: int = 300
    READING_DURATION_SECONDS: int = 180
    
    # Supabase
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    
    model_config = {
        "env_file": str(_env_file),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = ClinicalMasterSettings()
