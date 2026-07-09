from app.config import OPENAI_MODEL
from app.llm.client import call_tool
from app.models import TestStep

RECOVERY_TOOL = {
    "name": "emit_recovery_action",
    "description": "Propose a concrete recovery action that fulfils the failed step's intent using only elements present in the given live DOM.",
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["click", "fill", "assert_text"],
            },
            "selector": {
                "type": "string",
                "description": "A CSS selector that must match an element actually present in the provided DOM.",
            },
            "value": {
                "type": ["string", "null"],
                "description": "For 'fill': text to type. For 'assert_text': the substring to check for. Null for 'click'.",
            },
            "reasoning": {
                "type": "string",
                "description": (
                    "Explain, for a non-technical reader, what changed in the UI and why "
                    "this selector/action still satisfies the original step's intent."
                ),
            },
        },
        "required": ["action", "selector", "reasoning"],
    },
}

SYSTEM_PROMPT = """You are the agentic recovery executor in a hybrid test-execution
system. A deterministic step just failed because its selector no longer matches
the live page -- the UI has drifted since the test was authored. You are given
the step's original intent and a snapshot of the current live DOM.

Find an element actually present in the given DOM that fulfils the same intent
and propose one recovery action. Do not invent a selector that isn't present
in the DOM you were given. Be conservative: prefer the most specific selector
that still matches, so this recovery makes sense if it's later promoted back
into the deterministic script.
"""


def recover_step(step: TestStep, live_dom_html: str) -> dict:
    user_content = f"""Original step intent: {step.expected}
Original action: {step.action}
Original selector (no longer valid): {step.selector}

Current live DOM snapshot:
{live_dom_html}
"""
    return call_tool(
        model=OPENAI_MODEL,
        system=SYSTEM_PROMPT,
        user_content=user_content,
        tool=RECOVERY_TOOL,
    )
