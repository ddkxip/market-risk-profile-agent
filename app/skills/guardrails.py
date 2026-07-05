"""Guardrail skills — ADK callbacks that enforce the validators at runtime.

Attach these to any ADK LlmAgent via its callback hooks:

    from app.skills.guardrails import (
        ground_tool_output, append_disclaimer_and_flag_numbers, block_advice_requests,
    )

    agent = Agent(
        name="...",
        model="gemini-2.5-flash",
        tools=[...],
        after_tool_callback=ground_tool_output,
        after_model_callback=append_disclaimer_and_flag_numbers,
        before_model_callback=block_advice_requests,
    )

Signatures match google-adk 2.3.0:
- after_tool_callback(tool, args, tool_context, tool_response) -> Optional[dict]
- after_model_callback(callback_context, llm_response) -> Optional[LlmResponse]
- before_model_callback(callback_context, llm_request) -> Optional[LlmResponse]
Returning a value REPLACES the output; returning None leaves it unchanged.
"""

from __future__ import annotations

import json
import math

DISCLAIMER = (
    "\n\n---\n*AlphaInsight is an educational demo of agentic AI, not financial "
    "advice. Some figures are model-generated and may be inaccurate. Do not use "
    "this to make investment decisions.*"
)

# Phrases that indicate the user is asking for a personal recommendation.
_ADVICE_TRIGGERS = (
    "should i buy", "should i sell", "should i invest", "is it a good buy",
    "will i make money", "guaranteed", "how much should i put",
)


def _finite(x) -> bool:
    return isinstance(x, (int, float)) and not (math.isnan(x) or math.isinf(x))


def ground_tool_output(tool, args, tool_context, tool_response):
    """after_tool_callback: reject obviously broken numeric tool outputs.

    Our data tools return a JSON string. If that payload contains a NaN/inf or a
    negative price, we replace the response with a clean error dict so the model
    never synthesises analysis on top of corrupt numbers.
    """
    try:
        payload = tool_response
        if isinstance(tool_response, dict) and "result" in tool_response:
            payload = tool_response["result"]
        data = json.loads(payload) if isinstance(payload, str) else payload
    except (ValueError, TypeError):
        return None  # not JSON we understand; leave untouched

    if isinstance(data, dict):
        # any explicit error from the tool passes through unchanged
        if data.get("error"):
            return None
        for key in ("current_price", "score", "rsi_14", "price"):
            if key in data and not _finite(data[key]):
                return {"error": f"{tool.name} returned invalid '{key}': {data[key]!r}"}
        if _finite(data.get("current_price")) and data["current_price"] <= 0:
            return {"error": f"{tool.name} returned non-positive price"}
    return None


def append_disclaimer_and_flag_numbers(callback_context, llm_response):
    """after_model_callback: append the not-advice disclaimer to the final text.

    Optionally, if the caller stashed grounded values in
    callback_context.state['grounded_numbers'], flag prose figures that don't
    match any of them. Heuristic only — see validators.ungrounded_numbers.
    """
    if not (llm_response and llm_response.content and llm_response.content.parts):
        return None

    part = llm_response.content.parts[0]
    text = getattr(part, "text", None)
    if not text:
        return None

    addition = DISCLAIMER

    try:
        grounded = (callback_context.state or {}).get("grounded_numbers")
    except Exception:
        grounded = None
    if grounded:
        from app.skills.validators import ungrounded_numbers
        flagged = ungrounded_numbers(text, grounded)
        if flagged:
            preview = ", ".join(str(n) for n in flagged[:5])
            addition = (
                f"\n\n> ⚠️ Unverified figures detected in this summary "
                f"({preview}). Cross-check against the source data."
            ) + addition

    part.text = text + addition
    return llm_response


def block_advice_requests(callback_context, llm_request):
    """before_model_callback: short-circuit direct 'should I buy?' questions.

    Returns a canned safe response WITHOUT calling the model when the user asks
    for a personal recommendation. Returning None lets normal analysis proceed.
    """
    try:
        parts = llm_request.contents[-1].parts if llm_request.contents else []
        user_text = " ".join(getattr(p, "text", "") or "" for p in parts).lower()
    except Exception:
        return None

    if any(trigger in user_text for trigger in _ADVICE_TRIGGERS):
        from google.adk.models import LlmResponse
        from google.genai import types
        msg = (
            "I can't give personal buy/sell advice. I can walk you through the "
            "grounded evidence — technicals, SEC risk factors, sentiment, macro, "
            "and the projection — so you can weigh it yourself." + DISCLAIMER
        )
        return LlmResponse(
            content=types.Content(role="model", parts=[types.Part(text=msg)])
        )
    return None
