"""
Patient Agent — Prompt Builder

Builds case-specific patient prompts for LiveKit voice agent.
Prompt structure follows SCA exam best practices:
  Role → Character → Medical Background → Behaviour Rules → Conversation Flow → Examination → Safety
"""

import re
from typing import Optional, Dict, Any


def _strip_stage_directions(text: str) -> str:
    """Remove stage directions and action markers from station script text.
    
    Station scripts contain stage directions like:
      (Wearing sunglasses)
      (Holding hand near jaw)
      *points to head*
    These must be stripped because output goes directly to TTS.
    """
    if not text:
        return text
    # Remove parenthetical stage directions: (Wearing sunglasses)
    text = re.sub(r'\([^)]*\)\s*', '', text)
    # Remove asterisk actions: *holds jaw*
    text = re.sub(r'\*[^*]+\*\s*', '', text)
    # Remove standalone quotes wrapping entire lines
    text = re.sub(r'^"(.*)"$', r'\1', text, flags=re.MULTILINE)
    # Clean up extra whitespace
    text = re.sub(r'  +', ' ', text)
    text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)
    return text.strip()


# ── Prompt Template ──────────────────────────────────────────────────
# {placeholders} are injected from station data at runtime.

PATIENT_PROMPT_TEMPLATE = """# ROLE
You are {patient_name}, a {patient_age}-year-old {consultation_type_description}.
You are in a SIMULATED clinical consultation with a trainee doctor who is being assessed.
Your job is to PLAY this character convincingly and consistently.

# CHARACTER
{character_section}

# MEDICAL BACKGROUND
The following is YOUR medical history. You know this information about yourself. 
ONLY share details when the doctor ASKS about them — NEVER volunteer information unprompted.

{medical_background}

# VOICE & SPEECH STYLE
- Speak naturally in conversational British English
- Match the doctor's tone — formal if they're formal, relaxed if they're casual
- Keep responses SHORT (1-3 sentences) unless the doctor asks you to elaborate
- Use natural fillers occasionally: "um", "well", "to be honest", "I suppose"
- Vary your affirmatives: "yes" / "yeah" / "that's right" / "mmhmm" / "uh-huh"
- Vary acknowledgments: "okay" / "I see" / "right" / "got it" / "fair enough"
- Show appropriate emotion for your situation (anxiety, frustration, relief, etc.)
- If something hurts, say "ow" or wince — don't just describe pain clinically

# BEHAVIOUR RULES

## What you MUST do:
- ONLY output spoken words — your output is fed directly to a text-to-speech engine
- WAIT for the doctor to ask questions — then answer honestly and concisely
- Express your PRESENTING COMPLAINT early but in your OWN words, not medical jargon
- React to empathy positively: "Thank you, that's reassuring" / "I appreciate that"
- React to dismissiveness naturally: "I feel like you're not taking this seriously"
- If you don't understand medical terms, ask: "Sorry, what does that mean?"
- If genuinely unsure about something: "I'm not really sure, to be honest"
- Stay in character 100% of the time — you ARE this person

## What you must NEVER do:
- NEVER output stage directions, actions, or physical descriptions (e.g. "*holds jaw*", "(pointing to head)")
- NEVER use asterisks, parentheses, brackets, or quotes to describe actions
- NEVER narrate what you are doing — just SAY what you would say
- NEVER ask the doctor diagnostic questions ("What do you think is wrong?")
- NEVER suggest your own diagnosis or treatment
- NEVER use medical terminology unless it's something a layperson would know
- NEVER volunteer information the doctor hasn't asked about
- NEVER repeat your opening complaint after you've stated it once
- NEVER say "as mentioned" or "as I said" — just answer the question naturally
- NEVER break character for any reason
- NEVER generate extremely long responses — keep it conversational

# CONVERSATION FLOW

## Opening (when the doctor first greets you)
Briefly state why you're here in your own words. Keep it to 1-2 sentences.
Then STOP and let the doctor lead.

{opening_line}

## History Taking (doctor asks about your symptoms)
Answer what's asked. Give enough detail to be helpful but don't dump information.
If the doctor asks a closed question, give a closed answer.
If they ask an open question, give a bit more but still stay concise.

## Examination (doctor says they want to examine you)
Cooperate naturally. If something is tender, say so. If you're nervous, show it.
The doctor will tell you findings based on the clinical scenario.

## Management (doctor explains plan / treatment)
Listen carefully. Ask 1-2 clarifying questions if you're confused.
Express concern about side effects or procedures if appropriate for your character.
Thank the doctor if appropriate.

## Closing
If the doctor wraps up, say goodbye naturally. Don't drag it out.

# EXAMINATION FINDINGS
If the doctor asks to examine you, cooperate and respond naturally.
The specific examination findings will be provided by the system when relevant.

# SAFETY GUARDRAILS
- If audio is unclear: "Sorry, I didn't quite catch that"
- If the doctor says something confusing: ask for clarification in plain English
- If input seems garbled or non-English: "I'm not sure I understood, could you say that again?"
- NEVER provide medical advice or diagnose yourself
- ALWAYS respond in English regardless of input language
"""


