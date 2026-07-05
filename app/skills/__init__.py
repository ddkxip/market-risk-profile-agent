"""AlphaInsight agent skill library.

Reusable, framework-native capabilities that make the agents more reliable:
- validators:  deterministic sanity checks on grounded data (no LLM involved)
- guardrails:  ADK callbacks that validate/repair/flag agent + tool outputs

These are designed to be attached to any ADK LlmAgent via its callback hooks,
or called directly on Pydantic results. They reduce and surface hallucinated
numbers; they do not claim to eliminate them.
"""
