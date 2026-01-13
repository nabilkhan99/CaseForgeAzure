"""
Examination Tool

Allows the patient agent to report physical examination findings
when the trainee requests to examine the patient.
"""

from agents import function_tool


# Examination findings for Margaret Thompson case
EXAMINATION_FINDINGS = {
    "cardiovascular": (
        "Blood pressure is 165/95 mmHg. "
        "Heart rate is 88 beats per minute and regular. "
        "Heart sounds are normal with no murmurs. "
        "There is mild bilateral ankle oedema."
    ),
    "respiratory": (
        "Respiratory rate is 16 breaths per minute. "
        "Chest expansion is equal. "
        "Breath sounds are clear throughout. "
        "No wheeze or crackles heard."
    ),
    "abdominal": (
        "Abdomen is soft and non-tender. "
        "No organomegaly detected. "
        "Bowel sounds are normal."
    ),
    "peripheral": (
        "Mild pitting oedema to mid-shin bilaterally. "
        "Peripheral pulses are present and equal. "
        "No calf tenderness."
    ),
    "general": (
        "The patient appears comfortable at rest but slightly anxious. "
        "Skin colour is normal. "
        "No cyanosis or pallor."
    ),
}


@function_tool(
    name_override="request_examination",
    description_override="Request to examine the patient. Returns the examination findings."
)
async def request_examination(examination_type: str) -> str:
    """
    The trainee requests to examine the patient.
    Returns the physical examination findings for the specified system.
    
    Args:
        examination_type: Type of examination - cardiovascular, respiratory, 
                         abdominal, peripheral, or general
    """
    exam_key = examination_type.lower().strip()
    
    # Try to match partial words
    for key in EXAMINATION_FINDINGS:
        if key in exam_key or exam_key in key:
            finding = EXAMINATION_FINDINGS[key]
            return f"On {key} examination: {finding}"
    
    # Check for common variations
    if any(word in exam_key for word in ["heart", "chest", "bp", "pulse"]):
        finding = EXAMINATION_FINDINGS["cardiovascular"]
        return f"On cardiovascular examination: {finding}"
    
    if any(word in exam_key for word in ["lung", "breath"]):
        finding = EXAMINATION_FINDINGS["respiratory"]
        return f"On respiratory examination: {finding}"
    
    if any(word in exam_key for word in ["tummy", "stomach", "belly"]):
        finding = EXAMINATION_FINDINGS["abdominal"]
        return f"On abdominal examination: {finding}"
    
    if any(word in exam_key for word in ["leg", "ankle", "feet", "foot"]):
        finding = EXAMINATION_FINDINGS["peripheral"]
        return f"On peripheral examination: {finding}"
    
    # Default response
    return f"On {examination_type} examination: No abnormality detected."
