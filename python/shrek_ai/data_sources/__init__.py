"""
Comprehensive data source modules for Shrek AI.

Provides access to:
- SEC EDGAR filings (existing, enhanced)
- Earnings call transcripts (Seeking Alpha, Motley Fool, manual)
- News aggregation (Yahoo Finance, PR Newswire, Business Wire, Google News RSS)
- Investor Relations scraping (IR pages, PDFs, presentations)
- Research reports (boutique firms, free sources)
- Alternative data (patents, job postings, Google Trends)
"""

from .manager import DataSourceManager
from .transcripts import TranscriptFetcher
from .news import NewsAggregator
from .ir_scraper import IRScraper
from .research_reports import ResearchReportAggregator
from .alternative import AlternativeDataFetcher
from .content_extractor import ContentExtractor

__all__ = [
    'DataSourceManager',
    'TranscriptFetcher',
    'NewsAggregator',
    'IRScraper',
    'ResearchReportAggregator',
    'AlternativeDataFetcher',
    'ContentExtractor',
]
