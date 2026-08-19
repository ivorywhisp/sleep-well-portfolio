"""Sage — the in-app AI helper (the brief's optional LLM feature).

Grounded on the user's actual profile and recommendation so answers are
about THEIR result, not generic finance chat. The API key lives in
Streamlit secrets (never in the repo, per the brief); without a key the
app simply hides the chat, so forks and graders without credentials
lose nothing.
"""

# fast non-reasoning model first: reasoning models can spend the whole
# completion budget thinking and return empty content in a chat widget
MODELS = ["gpt-4o-mini", "gpt-5-mini"]

SYSTEM = """You are Sage, the assistant inside Sage Invest, a university \
project robo-advisor. Answer questions about the user's assessment and \
portfolio using the context below.

Rules:
- Educational explanations only — never personalised financial advice, \
never buy/sell instructions, never predictions.
- Be concise (under 120 words) and plain-spoken; gloss any jargon.
- Be honest about the app's limitations (historical data only, no costs \
or taxes, the future can differ from the past).
- If asked something unrelated to investing or this app, decline politely.

User context:
{context}"""


def reply(api_key: str, context: str, history: list[dict]) -> str:
    """One assistant turn. `history` is [{role, content}, ...] ending with
    the user's newest message."""
    # deferred import: a keyless deployment never needs the openai package
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    messages = ([{"role": "system",
                  "content": SYSTEM.format(context=context)}] + history)
    last_err: Exception | None = None
    for model in MODELS:
        try:
            out = client.chat.completions.create(
                model=model, messages=messages, max_completion_tokens=700)
            content = out.choices[0].message.content
            if content:  # empty = reasoning ate the budget -> try next
                return content
        except Exception as err:  # model not enabled for this key -> next
            last_err = err
    if last_err:
        raise last_err
    raise RuntimeError("no model returned content")
