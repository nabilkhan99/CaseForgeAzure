from app.services.portfolio_prompts import (
    PORTFOLIO_OUTPUT_CONTRACT,
    build_playground_system_prompt,
)


def test_playground_prompt_appends_render_contract():
    prompt = "You are a medic reviewing a case."
    combined = build_playground_system_prompt(prompt)

    assert combined.startswith(prompt)
    assert "Brief Description:" in combined
    assert "Capability: <selected capability name>" in combined
    assert "Learning needs identified from this event:" in combined
    assert PORTFOLIO_OUTPUT_CONTRACT.strip() in combined
