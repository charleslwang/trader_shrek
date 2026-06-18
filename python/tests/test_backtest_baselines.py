import pandas as pd
import pytest

from shrek_ai.backtest import Backtest


def test_backtest_baseline_curve_and_metrics():
    backtest = object.__new__(Backtest)
    backtest.initial_capital = 1000.0
    backtest.start_date = "2024-01-01"
    backtest.price_history = {
        "AAA": pd.Series(
            [10.0, 11.0, 12.0],
            index=pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
        ),
        "BBB": pd.Series(
            [20.0, 20.0, 22.0],
            index=pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
        ),
    }

    curve = backtest._buy_and_hold_curve(
        ["AAA", "BBB"],
        ["2024-01-01", "2024-01-02", "2024-01-03"],
    )
    metrics = backtest._results_from_curve(curve)

    assert curve[0] == 1000.0
    assert curve[-1] == 1150.0
    assert metrics["total_return"] == pytest.approx(0.15)
