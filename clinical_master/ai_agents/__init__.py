# AI Agents module
# Configure Gemini for ADK agents

import os
import sys
from pathlib import Path

# Handle imports for both package and script modes
try:
    from ..config import settings
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from clinical_master.config import settings

# Ensure GOOGLE_API_KEY is set in environment for google-genai / ADK
if settings.GOOGLE_API_KEY and not os.environ.get("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = settings.GOOGLE_API_KEY

if settings.GOOGLE_GENAI_USE_VERTEXAI and not os.environ.get("GOOGLE_GENAI_USE_VERTEXAI"):
    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = settings.GOOGLE_GENAI_USE_VERTEXAI

from .feedback import generate_feedback, ConsultationFeedback
from .patient import get_patient_agent, build_patient_prompt

__all__ = ["generate_feedback", "ConsultationFeedback", "get_patient_agent", "build_patient_prompt"]
