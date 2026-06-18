"""
News data processing and sentiment analysis
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from loguru import logger
from alpaca_trade_api import REST

from .config import get_alpaca_config


class NewsManager:
    """Manage news data for companies via Alpaca news API"""

    def __init__(self):
        config = get_alpaca_config()
        self.api = REST(
            key_id=config['api_key'],
            secret_key=config['secret_key'],
            base_url=config['base_url'],
            api_version='v2'
        )

    def fetch_news(
        self,
        symbol: str,
        days: int = 30,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Fetch recent news for a symbol via Alpaca news API.

        Args:
            symbol: Stock symbol
            days: Number of days to look back
            limit: Maximum number of articles

        Returns:
            List of news articles
        """
        try:
            start = (datetime.now() - timedelta(days=days)).isoformat()
            end = datetime.now().isoformat()
            news = self.api.get_news(symbol, start=start, end=end, limit=limit)
            articles = []
            for item in news:
                articles.append({
                    'title': item.headline,
                    'summary': item.summary,
                    'source': item.source,
                    'url': item.url,
                    'created_at': item.created_at.isoformat() if item.created_at else None,
                    'symbols': item.symbols,
                })
            logger.info(f"Fetched {len(articles)} news articles for {symbol}")
            return articles
        except Exception as e:
            logger.warning(f"Failed to fetch news for {symbol}: {e}")
            return []

    def analyze_sentiment(self, news_item: Dict[str, Any]) -> float:
        """
        Analyze sentiment of a news item using a simple keyword heuristic.

        Args:
            news_item: News item data

        Returns:
            Sentiment score (-1 to 1)
        """
        text = (news_item.get('title', '') + ' ' + news_item.get('summary', '')).lower()

        positive_words = ['beat', 'raise', 'growth', 'surge', 'rally', 'upgrade', 'strong',
                          'outperform', 'breakthrough', 'partnership', 'contract', 'expand']
        negative_words = ['miss', 'cut', 'decline', 'drop', 'downgrade', 'weak',
                          'underperform', 'layoff', 'recall', 'lawsuit', 'investigation',
                          'bankruptcy', 'warning', 'shortfall']

        pos_count = sum(1 for w in positive_words if w in text)
        neg_count = sum(1 for w in negative_words if w in text)

        total = pos_count + neg_count
        if total == 0:
            return 0.0
        return (pos_count - neg_count) / total

    def extract_events(self, news_item: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract thesis-relevant events from news using keyword matching.

        Args:
            news_item: News item data

        Returns:
            List of events
        """
        text = (news_item.get('title', '') + ' ' + news_item.get('summary', '')).lower()
        events = []

        event_keywords = {
            'earnings': ['earnings', 'revenue', 'profit', 'eps'],
            'guidance': ['guidance', 'outlook', 'forecast', 'expect'],
            'product': ['launch', 'product', 'release', 'fda approval'],
            'partnership': ['partnership', 'collaboration', 'deal', 'contract'],
            'acquisition': ['acquisition', 'merger', 'buyout', 'takeover'],
            'personnel': ['ceo', 'executive', 'resign', 'depart', 'appoint'],
            'legal': ['lawsuit', 'sec', 'investigation', 'settlement'],
        }

        for event_type, keywords in event_keywords.items():
            if any(kw in text for kw in keywords):
                sentiment = self.analyze_sentiment(news_item)
                events.append({
                    'event_type': event_type,
                    'title': news_item.get('title', ''),
                    'date': news_item.get('created_at', ''),
                    'sentiment': sentiment,
                })

        return events

    def filter_relevant_news(
        self,
        news: List[Dict[str, Any]],
        thesis_keywords: List[str],
    ) -> List[Dict[str, Any]]:
        """
        Filter news for thesis-relevant articles.

        Args:
            news: List of news articles
            thesis_keywords: Keywords relevant to thesis

        Returns:
            Filtered news articles
        """
        relevant = []

        for article in news:
            title = article.get('title', '').lower()
            summary = article.get('summary', '').lower()

            for keyword in thesis_keywords:
                if keyword.lower() in title or keyword.lower() in summary:
                    relevant.append(article)
                    break

        return relevant
