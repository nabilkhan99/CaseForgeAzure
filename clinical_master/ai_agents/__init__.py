# AI Agents module

import os
from config import settings

# Ensure GOOGLE_API_KEY is set in environment for google-genai (feedback agent)
if settings.GOOGLE_API_KEY and not os.environ.get("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = settings.GOOGLE_API_KEY

from .feedback import generate_feedback, ConsultationFeedback
from .patient import build_patient_prompt

__all__ = ["generate_feedback", "ConsultationFeedback", "build_patient_prompt"]
