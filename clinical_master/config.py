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
    AZURE_OPENAI_API_KEY: str = ""  # Primary key (for realtime)
    
    # Realtime API (voice)
    AZURE_OPENAI_REALTIME_DEPLOYMENT: str = "gpt-realtime"
    AZURE_OPENAI_REALTIME_API_VERSION: str = "2024-10-01-preview"
    
    # Chat Completions API (text/feedback)
    AZURE_OPENAI_CHAT_DEPLOYMENT: str = "gpt-4.1"
    AZURE_OPENAI_CHAT_API_VERSION: str = "2024-12-01-preview"
    AZURE_OPENAI_CHAT_API_KEY: str = ""  # Chat deployment key (if different from primary)
    
    # Session Configuration
    CONSULTATION_DURATION_SECONDS: int = 300  # 5 minutes for consultation
    READING_DURATION_SECONDS: int = 180  # 3 minutes for reading
    
    # Supabase Configuration
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    
    # Voice settings (marin or cedar recommended for best quality)
    DEFAULT_VOICE: str = "marin"
    
    # Turn detection settings
    # Using semantic_vad (recommended by OpenAI) instead of server_vad
    # semantic_vad provides more intelligent turn detection based on semantic understanding
    # Note: server_vad settings (silence_duration_ms, prefix_padding_ms) are not used with semantic_vad
    TURN_DETECTION_TYPE: str = "semantic_vad"
    
    # Noise reduction settings (near_field for typical microphone use, far_field for speaker)
    NOISE_REDUCTION_TYPE: str = "near_field"
    
    class Config:
        env_file = str(_env_file)
        env_file_encoding = "utf-8"
        extra = "ignore"  # Ignore extra env vars from existing app


# Singleton instance
settings = ClinicalMasterSettings()
