import json

from openai import OpenAI

from app.config import OPENAI_API_KEY

_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if not OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Copy .env.example to .env and add your key."
        )
    if _client is None:
        _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client


def call_tool(*, model: str, system: str, user_content: str, tool: dict, max_tokens: int = 1500) -> dict:
    """Force the model to respond via a single named tool/function call and
    return its parsed arguments dict. Using function-calling (rather than
    asking for free-text JSON and regexing it out) is what makes both the
    compiler and the recovery agent produce reliably structured output
    instead of prose we have to guess-parse.

    `tool` uses a provider-agnostic {name, description, input_schema} shape
    so compiler.py/recovery.py never touch a specific vendor's SDK; this
    function is the only place that speaks OpenAI's function-calling wire
    format, so swapping providers later means changing only this file.
    """
    client = get_client()
    response = client.chat.completions.create(
        model=model,
        max_completion_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
        tools=[
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["input_schema"],
                },
            }
        ],
        tool_choice={"type": "function", "function": {"name": tool["name"]}},
    )
    message = response.choices[0].message
    if not message.tool_calls:
        raise RuntimeError(f"Model did not call the expected tool '{tool['name']}'")
    call = message.tool_calls[0]
    if call.function.name != tool["name"]:
        raise RuntimeError(f"Model called unexpected tool '{call.function.name}'")
    return json.loads(call.function.arguments)