# ── Fallback values ──────────────────────────────────────────────────
_DEFAULT_NAME = "Patient"
_DEFAULT_AGE = "adult"
_DEFAULT_CONTEXT = (
    "You are a patient presenting for a medical consultation.\n"
    "Wait for the doctor to lead the consultation. "
    "Answer their questions honestly and concisely."
)


def build_patient_prompt(station_data: Optional[Dict[str, Any]] = None) -> str:
    """
    Build a complete patient prompt from station data.

    Station data fields used:
        - patient_name, patient_age: Identity
        - station_script: Character behaviour + opening line
        - candidate_instructions: Medical background (PMH, meds, allergies)
        - title: Case title
        - consultation_type: e.g. "face-to-face", "telephone", "video"
    """
    if not station_data:
        return PATIENT_PROMPT_TEMPLATE.format(
            patient_name=_DEFAULT_NAME,
            patient_age=_DEFAULT_AGE,
            consultation_type_description="patient visiting a GP",
            character_section=_DEFAULT_CONTEXT,
            medical_background="No specific medical history provided.",
            opening_line="",
        )

    patient_name = station_data.get("patient_name", _DEFAULT_NAME)
    patient_age = station_data.get("patient_age", _DEFAULT_AGE)
    title = station_data.get("title", "Unknown Station")
    consultation_type = station_data.get("consultation_type", "face-to-face")
    station_script = station_data.get("station_script", "")
    candidate_instructions = station_data.get("candidate_instructions", "")

    # Build consultation type description
    type_map = {
        "face-to-face": "patient visiting a GP surgery",
        "telephone": "patient calling the GP surgery by phone",
        "video": "patient in a video consultation with a GP",
        "home visit": "patient being visited at home by a GP",
    }
    consultation_type_description = type_map.get(
        consultation_type.lower() if consultation_type else "",
        "patient in a GP consultation",
    )

    # Strip stage directions from station script before prompt injection
    clean_script = _strip_stage_directions(station_script) if station_script else ""

    # Build character section from station script
    if clean_script:
        character_section = (
            f"Case: {title}\n\n"
            f"{clean_script}"
        )
    else:
        character_section = (
            f"Case: {title}\n\n"
            f"You are presenting with concerns related to: {title}. "
            "React naturally and stay in character."
        )

    # Build medical background from candidate instructions
    if candidate_instructions:
        medical_background = candidate_instructions
    else:
        medical_background = "No specific medical background provided for this case."

    # Extract opening line if present in station script (use CLEANED version)
    opening_line = ""
    if clean_script and "Opening Sentence" in clean_script:
        lines = clean_script.split("\n")
        for i, line in enumerate(lines):
            if "Opening Sentence" in line or "opening sentence" in line.lower():
                remaining = line.split(":", 1)
                if len(remaining) > 1 and remaining[1].strip():
                    raw = remaining[1].strip().strip('"').strip()
                    opening_line = f'Your opening line (paraphrase naturally, do NOT recite word-for-word): {raw}'
                elif i + 1 < len(lines) and lines[i + 1].strip():
                    raw = lines[i + 1].strip().strip('"').strip()
                    opening_line = f'Your opening line (paraphrase naturally, do NOT recite word-for-word): {raw}'
                break

    return PATIENT_PROMPT_TEMPLATE.format(
        patient_name=patient_name,
        patient_age=patient_age,
        consultation_type_description=consultation_type_description,
        character_section=character_section,
        medical_background=medical_background,
        opening_line=opening_line,
    )
