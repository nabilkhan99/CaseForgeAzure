# app/utils/text_processing.py
import re
from typing import Dict, List, Optional
from openai import AzureOpenAI
from ..config import Settings

def extract_sections(review_content: str, selected_capabilities: List[str]) -> Dict[str, any]:
    """Extract sections from review content."""
    sections = {
        "brief_description": "",
        "capabilities": {},
        "reflection": "",
        "learning_needs": ""
    }
    
    # Split content into sections
    content_parts = review_content.split('\n\n')
    current_section = None
    
    for part in content_parts:
        part = part.strip()
        if not part:
            continue
            
        if part.lower().startswith('brief description:'):
            current_section = "brief_description"
            sections["brief_description"] = part.replace('Brief Description:', '').strip()
        
        elif part.lower().startswith('capability:'):
            current_section = "capabilities"
            # Extract capability name and justification
            cap_lines = part.split('\n')
            cap_name = cap_lines[0].replace('Capability:', '').strip()
            if len(cap_lines) > 1:
                justification = '\n'.join(cap_lines[1:]).replace('Justification:', '').strip()
                sections["capabilities"][cap_name] = justification
        
        elif part.lower().startswith('reflection:'):
            current_section = "reflection"
            sections["reflection"] = part.replace('Reflection:', '').strip()
        
        elif part.lower().startswith('learning needs'):
            current_section = "learning_needs"
            sections["learning_needs"] = part.replace('Learning needs identified from this event:', '').strip()
        
        elif current_section:
            # Append content to current section
            if current_section == "capabilities":
                continue  # Skip appending to capabilities
            sections[current_section] = sections[current_section] + '\n' + part
    
    return sections

async def generate_title(case_description: str, client: AzureOpenAI, settings: Settings) -> str:
    """Generate a brief title from the case description."""
    try:
        response = client.chat.completions.create(
            model=settings.azure_openai_deployment,
            messages=[
                {"role": "system", "content": "Generate a brief (4-6 words) medical case title."},
                {"role": "user", "content": f"Create a title for: {case_description}"}
            ],
            max_tokens=50,
            temperature=0.7
        )
        
        return response.choices[0].message.content.strip().replace('"', '')
    except Exception:
        return "Case Review"