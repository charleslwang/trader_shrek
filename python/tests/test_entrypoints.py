"""
Smoke tests for advertised command modules.
"""

import importlib


def test_advertised_script_modules_import():
    modules = [
        "shrek_ai.scripts.build_universe",
        "shrek_ai.scripts.research_company",
        "shrek_ai.scripts.run_daily_research",
        "shrek_ai.scripts.run_market_hours_executor",
        "shrek_ai.scripts.post_market_review",
        "shrek_ai.scripts.backtest_shrek",
        "shrek_ai.scripts.manual_daily_workflow",
    ]

    for module in modules:
        imported = importlib.import_module(module)
        assert callable(imported.main)


def test_backtest_module_imports():
    imported = importlib.import_module("shrek_ai.backtest")
    assert hasattr(imported, "Backtest")
