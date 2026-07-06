# AlphaInsight Skill Library

Reusable, framework-native agent skills that make AlphaInsight's outputs more
reliable. In an ADK/Gemini system, a "skill" is a packaged capability expressed
through ADK's real primitives — here, **deterministic validators** plus
**runtime guardrail callbacks** — not an Anthropic-style `SKILL.md` (which does
not execute in a Gemini runtime).

These skills map to two course themes at once: **Day 3 (Skills & Context
Engineering)** and **Day 4 (Quality & Security)**.

## Design principle: ground, then guard

We reduce hallucinated numbers with a two-layer defense. No layer *prevents* a
language model from emitting a number; together they **ground, constrain, and
flag** them.

1. **Grounding** — numbers originate from deterministic code, not the model.
   Technical indicators (RSI/MACD/SMA) are computed in pandas; validators confirm
   they are in-range before they reach any LLM synthesis step.
2. **Guarding** — ADK callbacks intercept tool and model outputs at runtime to
   validate, repair, or flag them before they reach the user.

## Skills

### 1. Validators (`app/skills/validators.py`) — deterministic, no LLM
- `validate_technicals` / `validate_sentiment` / `validate_forecast` — range and
  type checks (RSI in [0,100], sentiment in [-1,1], price > 0, dates well-formed,
  enums recognised). Return a list of human-readable issues.
- `clamp_forecast` — repairs an implausible LLM forecast by bounding each day's
  move to +/- 25% of the prior day, so a projected 80% spike becomes a bounded
  value instead of nonsense.
- `ungrounded_numbers` — heuristic: extracts money/percentage figures from prose
  and flags any that don't match a grounded value within tolerance. A review aid,
  not a guarantee.

### 2. Guardrails (`app/skills/guardrails.py`) — ADK callbacks
- `ground_tool_output` (`after_tool_callback`) — replaces a tool response with a
  clean error if it contains a NaN/inf or a non-positive price, so the model never
  synthesises on top of corrupt data.
- `append_disclaimer_and_flag_numbers` (`after_model_callback`) — appends the
  not-financial-advice disclaimer and, if grounded values are supplied in session
  state, flags unverified figures in the generated summary.
- `block_advice_requests` (`before_model_callback`) — short-circuits direct
  "should I buy?" questions with a safe, model-free response (a Day-4 security /
  responsible-AI control, and a natural hook for prompt-injection defenses).

## How to attach

```python
from google.adk.agents import Agent
from app.skills.guardrails import (
    ground_tool_output, append_disclaimer_and_flag_numbers, block_advice_requests,
)

agent = Agent(
    name="portfolio_coordinator",
    model="gemini-2.5-flash",
    tools=[...],
    before_model_callback=block_advice_requests,
    after_tool_callback=ground_tool_output,
    after_model_callback=append_disclaimer_and_flag_numbers,
)
```

## Honest limitations
- Guardrails **detect and constrain**; they do not eliminate hallucination.
- `ungrounded_numbers` is a heuristic and can raise false positives (e.g. a year
  like 2026) — it flags for review rather than deleting.
- The forecast is calculated using a deterministic Holt projection model; `clamp_forecast` bounds the projection to ensure mathematical consistency while Gemini provides the qualitative commentary.
