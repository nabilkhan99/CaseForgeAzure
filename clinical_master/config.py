"""
Clinical Master Configuration

Environment variables for ElevenLabs, Azure OpenAI (feedback), and session settings.
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
    """Configuration for Clinical Master voice agent."""
    
    # ── ElevenLabs Configuration ──
    ELEVENLABS_API_KEY: str = ""
    ELEVENLABS_AGENT_ID: str = ""
    
    # ── Azure OpenAI Configuration (for feedback generation only) ──
    AZURE_OPENAI_ENDPOINT: str = ""
    AZURE_OPENAI_API_KEY: str = ""
    
    # Chat Completions API (used by feedback agent)
    AZURE_OPENAI_CHAT_DEPLOYMENT: str = "gpt-4.1"
    AZURE_OPENAI_CHAT_API_VERSION: str = "2024-12-01-preview"
    AZURE_OPENAI_CHAT_API_KEY: str = ""
    
    # ── Session Configuration ──
    CONSULTATION_DURATION_SECONDS: int = 300  # 5 minutes for consultation
    READING_DURATION_SECONDS: int = 180  # 3 minutes for reading
    
    # ── Supabase Configuration ──
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    
    class Config:
        env_file = str(_env_file)
        env_file_encoding = "utf-8"
        extra = "ignore"


# Singleton instance
settings = ClinicalMasterSettings()
