"""
Clinical Master Configuration

Environment variables for Azure OpenAI and session settings.
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
    
    # Azure OpenAI Configuration
    AZURE_OPENAI_ENDPOINT: str = ""
    AZURE_OPENAI_API_KEY: str = ""
    AZURE_OPENAI_REALTIME_DEPLOYMENT: str = "gpt-realtime"
    AZURE_OPENAI_API_VERSION: str = "2024-10-01-preview"
    
    # Text model for feedback generation (can use existing deployment)
    AZURE_OPENAI_CHAT_DEPLOYMENT: str = "gpt-4"
    
    # Session Configuration
    CONSULTATION_DURATION_SECONDS: int = 120  # 2 minutes for testing
    
    # Voice settings
    DEFAULT_VOICE: str = "marin"
    
    # VAD settings
    VAD_SILENCE_DURATION_MS: int = 500
    VAD_PREFIX_PADDING_MS: int = 300
    
    class Config:
        env_file = str(_env_file)
        env_file_encoding = "utf-8"
        extra = "ignore"  # Ignore extra env vars from existing app


# Singleton instance
settings = ClinicalMasterSettings()
