"""
Unified DataSourceManager - orchestrates all data sources.

Provides a single interface for fetching comprehensive company data
from SEC filings, transcripts, news, IR, research reports, and alternative data.
"""

import json
import time
from typing import Optional, Dict, Any, List
from pathlib import Path
from datetime import datetime, timedelta
from loguru import logger

from .transcripts import TranscriptFetcher
from .news import NewsAggregator
from .ir_scraper import IRScraper
from .research_reports import ResearchReportAggregator
from .alternative import AlternativeDataFetcher


class DataSourceManager:
    """
    Unified manager for all data sources.
    
    Fetches and aggregates data from:
    - SEC EDGAR filings (via existing SECEdgar)
    - Earnings call transcripts
    - News (Yahoo, PR Newswire, Business Wire, Google, SEC 8-K)
    - Investor Relations materials
    - Research reports and analyst opinions
    - Alternative data (patents, jobs, trends)
    """
    
    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or Path('data')
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize all fetchers
        self.transcript_fetcher = TranscriptFetcher(
            cache_dir=self.base_dir / 'cache' / 'transcripts',
            storage_dir=self.base_dir / 'transcripts',
        )
        self.news_aggregator = NewsAggregator(
            cache_dir=self.base_dir / 'cache' / 'news',
            storage_dir=self.base_dir / 'news',
        )
        self.ir_scraper = IRScraper(
            cache_dir=self.base_dir / 'cache' / 'ir',
            storage_dir=self.base_dir / 'ir',
        )
        self.research_aggregator = ResearchReportAggregator(
            cache_dir=self.base_dir / 'cache' / 'research',
            storage_dir=self.base_dir / 'research',
        )
        self.alternative_fetcher = AlternativeDataFetcher(
            cache_dir=self.base_dir / 'cache' / 'alternative',
            storage_dir=self.base_dir / 'alternative',
        )
    
    def gather_company_data(
        self,
        symbol: str,
        company_name: str = '',
        domain: str = '',
        include_transcripts: bool = True,
        include_news: bool = True,
        include_ir: bool = True,
        include_research: bool = True,
        include_alternative: bool = True,
        news_days: int = 30,
        transcript_quarters: int = 4,
    ) -> Dict[str, Any]:
        """
        Gather comprehensive data for a company from all sources.
        
        Args:
            symbol: Stock symbol
            company_name: Full company name
            domain: Known company domain
            include_transcripts: Whether to fetch transcripts
            include_news: Whether to fetch news
            include_ir: Whether to scrape IR
            include_research: Whether to fetch research reports
            include_alternative: Whether to fetch alternative data
            news_days: How many days of news to fetch
            transcript_quarters: How many quarters of transcripts
        
        Returns:
            Comprehensive company data dictionary
        """
        logger.info(f"Gathering comprehensive data for {symbol}")
        start_time = time.time()
        
        data = {
            'symbol': symbol,
            'company_name': company_name,
            'gathered_at': datetime.now().isoformat(),
            'sources': {},
            'consolidated': {},
        }
        
        # 1. Earnings Transcripts
        if include_transcripts:
            try:
                transcripts = self.transcript_fetcher.get_transcripts(symbol, transcript_quarters)
                data['sources']['transcripts'] = transcripts
                
                # Build consolidated transcript text
                transcript_texts = []
                for t in transcripts:
                    transcript_texts.append(
                        f"=== {t.get('quarter', 'Unknown')} Transcript ({t.get('source', '')}) ===\n"
                        f"{t.get('content', '')[:8000]}"
                    )
                data['consolidated']['transcript_text'] = '\n\n'.join(transcript_texts)
                logger.info(f"  Transcripts: {len(transcripts)} found")
            except Exception as e:
                logger.error(f"Failed to fetch transcripts for {symbol}: {e}")
                data['sources']['transcripts'] = []
        
        # 2. News
        if include_news:
            try:
                news = self.news_aggregator.get_news(symbol, company_name, days=news_days)
                data['sources']['news'] = news
                
                # Build consolidated news text
                news_texts = []
                for article in news[:20]:  # Top 20 articles
                    news_texts.append(
                        f"[{article.get('source', '')}] {article.get('title', '')}\n"
                        f"{article.get('summary', '')}"
                    )
                data['consolidated']['news_text'] = '\n\n'.join(news_texts)
                
                # Extract thesis-relevant events
                thesis_keywords = [
                    'partnership', 'contract', 'patent', 'FDA', 'approval',
                    'acquisition', 'merger', 'guidance', 'product launch',
                    'AI', 'artificial intelligence', 'platform', 'cloud',
                    'government', 'defense', 'sovereign',
                ]
                relevant_news = self.news_aggregator.filter_thesis_relevant(news, thesis_keywords)
                events = self.news_aggregator.extract_events(relevant_news)
                data['consolidated']['news_events'] = events
                
                logger.info(f"  News: {len(news)} articles, {len(relevant_news)} thesis-relevant, {len(events)} events")
            except Exception as e:
                logger.error(f"Failed to fetch news for {symbol}: {e}")
                data['sources']['news'] = []
        
        # 3. IR Materials
        if include_ir:
            try:
                ir_data = self.ir_scraper.scrape_ir(symbol, company_name, domain)
                data['sources']['ir'] = ir_data
                data['consolidated']['ir_text'] = ir_data.get('presentations_text', '')
                logger.info(f"  IR: {len(ir_data.get('presentations', []))} presentations")
            except Exception as e:
                logger.error(f"Failed to scrape IR for {symbol}: {e}")
                data['sources']['ir'] = {}
        
        # 4. Research Reports
        if include_research:
            try:
                research = self.research_aggregator.get_research(symbol, company_name)
                data['sources']['research'] = research
                data['consolidated']['research_text'] = research.get('consolidated_text', '')
                data['consolidated']['analyst_consensus'] = research.get('analyst_consensus', {})
                data['consolidated']['bullish_theses'] = research.get('bullish_theses', [])
                data['consolidated']['bearish_theses'] = research.get('bearish_theses', [])
                logger.info(f"  Research: {len(research.get('research_articles', []))} articles")
            except Exception as e:
                logger.error(f"Failed to fetch research for {symbol}: {e}")
                data['sources']['research'] = {}
        
        # 5. Alternative Data
        if include_alternative:
            try:
                alt_data = self.alternative_fetcher.get_alternative_data(symbol, company_name)
                data['sources']['alternative'] = alt_data
                data['consolidated']['alternative_text'] = alt_data.get('consolidated_text', '')
                data['consolidated']['alternative_signals'] = alt_data.get('signals', [])
                logger.info(f"  Alternative: {len(alt_data.get('patents', []))} patents, {len(alt_data.get('job_postings', []))} jobs")
            except Exception as e:
                logger.error(f"Failed to fetch alternative data for {symbol}: {e}")
                data['sources']['alternative'] = {}
        
        # Build master consolidated text for LLM consumption
        master_text = self._build_master_text(data['consolidated'])
        data['consolidated']['master_text'] = master_text
        
        elapsed = time.time() - start_time
        logger.info(f"Data gathering complete for {symbol} in {elapsed:.1f}s")
        
        return data
    
    def _build_master_text(self, consolidated: Dict[str, Any]) -> str:
        """Build a master text combining all sources for LLM analysis."""
        sections = []
        
        # Transcripts (highest priority - forward-looking)
        if consolidated.get('transcript_text'):
            sections.append("## EARNINGS CALL TRANSCRIPTS\n\n" + consolidated['transcript_text'])
        
        # News (timely)
        if consolidated.get('news_text'):
            sections.append("## RECENT NEWS\n\n" + consolidated['news_text'])
        
        # IR presentations (strategic)
        if consolidated.get('ir_text'):
            sections.append("## INVESTOR PRESENTATIONS\n\n" + consolidated['ir_text'])
        
        # Research (analyst views)
        if consolidated.get('research_text'):
            sections.append("## ANALYST RESEARCH\n\n" + consolidated['research_text'])
        
        # Alternative data
        if consolidated.get('alternative_text'):
            sections.append("## ALTERNATIVE DATA SIGNALS\n\n" + consolidated['alternative_text'])
        
        # News events summary
        if consolidated.get('news_events'):
            event_lines = ["## EXTRACTED EVENTS"]
            for event in consolidated['news_events'][:10]:
                event_lines.append(f"- [{event.get('date', '')}] {event.get('event_type', '')}: {event.get('title', '')}")
            sections.append('\n'.join(event_lines))
        
        # Analyst consensus
        consensus = consolidated.get('analyst_consensus', {})
        if consensus:
            sections.append(f"""## ANALYST CONSENSUS
- Buy: {consensus.get('buy_count', 'N/A')} ({consensus.get('buy_pct', 0):.0%})
- Hold: {consensus.get('hold_count', 'N/A')} ({consensus.get('hold_pct', 0):.0%})
- Sell: {consensus.get('sell_count', 'N/A')} ({consensus.get('sell_pct', 0):.0%})
- Price Target: ${consensus.get('price_target', 'N/A')}
""")
        
        # Bullish/Bearish theses
        bullish = consolidated.get('bullish_theses', [])
        bearish = consolidated.get('bearish_theses', [])
        
        if bullish:
            sections.append("## BULLISH ANALYST THESES")
            for thesis in bullish[:5]:
                sections.append(f"- [{thesis.get('source', '')}] {thesis.get('title', '')}")
        
        if bearish:
            sections.append("## BEARISH ANALYST THESES")
            for thesis in bearish[:5]:
                sections.append(f"- [{thesis.get('source', '')}] {thesis.get('title', '')}")
        
        # Alternative signals
        signals = consolidated.get('alternative_signals', [])
        if signals:
            sections.append("## ALTERNATIVE DATA SIGNALS")
            for signal in signals:
                sections.append(f"- {signal.get('type', '')}: {signal.get('description', '')} (score: {signal.get('score', 0):.2f})")
        
        return '\n\n'.join(sections)
    
    def save_company_data(self, symbol: str, data: Dict[str, Any]) -> Path:
        """Save gathered data to storage."""
        filepath = self.base_dir / 'cache' / f"{symbol}_comprehensive_data.json"
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        
        return filepath
    
    def load_company_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Load previously gathered data."""
        filepath = self.base_dir / 'cache' / f"{symbol}_comprehensive_data.json"
        if not filepath.exists():
            return None
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load data for {symbol}: {e}")
            return None
    
    def get_source_summary(self, data: Dict[str, Any]) -> str:
        """Get a human-readable summary of gathered data."""
        sources = data.get('sources', {})
        
        summary = []
        summary.append(f"Data for {data.get('symbol', 'Unknown')}:")
        
        if 'transcripts' in sources:
            summary.append(f"  Transcripts: {len(sources['transcripts'])}")
        
        if 'news' in sources:
            summary.append(f"  News articles: {len(sources['news'])}")
        
        if 'ir' in sources:
            ir = sources['ir']
            summary.append(f"  IR presentations: {len(ir.get('presentations', []))}")
        
        if 'research' in sources:
            research = sources['research']
            summary.append(f"  Research articles: {len(research.get('research_articles', []))}")
        
        if 'alternative' in sources:
            alt = sources['alternative']
            summary.append(f"  Patents: {len(alt.get('patents', []))}")
            summary.append(f"  Job postings: {len(alt.get('job_postings', []))}")
        
        return '\n'.join(summary)
