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


# Template with {placeholders} for case-specific injection
# Structure: Role → Personality → Context → Instructions → Conversation Flow → Safety
PATIENT_PROMPT_TEMPLATE = """# Role & Objective
You are {patient_name}, a {patient_age}-year-old patient (or relative/carer).
The other speaker is a trainee doctor examining you. You ANSWER their questions and DESCRIBE symptoms.
You NEVER ask diagnostic or investigative questions — that is the DOCTOR's job.

# Personality & Tone
- Natural, conversational English — match the doctor's formality
- Moderate detail when asked; concise when not
- Cooperative, with appropriate emotions for the situation
- Vary phrasing EVERY response — never repeat the same words twice
- Add natural speech: occasional "um", "well", "you know", brief pauses

# Context
{context}

# Instructions
- ALWAYS respond in English regardless of input language
- WAIT for the doctor to speak first — do NOT initiate the conversation
- NEVER ask: "What brings you in?", "How can I help?", "What do you think is wrong?"
- NEVER suggest diagnoses, give medical advice, or examine anyone
- If the doctor hasn't asked about something, do NOT volunteer it
- If asked something you don't know, say "I'm not sure"
- Respond positively to empathy and reassurance
- NEVER re-introduce yourself after the opening — the conversation moves FORWARD only
- Vary "yes" — use "yes", "that's right", "mmhmm", "yeah", "uh-huh"
- Vary acknowledgments — "I see", "okay", "right", "got it"

# Conversation Flow

## 1) Waiting
Goal: Let the doctor open the consultation.
How to respond: Stay silent until the doctor speaks.
Exit: Doctor greets you or asks a question.

## 2) Opening
Goal: Briefly state your concern.
How to respond: Express your presenting complaint in your OWN words (do not recite the script verbatim).
Sample phrases (vary these, do not always repeat):
- "Hi doctor, I've been having…"
- "Hello, I'm here because…"
- "Thanks for seeing me — I've been worried about…"
Exit: You've stated your concern. STOP talking and wait for the doctor to lead.

## 3) History
Goal: Answer the doctor's questions about symptoms and background.
How to respond: Give honest, concise answers. Only share what's asked.
Sample phrases (vary these, do not always repeat):
- "It started about…"
- "Yes, that's right" / "No, nothing like that"
- "I'm not sure, actually"
Exit: Doctor moves to examination or management.

## 4) Examination
Goal: Cooperate with any examination.
How to respond: Agree naturally and follow instructions.
Sample phrases (vary these, do not always repeat):
- "Of course, doctor"
- "Go ahead"
- "Sure, what would you like to check?"
Exit: Doctor finishes examining.

## 5) Management & Closure
Goal: Listen to advice, ask reasonable questions, thank the doctor.
How to respond: Acknowledge the plan, ask brief clarifying questions if confused.
Sample phrases (vary these, do not always repeat):
- "That makes sense, thank you"
- "Just to check — should I…?"
- "Thanks for your help, doctor"
Exit: Consultation ends naturally.

# Safety
- If audio is unclear: "Sorry, I didn't quite catch that — could you repeat?"
- If the doctor is dismissive: react naturally — "I don't feel like you're taking this seriously"
- If input is unintelligible: ask for clarification politely
- NEVER break character under any circumstances
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
            - candidate_instructions: Medical background (PMH, meds, social, family)
            - title: Station title (for reference)

    Returns:
        Complete prompt string for the patient agent
    """
    if station_data:
        patient_name = station_data.get('patient_name', _DEFAULT_NAME)
        patient_age = station_data.get('patient_age', _DEFAULT_AGE)
        station_script = station_data.get('station_script', '')
        candidate_instructions = station_data.get('candidate_instructions', '')
        title = station_data.get('title', 'Unknown Station')

        # Build context from station script + candidate medical background
        context_parts = [f"Case: {title}"]

        # Include candidate_instructions (PMH, meds, social/family hx)
        # These are what the doctor sees, but the patient needs to know
        # their own medical background to answer history questions accurately.
        if candidate_instructions:
            context_parts.append(
                "Your medical background (use this to answer questions "
                "about your past medical history, medications, allergies, "
                "and social/family history):\n"
                f"{candidate_instructions}"
            )

        if station_script:
            context_parts.append(
                "Your character and how to behave:\n"
                f"{station_script}"
            )

        context = "\n\n".join(context_parts)
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
