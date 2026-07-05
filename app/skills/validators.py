"""Deterministic validators — the grounding layer of the skill library.

Every function here is pure and deterministic (no LLM, no network). They check
that grounded data is internally consistent and within physically-possible
ranges, and can gently repair implausible LLM-generated forecasts. Because they
never call a model, their verdicts are trustworthy and cheap.

Each validator returns a list[str] of human-readable issues (empty == clean),
so callers can log, flag in the UI, or fail an eval on them.
"""

from __future__ import annotations

import math
import re
from datetime import datetime
from typing import Optional

# Allowed enum-like values, kept in one place so the UI, evals, and guardrails agree.
VALID_TREND = {
    "Strong Bullish",
    "Moderately Bullish (Short-term)",
    "Strong Bearish",
    "Neutral / Sideways",
}
VALID_SENTIMENT = {"Bullish", "Bearish", "Neutral"}
VALID_CONFIDENCE = {"High", "Medium", "Low"}

# A single trading day rarely moves more than this for a large-cap equity.
# Used to catch LLM forecasts that invent unrealistic spikes/crashes.
MAX_DAILY_MOVE_PCT = 0.25


def _is_finite_number(x) -> bool:
    return isinstance(x, (int, float)) and not (math.isnan(x) or math.isinf(x))


def validate_technicals(tech) -> list[str]:
    """Validate a TechnicalIndicatorValues object. Returns list of issues."""
    issues: list[str] = []
    if not _is_finite_number(tech.current_price) or tech.current_price <= 0:
        issues.append(f"current_price {tech.current_price!r} is not a positive number")
    if not _is_finite_number(tech.rsi_14) or not (0.0 <= tech.rsi_14 <= 100.0):
        issues.append(f"rsi_14 {tech.rsi_14!r} outside [0, 100]")
    for field in ("sma_50", "sma_200", "macd_value", "macd_signal"):
        val = getattr(tech, field, None)
        if not _is_finite_number(val):
            issues.append(f"{field} {val!r} is not a finite number")
    if tech.trend_status not in VALID_TREND:
        issues.append(f"trend_status {tech.trend_status!r} not a recognised value")
    return issues


def validate_sentiment(sent) -> list[str]:
    """Validate a SentimentAnalysis object. Returns list of issues."""
    issues: list[str] = []
    if not _is_finite_number(sent.score) or not (-1.0 <= sent.score <= 1.0):
        issues.append(f"sentiment score {sent.score!r} outside [-1.0, 1.0]")
    if sent.overall_sentiment not in VALID_SENTIMENT:
        issues.append(f"overall_sentiment {sent.overall_sentiment!r} not recognised")
    return issues


def _valid_date(s: str) -> bool:
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return True
    except (ValueError, TypeError):
        return False


def validate_forecast(forecast, last_close: Optional[float] = None) -> list[str]:
    """Validate a ForecastData object. If last_close is given, also check that
    day-over-day moves are physically plausible. Returns list of issues.
    """
    issues: list[str] = []
    if forecast is None:
        return ["forecast object is missing"]

    pts = getattr(forecast, "points", []) or []
    if len(pts) != 5:
        issues.append(f"expected exactly 5 forecast points, got {len(pts)}")

    prev = last_close
    for i, pt in enumerate(pts):
        if not _is_finite_number(pt.price) or pt.price <= 0:
            issues.append(f"forecast point {i + 1} price {pt.price!r} not positive")
        if not _valid_date(pt.date):
            issues.append(f"forecast point {i + 1} date {pt.date!r} not YYYY-MM-DD")
        if prev and _is_finite_number(getattr(pt, "price", None)) and pt.price > 0:
            move = abs(pt.price - prev) / prev
            if move > MAX_DAILY_MOVE_PCT:
                issues.append(
                    f"forecast point {i + 1} implies a {move:.0%} move from "
                    f"{prev:.2f} to {pt.price:.2f} (> {MAX_DAILY_MOVE_PCT:.0%} threshold)"
                )
        if _is_finite_number(getattr(pt, "price", None)):
            prev = pt.price

    if forecast.confidence_level not in VALID_CONFIDENCE:
        issues.append(f"confidence_level {forecast.confidence_level!r} not recognised")
    return issues


def clamp_forecast(forecast, last_close: float):
    """Repair an implausible forecast in place by clamping each day's move to
    +/- MAX_DAILY_MOVE_PCT of the prior day. Returns (forecast, list_of_repairs).
    Use this when you'd rather present a bounded projection than reject it.
    """
    repairs: list[str] = []
    prev = last_close
    for i, pt in enumerate(getattr(forecast, "points", []) or []):
        if not _is_finite_number(getattr(pt, "price", None)) or prev is None:
            continue
        hi = prev * (1 + MAX_DAILY_MOVE_PCT)
        lo = prev * (1 - MAX_DAILY_MOVE_PCT)
        if pt.price > hi:
            repairs.append(f"day {i + 1}: clamped {pt.price:.2f} -> {hi:.2f}")
            pt.price = round(hi, 2)
        elif pt.price < lo:
            repairs.append(f"day {i + 1}: clamped {pt.price:.2f} -> {lo:.2f}")
            pt.price = round(lo, 2)
        prev = pt.price
    return forecast, repairs


# --- Narrative grounding heuristic -------------------------------------------

# Matches money ($1,234.56) and percentage (12.3%) figures in prose.
_MONEY_RE = re.compile(r"\$\s?([0-9][0-9,]*\.?[0-9]*)")
_PCT_RE = re.compile(r"([0-9]+\.?[0-9]*)\s?%")


def extract_reported_numbers(text: str) -> list[float]:
    """Pull money and percentage figures out of generated prose."""
    nums: list[float] = []
    for m in _MONEY_RE.findall(text or ""):
        try:
            nums.append(float(m.replace(",", "")))
        except ValueError:
            pass
    for m in _PCT_RE.findall(text or ""):
        try:
            nums.append(float(m))
        except ValueError:
            pass
    return nums


def ungrounded_numbers(text: str, grounded: list[float], tol: float = 0.02) -> list[float]:
    """Return money/percent figures in `text` that don't match any grounded
    value within relative tolerance `tol`. HEURISTIC: it can't tell a price from
    a coincidental number, so treat the result as a flag for review, not proof.
    """
    flagged: list[float] = []
    for n in extract_reported_numbers(text):
        if not any(g != 0 and abs(n - g) / abs(g) <= tol for g in grounded if g):
            flagged.append(n)
    return flagged
