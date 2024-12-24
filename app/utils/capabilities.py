# app/utils/capabilities.py
from typing import Dict, List

def parse_capabilities(content: str) -> Dict[str, List[str]]:
    """Parse capabilities from configuration content."""
    capabilities = {}
    current_capability = None
    current_points = []
    
    lines = [line.rstrip() for line in content.split('\n') if line.strip()]
    
    for line in lines:
        if not line.startswith('-'):
            if current_capability and current_points:
                capabilities[current_capability] = current_points
            current_capability = line
            current_points = []
        else:
            current_points.append(line.lstrip('- '))
    
    if current_capability and current_points:
        capabilities[current_capability] = current_points
    
    return capabilities

def format_capabilities(selected_capabilities: List[str]) -> str:
    """Format selected capabilities into text format."""
    formatted_text = ""
    for cap in selected_capabilities:
        formatted_text += f"Capability: {cap}\n"
        formatted_text += "Justification [describe how your actions and approach link to the capability]:\n\n"
    return formatted_text