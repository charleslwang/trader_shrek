"""
Generate a lightweight post-market review from stored Shrek decisions.
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

from loguru import logger

from shrek_ai.config import load_env
from shrek_ai.storage import StorageManager


def _finite_float(value, default=None):
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed == parsed else default


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a Shrek post-market review")
    parser.add_argument(
        "--storage",
        type=Path,
        default=Path("data/storage"),
        help="Storage directory containing shrek_analytics.duckdb",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional JSON report path",
    )
    args = parser.parse_args()

    load_env()

    storage = StorageManager(args.storage)
    latest = storage.get_latest_decisions()

    decision_counts = {}
    if not latest.empty and "decision" in latest.columns:
        decision_counts = latest["decision"].fillna("UNKNOWN").value_counts().to_dict()

    buy_candidates = []
    if not latest.empty:
        buy_rows = latest[latest["decision"].isin(["BUY_STARTER", "CONVICTION_BUY", "ADD"])]
        for _, row in buy_rows.sort_values("shrek_score", ascending=False).head(10).iterrows():
            buy_candidates.append({
                "symbol": row.get("symbol"),
                "decision": row.get("decision"),
                "shrek_score": _finite_float(row.get("shrek_score")),
                "expected_return": _finite_float(row.get("expected_return")),
                "risk_penalty": _finite_float(row.get("risk_penalty")),
                "date": str(row.get("date")),
            })

    risk_reviews = []
    if not latest.empty:
        review_rows = latest[
            (latest["decision"].isin(["SELL", "TRIM", "AVOID", "WATCH"]))
            | (latest["risk_penalty"].fillna(0) >= 0.65)
        ]
        for _, row in review_rows.sort_values("risk_penalty", ascending=False).head(10).iterrows():
            risk_reviews.append({
                "symbol": row.get("symbol"),
                "decision": row.get("decision"),
                "risk_penalty": _finite_float(row.get("risk_penalty")),
                "thesis_probability": _finite_float(row.get("thesis_probability")),
                "date": str(row.get("date")),
            })

    report = {
        "generated_at": datetime.now().isoformat(),
        "symbols_reviewed": int(len(latest)),
        "decision_counts": decision_counts,
        "buy_candidates": buy_candidates,
        "risk_reviews": risk_reviews,
    }

    output = args.output
    if output is None:
        output = Path("data/reports") / f"post_market_{datetime.now().date().isoformat()}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    logger.info("Post-market review saved to {}", output)
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
