from shrek_ai.decision_policy import (
    BUY_DECISIONS,
    SELL_DECISIONS,
    normalize_decision_label,
    validate_final_decision,
)


PASSING_BUY_METRICS = {
    "expected_return": 0.28,
    "upside_downside": 3.0,
    "quality": 0.75,
    "risk_penalty": 0.25,
    "thesis_probability": 0.78,
    "timing": 0.60,
    "shrek_score": 0.82,
    "secular_conviction": 0.20,
    "narrative_conviction": 0.20,
    "valuation_confidence": 0.80,
    "proxy_confidence": 0.80,
}


def test_normalize_raw_agent_actions_to_strict_enum():
    assert normalize_decision_label("buy") == "BUY_STARTER"
    assert normalize_decision_label("strong buy") == "CONVICTION_BUY"
    assert normalize_decision_label("reduce") == "TRIM"
    assert normalize_decision_label("sell") == "SELL"
    assert normalize_decision_label("unknown") == "AVOID"


def test_raw_buy_becomes_actionable_only_after_math_gate():
    decision = validate_final_decision({"decision": "buy"}, PASSING_BUY_METRICS)
    assert decision["decision"] in BUY_DECISIONS
    assert decision["decision"] == "BUY_STARTER"


def test_low_confidence_valuation_blocks_buy():
    metrics = {**PASSING_BUY_METRICS, "valuation_confidence": 0.20}
    decision = validate_final_decision({"decision": "buy"}, metrics)
    assert decision["decision"] == "WATCH"
    assert "Valuation provenance" in decision["deterministic_gate_reason"]


def test_existing_position_starter_buy_converts_through_add_gate():
    decision = validate_final_decision(
        {"decision": "BUY_STARTER"},
        PASSING_BUY_METRICS,
        position_exists=True,
    )
    assert decision["decision"] == "ADD"
    assert "add gate" in decision["deterministic_gate_reason"]


def test_existing_position_starter_buy_holds_when_add_gate_fails():
    metrics = {**PASSING_BUY_METRICS, "shrek_score": 0.70}
    decision = validate_final_decision(
        {"decision": "BUY_STARTER"},
        metrics,
        position_exists=True,
    )
    assert decision["decision"] == "HOLD"
    assert "does not pass add gate" in decision["deterministic_gate_reason"]


def test_sell_requires_position_and_weak_metrics():
    weak_metrics = {
        **PASSING_BUY_METRICS,
        "expected_return": -0.05,
        "shrek_score": 0.40,
        "valuation_confidence": 0.70,
    }
    no_position = validate_final_decision(
        {"decision": "sell"},
        weak_metrics,
        position_exists=False,
    )
    assert no_position["decision"] == "HOLD"

    with_position = validate_final_decision(
        {"decision": "sell"},
        weak_metrics,
        position_exists=True,
    )
    assert with_position["decision"] in SELL_DECISIONS
    assert with_position["decision"] == "SELL"


def test_agent_sell_is_held_when_metrics_do_not_support_it():
    decision = validate_final_decision(
        {"decision": "sell"},
        PASSING_BUY_METRICS,
        position_exists=True,
    )
    assert decision["decision"] == "HOLD"
