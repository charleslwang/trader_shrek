import json
from datetime import date, timedelta

from shrek_ai.scripts.run_market_hours_executor import (
    _parse_source_docs,
    _research_age_days,
    _source_confidence,
)


def test_parse_source_docs_reads_confidence_blob():
    source_docs = json.dumps({
        "valuation_confidence": 0.22,
        "proxy_confidence": 0.77,
    })

    parsed = _parse_source_docs(source_docs)

    assert _source_confidence(parsed, "valuation_confidence", 0.65) == 0.22
    assert _source_confidence(parsed, "proxy_confidence", 0.65) == 0.77


def test_parse_source_docs_tolerates_legacy_string():
    parsed = _parse_source_docs("filing_analysis,valuation_analysis")

    assert parsed == {}
    assert _source_confidence(parsed, "valuation_confidence", 0.65) == 0.65


def test_research_age_days():
    recent = date.today() - timedelta(days=3)

    assert _research_age_days(recent.isoformat()) == 3
    assert _research_age_days("not-a-date") is None
