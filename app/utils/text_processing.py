# app/utils/text_processing.py
import re
from typing import Dict, List, Optional
from openai import AzureOpenAI
from openai import AsyncAzureOpenAI
from ..config import Settings

def extract_sections(review_content: str, selected_capabilities: List[str]) -> Dict[str, any]:
    """Extract sections from review content."""
    print(f"🟡 extract_sections: Starting extraction, content length: {len(review_content)} chars")
    
    sections = {
        "brief_description": "",
        "capabilities": {},
        "reflection": "",
        "learning_needs": ""
    }
    
    # Split content into sections
    content_parts = review_content.split('\n\n')
    print(f"🟡 extract_sections: Split into {len(content_parts)} parts")
    current_section = None
    
    for idx, part in enumerate(content_parts):
        part = part.strip()
        if not part:
            continue
            
        if part.lower().startswith('brief description:'):
            current_section = "brief_description"
            # Handle both "Brief Description:" and "Brief description:"
            content = part
            for prefix in ['Brief Description:', 'Brief description:', 'BRIEF DESCRIPTION:']:
                if content.startswith(prefix):
                    content = content.replace(prefix, '', 1).strip()
                    break
            sections["brief_description"] = content
        
        elif part.lower().startswith('capability:'):
            current_section = "capabilities"
            # Extract capability name and justification
            cap_lines = part.split('\n')
            # Handle "Capability:" with different cases
            cap_name = cap_lines[0]
            for prefix in ['Capability:', 'capability:', 'CAPABILITY:']:
                if cap_name.startswith(prefix):
                    cap_name = cap_name.replace(prefix, '', 1).strip()
                    break
            
            if len(cap_lines) > 1:
                justification = '\n'.join(cap_lines[1:])
                # Remove "Justification:" label if present
                for prefix in ['Justification:', 'justification:', 'JUSTIFICATION:']:
                    if justification.strip().startswith(prefix):
                        justification = justification.strip().replace(prefix, '', 1).strip()
                        break
                sections["capabilities"][cap_name] = justification.strip()
        
        elif part.lower().startswith('reflection:'):
            current_section = "reflection"
            content = part
            for prefix in ['Reflection:', 'reflection:', 'REFLECTION:']:
                if content.startswith(prefix):
                    content = content.replace(prefix, '', 1).strip()
                    break
            sections["reflection"] = content
        
        elif part.lower().startswith('learning needs'):
            current_section = "learning_needs"
            content = part
            # Handle various formats
            for prefix in ['Learning needs identified from this event:', 'Learning Needs Identified:', 
                          'Learning needs:', 'Learning Needs:', 'LEARNING NEEDS:']:
                if prefix.lower() in content.lower():
                    # Find the prefix case-insensitively and remove it
                    idx = content.lower().find(prefix.lower())
                    if idx != -1:
                        content = content[idx + len(prefix):].strip()
                        break
            sections["learning_needs"] = content
        
        elif current_section:
            # Append content to current section
            if current_section == "capabilities":
                continue  # Skip appending to capabilities
            sections[current_section] = sections[current_section] + '\n' + part
    
    print(f"🟡 extract_sections: Completed. Found {len(sections['capabilities'])} capabilities")
    print(f"🟡 extract_sections: Brief desc: {len(sections['brief_description'])} chars")
    print(f"🟡 extract_sections: Reflection: {len(sections['reflection'])} chars")
    print(f"🟡 extract_sections: Learning needs: {len(sections['learning_needs'])} chars")
    
    return sections

async def generate_title(case_description: str, client: AsyncAzureOpenAI, settings: Settings) -> str:
    """Generate a brief title from the case description."""
    try:
        print(f"🟢 generate_title: Starting, description length: {len(case_description)} chars")
        response = await client.chat.completions.create(
            model=settings.azure_openai_deployment,
            messages=[
                {"role": "system", "content": "Generate a brief (4-6 words) medical case title."},
                {"role": "user", "content": f"Create a title for: {case_description}"}
            ],
            max_tokens=50,
            temperature=0.7
        )
        
        title = response.choices[0].message.content.strip().replace('"', '')
        print(f"🟢 generate_title: Completed, title: '{title}'")
        return title
    except Exception as e:
        print(f"❌ generate_title: Error - {str(e)}, returning default")
        return "Case Review"