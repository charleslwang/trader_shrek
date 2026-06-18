"""
Shared decision normalization and deterministic gates.
"""

from __future__ import annotations

from enum import Enum
from math import isfinite
from typing import Any, Mapping, Optional

from loguru import logger

from shrek_ai.math import entry_decision, investability_gate


class Decision(str, Enum):
    AVOID = "AVOID"
    WATCH = "WATCH"
    HOLD = "HOLD"
    BUY_STARTER = "BUY_STARTER"
    ADD = "ADD"
    CONVICTION_BUY = "CONVICTION_BUY"
    TRIM = "TRIM"
    SELL = "SELL"


BUY_DECISIONS = {Decision.BUY_STARTER.value, Decision.ADD.value, Decision.CONVICTION_BUY.value}
SELL_DECISIONS = {Decision.TRIM.value, Decision.SELL.value}
ACTIONABLE_DECISIONS = BUY_DECISIONS | SELL_DECISIONS


_ACTION_ALIASES = {
    "": Decision.AVOID.value,
    "AVOID": Decision.AVOID.value,
    "PASS": Decision.AVOID.value,
    "NO_BUY": Decision.AVOID.value,
    "WATCH": Decision.WATCH.value,
    "MONITOR": Decision.WATCH.value,
    "WAIT": Decision.WATCH.value,
    "HOLD": Decision.HOLD.value,
    "BUY": Decision.BUY_STARTER.value,
    "STARTER": Decision.BUY_STARTER.value,
    "STARTER_BUY": Decision.BUY_STARTER.value,
    "BUY_STARTER": Decision.BUY_STARTER.value,
    "ADD": Decision.ADD.value,
    "BUY_MORE": Decision.ADD.value,
    "CONVICTION": Decision.CONVICTION_BUY.value,
    "CONVICTION_BUY": Decision.CONVICTION_BUY.value,
    "STRONG_BUY": Decision.CONVICTION_BUY.value,
    "TRIM": Decision.TRIM.value,
    "REDUCE": Decision.TRIM.value,
    "SELL": Decision.SELL.value,
    "EXIT": Decision.SELL.value,
}


def normalize_decision_label(value: Any) -> str:
    """Map raw LLM or legacy labels into the strict decision enum."""
    text = str(value or "").upper().strip().replace("-", "_").replace(" ", "_")
    return _ACTION_ALIASES.get(text, Decision.AVOID.value)


