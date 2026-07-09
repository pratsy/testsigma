from app.config import OPENAI_MODEL
from app.llm.client import call_tool
from app.models import TestCase, TestStep
from app.target_app.reference_dom import APP_MANIFEST

COMPILER_TOOL = {
    "name": "emit_test_case",
    "description": "Emit a structured, executable test case for the described intent.",
    "input_schema": {
        "type": "object",
        "properties": {
            "steps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["goto", "fill", "click", "assert_text"],
                        },
                        "selector": {
                            "type": ["string", "null"],
                            "description": "CSS selector the action applies to. Null for 'goto'.",
                        },
                        "value": {
                            "type": ["string", "null"],
                            "description": (
                                "For 'goto': the URL path. For 'fill': the text to type. "
                                "For 'assert_text': the substring expected inside the "
                                "selector's text content. Null for 'click'."
                            ),
                        },
                        "expected": {
                            "type": "string",
                            "description": (
                                "Plain-English statement of what this step is trying to "
                                "accomplish and what success looks like, independent of the "
                                "selector. Used for both the human-readable run report and "
                                "as the fallback spec if the selector stops working."
                            ),
                        },
                    },
                    "required": ["action", "expected"],
                },
            }
        },
        "required": ["steps"],
    },
}

SYSTEM_PROMPT = f"""You are a test-authoring compiler for a browser automation system.
You are given a plain-English test intent and a manifest describing the pages
and known selectors of the application under test (captured from the current
build). Convert the intent into an ordered sequence of concrete steps using
only the documented selectors.

Application manifest:
{APP_MANIFEST}

Rules:
- Always start with a 'goto' step to /target/login.
- Use 'fill' for the username and password fields, then 'click' the login button.
- After login the app redirects to /target/orders automatically.
- End with an 'assert_text' step against the order summary element, checking
  for text that confirms the last order is visible.
- Every step must have a clear 'expected' description written for a
  non-technical reader (e.g. a release manager), independent of the selector.
"""


def compile_intent(intent: str) -> TestCase:
    result = call_tool(
        model=OPENAI_MODEL,
        system=SYSTEM_PROMPT,
        user_content=f"Intent: {intent}",
        tool=COMPILER_TOOL,
    )
    steps = [
        TestStep(
            order=i,
            action=raw["action"],
            selector=raw.get("selector"),
            value=raw.get("value"),
            expected=raw["expected"],
        )
        for i, raw in enumerate(result["steps"])
    ]
    return TestCase(intent=intent, steps=steps)
