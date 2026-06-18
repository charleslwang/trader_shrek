"""
Command-line entry point for Shrek backtests.
"""

import argparse
import json
from pathlib import Path

from loguru import logger

from shrek_ai.backtest import Backtest
from shrek_ai.config import load_env


def _read_symbols(path: Path) -> list[str]:
    symbols: list[str] = []
    seen = set()
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            symbol = stripped.upper()
            if symbol not in seen:
                seen.add(symbol)
                symbols.append(symbol)
    return symbols


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a Shrek price-driven backtest")
    parser.add_argument("--start", required=True, help="Start date, YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="End date, YYYY-MM-DD")
    parser.add_argument("--symbols", nargs="*", help="Ticker symbols to backtest")
    parser.add_argument(
        "--candidates",
        type=Path,
        default=Path("data/candidates.txt"),
        help="Candidate symbol file used when --symbols is omitted",
    )
    parser.add_argument("--capital", type=float, default=100000.0, help="Initial capital")
    parser.add_argument(
        "--rebalance",
        choices=["daily", "weekly", "monthly"],
        default="monthly",
        help="Rebalance frequency",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/reports/backtest_results.json"),
        help="Path for JSON results",
    )
    args = parser.parse_args()

    load_env()

    symbols = [s.upper() for s in args.symbols] if args.symbols else _read_symbols(args.candidates)
    if not symbols:
        raise SystemExit("No symbols provided and candidates file is empty")

    backtest = Backtest(
        start_date=args.start,
        end_date=args.end,
        initial_capital=args.capital,
    )
    results = backtest.run_backtest(symbols, rebalance_frequency=args.rebalance)
    backtest.save_results(results, args.output)

    logger.info(
        "Backtest finished: final=${:.2f} return={:.2f}% trades={}",
        results["final_value"],
        results["total_return"] * 100,
        results["num_trades"],
    )

    print(json.dumps({
        "final_value": results["final_value"],
        "total_return": results["total_return"],
        "sharpe_ratio": results["sharpe_ratio"],
        "max_drawdown": results["max_drawdown"],
        "num_trades": results["num_trades"],
        "baselines": results.get("baselines", {}),
        "output": str(args.output),
    }, indent=2))


if __name__ == "__main__":
    main()
