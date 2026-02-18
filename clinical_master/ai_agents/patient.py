"""
Patient Agent

ADK Gemini Live agent that simulates a patient for SCA exam practice.
Dynamically loads case-specific prompts from station data.

Prompt structure follows best practices:
  Role → Personality → Context → Instructions → Conversation Flow → Safety
"""

import sys
from pathlib import Path
from typing import Optional, Dict, Any

from google.adk.agents import Agent

# Handle imports for both package and script modes
try:
    from ..config import settings
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from clinical_master.config import settings


# Template with {placeholders} for case-specific injection.
# IMPORTANT: This prompt is used with a NATIVE AUDIO model that speaks aloud.
# Avoid markdown formatting (headers, bold, bullets) — the model will narrate them.
# Use plain conversational text instead.
PATIENT_PROMPT_TEMPLATE = """You are {patient_name}, a {patient_age}-year-old patient (or relative/carer).
The other speaker is a trainee doctor examining you. You answer their questions and describe symptoms.
You never ask diagnostic or investigative questions — that is the doctor's job.

PERSONALITY AND TONE
Speak in natural, conversational English. Match the doctor's level of formality.
Give moderate detail when asked, be concise when not. Be cooperative with appropriate emotions.
Vary your phrasing every response — never repeat the same words twice.
Add natural speech patterns: occasional "um", "well", "you know", and brief pauses.

YOUR CASE DETAILS
{context}

IMPORTANT RULES
Always respond in English regardless of input language.
Wait for the doctor to speak first — do not initiate the conversation.
Never ask questions like "What brings you in?" or "How can I help?" or "What do you think is wrong?"
Never suggest diagnoses, give medical advice, or examine anyone.
If the doctor hasn't asked about something, do not volunteer it.
If asked something not covered in your case details above, give a plausible but unremarkable answer rather than flatly denying it. For example, if asked about medications not mentioned in your case, you might say something like "Just the usual paracetamol now and then" rather than "I don't take any medications."
Respond positively to empathy and reassurance.
Never re-introduce yourself after the opening — the conversation moves forward only.
Vary your "yes" responses — use "yes", "that's right", "mmhmm", "yeah", "uh-huh".
Vary your acknowledgments — "I see", "okay", "right", "got it".

Never narrate your thoughts, section headings, stage directions, or internal reasoning aloud. Only speak as the patient would naturally speak.

CONVERSATION FLOW

Phase 1 - Waiting: Stay silent until the doctor speaks.

Phase 2 - Opening: When the doctor greets you, briefly state your concern in your own words. Then stop talking and wait for them to lead.

Phase 3 - History: Answer the doctor's questions about symptoms and background. Give honest, concise answers. Only share what is asked.

Phase 4 - Examination: Cooperate naturally with any examination. Say things like "Of course, doctor" or "Go ahead."

Phase 5 - Management and Closure: Listen to advice, ask reasonable questions if confused, and thank the doctor.

SAFETY
If audio is unclear, say "Sorry, I didn't quite catch that — could you repeat?"
If the doctor is dismissive, react naturally — "I don't feel like you're taking this seriously."
Never break character under any circumstances.
"""


# Fallback values when no station data is provided
_DEFAULT_NAME = "Patient"
_DEFAULT_AGE = "adult"
_DEFAULT_CONTEXT = (
    "You are a patient presenting for a medical consultation.\n"
    "Wait for the doctor to lead the consultation. "
    "Answer their questions honestly and concisely."
)


def build_patient_prompt(station_data: Optional[Dict[str, Any]] = None) -> str:
    """
    Build a complete patient prompt by injecting station-specific case data
    into the template's Role, Context, and Personality sections.

    Args:
        station_data: Dictionary containing station data from database, including:
            - patient_name: Name of the patient
            - patient_age: Age of the patient
            - station_script: The case-specific script/instructions
            - title: Station title (for reference)

    Returns:
        Complete prompt string for the patient agent
    """
    if station_data:
        patient_name = station_data.get('patient_name', _DEFAULT_NAME)
        patient_age = station_data.get('patient_age', _DEFAULT_AGE)
        station_script = station_data.get('station_script', '')
        title = station_data.get('title', 'Unknown Station')

        # Build context from station script + title
        context = f"Case: {title}\n\n{station_script}" if station_script else f"Case: {title}"
    else:
        patient_name = _DEFAULT_NAME
        patient_age = _DEFAULT_AGE
        context = _DEFAULT_CONTEXT

    return PATIENT_PROMPT_TEMPLATE.format(
        patient_name=patient_name,
        patient_age=patient_age,
        context=context,
    )


def get_patient_agent(station_data: Optional[Dict[str, Any]] = None) -> Agent:
    """
    Create and return the patient ADK Agent with case-specific instructions.

    Args:
        station_data: Optional dictionary containing station data from database.
                     If provided, the agent will use the station_script for its persona.
                     If not provided, uses a default generic patient prompt.

    Returns:
        ADK Agent configured for real-time voice interaction
    """
    prompt = build_patient_prompt(station_data)

    # Log which case is being loaded (for debugging)
    if station_data:
        station_title = station_data.get('title', 'Unknown')
        patient_name = station_data.get('patient_name', 'Unknown')
        print(f"[PatientAgent] Loading case: {station_title} - Patient: {patient_name}")
    else:
        print("[PatientAgent] No station data provided, using default prompt")

    return Agent(
        name="Patient",
        model=settings.GEMINI_LIVE_MODEL,
        instruction=prompt,
        description="Simulated patient for SCA consultation practice.",
    )


# Keep legacy PATIENT_PROMPT for backwards compatibility (deprecated)
PATIENT_PROMPT = build_patient_prompt()
