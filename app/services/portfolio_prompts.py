"""Prompt helpers for the Portfolio tool.

The live Portfolio prompt remains in Settings.SYSTEM_PROMPT. The playground
lets a reviewer replace that prompt for one request, but the UI still needs a
stable section structure to parse and render the result.
"""

PORTFOLIO_OUTPUT_CONTRACT = """
OUTPUT CONTRACT FOR THE FOURTEEN FISHERMAN PORTFOLIO UI

Return the review using exactly these section headings:

Brief Description:
Write the case summary.

Capability: <selected capability name>
Justification: Write the justification for this selected capability.

Repeat the Capability and Justification pair for each selected capability.

Reflection:
Write the reflection.

Learning needs identified from this event:
Write the learning needs.

Do not use Markdown headings, bullet points, asterisks, or tables.
"""


def build_playground_system_prompt(prompt: str) -> str:
    """Append the locked render contract to a playground prompt."""
    return f"{prompt.strip()}\n\n---\n\n{PORTFOLIO_OUTPUT_CONTRACT.strip()}"
