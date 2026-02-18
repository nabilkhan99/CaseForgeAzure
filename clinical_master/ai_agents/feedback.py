"""
Feedback Agent

Text-based agent that analyzes consultation transcripts
and generates structured feedback aligned with SCA marking domains.

Uses Gemini via google-genai for single-shot structured output.
"""

import json
import logging
import sys
from pathlib import Path
from typing import List

from google import genai
from google.genai import types as genai_types
from pydantic import BaseModel, Field

# Handle imports for both package and script modes
try:
    from ..config import settings
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from clinical_master.config import settings

logger = logging.getLogger(__name__)


class DomainScore(BaseModel):
    """Score for a single assessment domain."""
    domain: str = Field(description="Name of the domain")
    score: int = Field(ge=0, le=100, description="Score out of 100")
    strengths: List[str] = Field(description="What the trainee did well")
    improvements: List[str] = Field(description="Areas for improvement")


class ConsultationFeedback(BaseModel):
    """Structured feedback for a consultation."""
    data_gathering: DomainScore = Field(description="Assessment of history taking and information gathering")
    clinical_management: DomainScore = Field(description="Assessment of diagnosis, management plan, and safety-netting")
    interpersonal_skills: DomainScore = Field(description="Assessment of communication, empathy, and rapport")
    overall_summary: str = Field(description="Brief overall summary of the consultation")
    key_learning_points: List[str] = Field(description="3-5 key takeaways for the trainee")


FEEDBACK_PROMPT = """
You are an experienced RCGP SCA examiner providing constructive feedback on a GP trainee's consultation.

# Your Role
Analyze the consultation transcript and provide balanced, specific feedback that will help the trainee improve.
Use the case-specific marking criteria provided in the input to assess the trainee's performance accurately.

# Assessment Domains

## 1. Data Gathering (History Taking)
- Systematic questioning
- Identification of presenting complaint
- Exploration of red flag symptoms  
- Past medical history, medications, allergies
- Social and family history
- ICE (Ideas, Concerns, Expectations)
- **Use the case-specific Data Gathering criteria if provided**

## 2. Clinical Management
- Appropriate differential diagnosis
- Justified investigations
- Clear management plan
- Safety-netting advice
- Follow-up arrangements
- Appropriate referral decisions
- **Use the case-specific Clinical Management criteria if provided**

## 3. Interpersonal Skills
- Rapport building
- Active listening
- Empathy and reassurance
- Clear explanations
- Shared decision-making
- Professional manner
- **Use the case-specific Interpersonal Skills criteria if provided**

# Scoring Guidelines
- 80-100: Excellent - comprehensive, thorough, no significant omissions
- 60-79: Good - most key areas covered with minor gaps
- 40-59: Adequate - some important areas missed
- 20-39: Needs improvement - significant gaps
- 0-19: Poor - major omissions, unsafe practice

# Important
- Score against the CASE-SPECIFIC marking criteria when provided — these define what the trainee should have done
- Be specific with feedback - reference what was actually said
- Balance criticism with recognition of what was done well
- Focus on actionable improvements
- Keep learning points practical and memorable
- Use the clinical learning points (if provided) to inform key takeaways

# Output Format
You MUST respond with a single JSON object matching the ConsultationFeedback schema with these exact fields:
- data_gathering: { domain, score, strengths, improvements }
- clinical_management: { domain, score, strengths, improvements }
- interpersonal_skills: { domain, score, strengths, improvements }
- overall_summary: string
- key_learning_points: array of strings
"""


async def generate_feedback(transcript: List[dict], case_brief: str) -> ConsultationFeedback:
    """
    Generate structured feedback from a consultation transcript.
    
    Uses Gemini via google-genai for single-shot structured output generation.
    
    Args:
        transcript: List of {role, content, timestamp} dicts
        case_brief: Summary of the case for context
    
    Returns:
        ConsultationFeedback with scores and learning points
    """
    # Return default feedback if no transcript
    if not transcript:
        return ConsultationFeedback(
            data_gathering=DomainScore(
                domain="Data Gathering",
                score=0,
                strengths=[],
                improvements=["No consultation data available to assess"]
            ),
            clinical_management=DomainScore(
                domain="Clinical Management",
                score=0,
                strengths=[],
                improvements=["No consultation data available to assess"]
            ),
            interpersonal_skills=DomainScore(
                domain="Interpersonal Skills",
                score=0,
                strengths=[],
                improvements=["No consultation data available to assess"]
            ),
            overall_summary="No consultation transcript was captured.",
            key_learning_points=["Ensure audio is working for next attempt"]
        )
    
    # Format transcript for analysis
    transcript_text = "\n".join([
        f"[{t.get('timestamp', 'N/A')}] {t.get('role', 'Unknown').upper()}: {t.get('content', '')}" 
        for t in transcript
        if t.get('content')
    ])
    
    prompt = f"""
{FEEDBACK_PROMPT}

# Case Context
{case_brief}

# Consultation Transcript
{transcript_text}

Please analyze this consultation and provide structured feedback as JSON.
"""
    
    try:
        client = genai.Client()
        
        response = await client.aio.models.generate_content(
            model=settings.GEMINI_FEEDBACK_MODEL,
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ConsultationFeedback,
                temperature=0.3,
            ),
        )
        
        return ConsultationFeedback.model_validate_json(response.text)
        
    except Exception as e:
        logger.error(f"Feedback generation error: {e}")
        # Fall back to parsing response text if structured output fails
        try:
            # Try parsing as raw JSON
            if hasattr(e, '__context__') and hasattr(e.__context__, 'text'):
                return ConsultationFeedback.model_validate_json(e.__context__.text)
        except Exception:
            pass
        raise
