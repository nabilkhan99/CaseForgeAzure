"""
Feedback Agent

Text-based agent that analyzes consultation transcripts
and generates structured feedback aligned with SCA marking domains.
"""

from typing import List
from pydantic import BaseModel, Field

from agents import Agent, Runner


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

# Assessment Domains

## 1. Data Gathering (History Taking)
- Systematic questioning
- Identification of presenting complaint
- Exploration of red flag symptoms  
- Past medical history, medications, allergies
- Social and family history
- ICE (Ideas, Concerns, Expectations)

## 2. Clinical Management
- Appropriate differential diagnosis
- Justified investigations
- Clear management plan
- Safety-netting advice
- Follow-up arrangements
- Appropriate referral decisions

## 3. Interpersonal Skills
- Rapport building
- Active listening
- Empathy and reassurance
- Clear explanations
- Shared decision-making
- Professional manner

# For This Case (Margaret Thompson, 58, Chest Pain)

**Key History Points to Cover:**
- Duration and character of chest pain
- Exacerbating and relieving factors
- Radiation to arm/jaw/back
- Associated symptoms (breathlessness, nausea, sweating)
- Cardiac risk factors (smoking, diabetes, hypertension, family history)

**Red Flags That Should Be Identified:**
- Pain at rest / waking from sleep
- Breathlessness at rest
- Ankle swelling
- Nausea with pain

**Expected Management:**
- Recognition of possible ACS/unstable angina
- Urgent referral or A&E recommendation
- ECG interpretation if done
- Aspirin consideration
- Clear safety-net advice

# Scoring Guidelines
- 80-100: Excellent - comprehensive, thorough, no significant omissions
- 60-79: Good - most key areas covered with minor gaps
- 40-59: Adequate - some important areas missed
- 20-39: Needs improvement - significant gaps
- 0-19: Poor - major omissions, unsafe practice

# Important
- Be specific with feedback - reference what was actually said
- Balance criticism with recognition of what was done well
- Focus on actionable improvements
- Keep learning points practical and memorable
"""


feedback_agent = Agent(
    name="Feedback Examiner",
    instructions=FEEDBACK_PROMPT,
    output_type=ConsultationFeedback,
    model="gpt-4.1",  # Use text model, not realtime
)


async def generate_feedback(transcript: List[dict], case_brief: str) -> ConsultationFeedback:
    """
    Generate structured feedback from a consultation transcript.
    
    Args:
        transcript: List of {role, content, timestamp} dicts
        case_brief: Summary of the case for context
    
    Returns:
        ConsultationFeedback with scores and learning points
    """
    # Format transcript for analysis
    if not transcript:
        # Return default feedback if no transcript
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
    
    transcript_text = "\n".join([
        f"[{t.get('timestamp', 'N/A')}] {t.get('role', 'Unknown').upper()}: {t.get('content', '')}" 
        for t in transcript
        if t.get('content')
    ])
    
    prompt = f"""
# Case Context
{case_brief}

# Consultation Transcript
{transcript_text}

Please analyze this consultation and provide structured feedback.
"""
    
    result = await Runner.run(feedback_agent, input=prompt)
    return result.final_output