def normalize_agent_decision(decision: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return a copy of an agent decision with a strict decision label."""
    normalized = dict(decision or {})
    raw = normalized.get("decision", normalized.get("action", "AVOID"))
    normalized["raw_decision"] = raw
    normalized["decision"] = normalize_decision_label(raw)
    return normalized


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if isfinite(parsed) else default


def _thresholds_from_config(config: Any) -> dict[str, float] | None:
    if config is None or not hasattr(config, "entry_thresholds"):
        return None
    entry = config.entry_thresholds
    return {
        "min_shrek_score": _safe_float(getattr(entry, "min_shrek_score", 0.75), 0.75),
        "min_expected_return": _safe_float(
            getattr(entry, "min_expected_return_12m", 0.20), 0.20
        ),
        "min_upside_downside": _safe_float(
            getattr(entry, "min_upside_downside_ratio", 2.0), 2.0
        ),
        "min_quality": _safe_float(getattr(entry, "min_quality_score", 0.65), 0.65),
        "max_risk_penalty": _safe_float(getattr(entry, "max_risk_penalty", 0.45), 0.45),
        "min_thesis_probability": _safe_float(
            getattr(entry, "min_thesis_probability", 0.70), 0.70
        ),
        "min_timing": _safe_float(getattr(entry, "min_timing_score", 0.45), 0.45),
    }


def _metric(metrics: Mapping[str, Any], key: str, default: float = 0.0) -> float:
    return _safe_float(metrics.get(key), default)


def validate_final_decision(
    agent_decision: Mapping[str, Any] | None,
    metrics: Mapping[str, Any],
    *,
    position_exists: Optional[bool] = None,
    config: Any = None,
) -> dict[str, Any]:
    """
    Normalize and gate the final research decision before storage or execution.

    LLM agents can express intent, but this function is the last word on whether
    the stored/actionable decision is a buy, add, trim, sell, hold, watch, or avoid.
    """
    decision = normalize_agent_decision(agent_decision)
    requested = decision["decision"]

    expected_return = _metric(metrics, "expected_return")
    upside_downside = _metric(metrics, "upside_downside")
    quality = _metric(metrics, "quality", _metric(metrics, "quality_score"))
    risk_penalty = _metric(metrics, "risk_penalty")
    thesis_probability = _metric(metrics, "thesis_probability")
    timing = _metric(metrics, "timing", _metric(metrics, "timing_score"))
    shrek_score = _metric(metrics, "shrek_score")
    secular_conviction = _metric(metrics, "secular_conviction")
    narrative_conviction = _metric(metrics, "narrative_conviction")
    valuation_confidence = _metric(metrics, "valuation_confidence", 1.0)
    proxy_confidence = _metric(metrics, "proxy_confidence", 1.0)

    thresholds = _thresholds_from_config(config)

    def finish(new_decision: str, reason: str) -> dict[str, Any]:
        if new_decision != requested:
            decision["validation_override"] = reason
            logger.info(
                "Decision gate changed {} to {}: {}",
                requested,
                new_decision,
                reason,
            )
        decision["decision"] = new_decision
        decision["deterministic_gate_reason"] = reason
        return decision

    if requested in BUY_DECISIONS:
        if valuation_confidence < 0.45:
            return finish(Decision.WATCH.value, "Valuation provenance confidence below buy threshold")
        if proxy_confidence < 0.40:
            return finish(Decision.WATCH.value, "Too many key scores rely on low-confidence proxies")

        if requested in {
            Decision.ADD.value,
            Decision.BUY_STARTER.value,
            Decision.CONVICTION_BUY.value,
        } and position_exists is True:
            if investability_gate(
                expected_return=expected_return,
                upside_downside=upside_downside,
                quality=quality,
                risk_penalty=risk_penalty,
                thesis_probability=thesis_probability,
                timing=timing,
                thresholds=thresholds,
            ) and shrek_score >= 0.78:
                return finish(Decision.ADD.value, "Existing position passes add gate")
            return finish(Decision.HOLD.value, "Existing position does not pass add gate")

        deterministic, reason = entry_decision(
            position_exists=False,
            shrek_score=shrek_score,
            expected_return=expected_return,
            upside_downside=upside_downside,
            quality=quality,
            risk_penalty=risk_penalty,
            thesis_probability=thesis_probability,
            timing=timing,
            secular_conviction=secular_conviction,
            narrative_conviction=narrative_conviction,
            thresholds=thresholds,
        )
        return finish(deterministic, reason)

    if requested in SELL_DECISIONS:
        if position_exists is False:
            return finish(Decision.HOLD.value, "Sell/trim ignored because no position exists")
        if valuation_confidence < 0.35 and risk_penalty < 0.75 and thesis_probability >= 0.50:
            return finish(Decision.HOLD.value, "Sell/trim blocked by low valuation confidence")

        if (
            expected_return <= 0.0
            or shrek_score < 0.50
            or thesis_probability < 0.50
            or risk_penalty >= 0.75
        ):
            return finish(Decision.SELL.value, "Sell gate passed")

        if requested == Decision.SELL.value and (
            expected_return < 0.05
            or upside_downside < 1.0
            or shrek_score < 0.55
            or thesis_probability < 0.55
            or risk_penalty >= 0.70
        ):
            return finish(Decision.SELL.value, "Agent sell supported by weak metrics")

        if (
            requested == Decision.TRIM.value
            or expected_return < 0.08
            or upside_downside < 1.20
            or shrek_score < 0.60
            or thesis_probability < 0.60
            or risk_penalty >= 0.65
        ):
            return finish(Decision.TRIM.value, "Trim gate passed")

        return finish(Decision.HOLD.value, "Sell/trim signal not supported by deterministic metrics")

    if requested in {Decision.HOLD.value, Decision.WATCH.value, Decision.AVOID.value}:
        return finish(requested, "Non-actionable decision preserved")

    return finish(Decision.AVOID.value, "Unknown decision normalized to AVOID")


def is_actionable_decision(decision: Any) -> bool:
    return normalize_decision_label(decision) in ACTIONABLE_DECISIONS
