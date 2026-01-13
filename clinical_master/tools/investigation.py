"""
Investigation Tool

Allows the patient agent to report investigation results
when the trainee requests tests or observations.
"""

from agents import function_tool


# Investigation results for Margaret Thompson case
INVESTIGATION_RESULTS = {
    "ecg": (
        "Sinus rhythm at 88 bpm. "
        "ST depression in leads V4, V5, and V6. "
        "T wave inversion in lead aVL. "
        "No acute ST elevation."
    ),
    "blood_pressure": "165/95 mmHg",
    "pulse": "88 beats per minute, regular",
    "oxygen_saturation": "97% on room air",
    "spo2": "97% on room air",
    "blood_glucose": "8.2 mmol/L (random)",
    "temperature": "36.8°C",
    "respiratory_rate": "16 breaths per minute",
    "peak_flow": "380 L/min (predicted 420 L/min for age and height)",
    "weight": "78 kg",
    "height": "165 cm",
    "bmi": "28.6 kg/m²",
}


@function_tool(
    name_override="get_investigation_result",
    description_override="Get the result of a bedside investigation or observation."
)
async def get_investigation_result(investigation: str) -> str:
    """
    The trainee requests an investigation result.
    Returns the result if available for this case.
    
    Args:
        investigation: Type of investigation (ECG, blood pressure, pulse, 
                      oxygen saturation, blood glucose, etc.)
    """
    inv_key = investigation.lower().strip().replace(" ", "_").replace("-", "_")
    
    # Direct match
    if inv_key in INVESTIGATION_RESULTS:
        return f"{investigation}: {INVESTIGATION_RESULTS[inv_key]}"
    
    # Check for common variations
    if any(word in inv_key for word in ["ecg", "electrocardiogram", "ekg"]):
        return f"ECG: {INVESTIGATION_RESULTS['ecg']}"
    
    if any(word in inv_key for word in ["bp", "blood_pressure", "pressure"]):
        return f"Blood pressure: {INVESTIGATION_RESULTS['blood_pressure']}"
    
    if any(word in inv_key for word in ["pulse", "heart_rate", "hr"]):
        return f"Pulse: {INVESTIGATION_RESULTS['pulse']}"
    
    if any(word in inv_key for word in ["oxygen", "sats", "spo2", "o2"]):
        return f"Oxygen saturation: {INVESTIGATION_RESULTS['oxygen_saturation']}"
    
    if any(word in inv_key for word in ["glucose", "sugar", "bm"]):
        return f"Blood glucose: {INVESTIGATION_RESULTS['blood_glucose']}"
    
    if any(word in inv_key for word in ["temp", "temperature"]):
        return f"Temperature: {INVESTIGATION_RESULTS['temperature']}"
    
    if any(word in inv_key for word in ["rr", "respiratory", "breathing"]):
        return f"Respiratory rate: {INVESTIGATION_RESULTS['respiratory_rate']}"
    
    # For blood tests that would need to be sent away
    if any(word in inv_key for word in ["troponin", "cardiac_enzymes", "blood_test", "fbc", "u&e"]):
        return f"{investigation}: This would need to be sent to the laboratory. Results would take 1-2 hours."
    
    # Default response
    return f"{investigation}: Result not available at bedside."
