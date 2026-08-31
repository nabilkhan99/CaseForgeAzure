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

# ---------------------------------------------------------------------------
# Post-generation output cleanup (build spec section 8)
#
# Two narrow helpers applied to every string the Portfolio model writes back to
# the trainee. Both are deliberately conservative: this text is pasted straight
# into an RCGP ePortfolio, so a false positive that corrupts a real review is
# worse than a miss that a human still has to catch.
#
# Do NOT reach for app.utils.no_dashes.enforce_no_dashes here. It strips every
# intra-word hyphen, so "co-amoxiclav" becomes "co amoxiclav", which the
# Portfolio prompt explicitly calls a clinical error.
# ---------------------------------------------------------------------------

# Spec 8a: /(\d+)-(year|month|week|day)-old/gi -> "$1 $2 old".
# Anchored on both hyphens and on the literal word "old", so it can only fire on
# an age construction. Ordinary and clinical hyphens are structurally unreachable.
_AGE_HYPHEN_RE = re.compile(r"(\d+)-(year|month|week|day)-(old)", re.IGNORECASE)

# Spec 8b safeguard: a title followed by a capitalised word reads as a personal
# name. Detection only, never rewriting.
_NAME_TITLES = ("Dr", "Mr", "Mrs", "Ms", "Miss", "Prof", "Professor", "Sister", "Nurse")

_TITLE_NAME_RE = re.compile(
    r"\b(?:" + "|".join(_NAME_TITLES) + r")\.?\s+[A-Z][A-Za-z'’-]+"
)

# Capitalised words that follow a title as part of a role, not as a surname.
# Keeps the flag useful: a warning nobody trusts gets ignored.
_ROLE_WORDS_AFTER_TITLE = frozenset(
    {
        "Practitioner",
        "Practitioners",
        "Specialist",
        "Specialists",
        "Prescriber",
        "Consultant",
        "Manager",
        "Lead",
        "Led",
        "Team",
        "Practice",
        "Colleague",
        "Colleagues",
        "In",
        "On",
        "Of",
        "And",
    }
)


def strip_age_hyphens(text: str) -> str:
    """Rewrite hyphenated ages as spaced ages, per build spec section 8a.

    "a 42-year-old man" -> "a 42 year old man". Years, months, weeks and days,
    any casing. The casing of the matched words is preserved, so "6-Week-Old"
    becomes "6 Week Old" rather than being silently lower-cased.

    Nothing else is touched: "co-amoxiclav", "self-employed" and "follow-up"
    come back unchanged, because the pattern requires a leading numeral, an age
    word, and the trailing word "old".
    """
    if not isinstance(text, str):
        raise TypeError(f"strip_age_hyphens expects str, got {type(text).__name__}")
    return _AGE_HYPHEN_RE.sub(lambda m: f"{m.group(1)} {m.group(2)} {m.group(3)}", text)


def find_name_title_patterns(text: str) -> List[str]:
    """Return the "title + capitalised word" fragments that read as personal names.

    The build spec's recommended safeguard for section 8b: flag output such as
    "Dr O'Rourke" or "Sister Amara" for human review. Purely a detector. It
    never rewrites the text, because a false positive here would corrupt a real
    review, and role phrases ("Nurse Practitioner") are filtered out so the
    signal stays worth acting on.

    Returns the matched fragments in order of first appearance, de-duplicated.
    An empty list means nothing was flagged.
    """
    if not isinstance(text, str):
        raise TypeError(f"find_name_title_patterns expects str, got {type(text).__name__}")

    hits: List[str] = []
    seen = set()
    for match in _TITLE_NAME_RE.finditer(text):
        fragment = match.group(0)
        following = fragment.split()[-1]
        if following in _ROLE_WORDS_AFTER_TITLE:
            continue
        if fragment in seen:
            continue
        seen.add(fragment)
        hits.append(fragment)
    return hits
