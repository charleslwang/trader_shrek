"""
Local price cache for Alpaca market data using DuckDB.

Caches historical bars and latest quotes to reduce API calls
and avoid hitting Alpaca rate limits during repeated research runs.
"""

from typing import Optional, Dict, Any
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import duckdb
from loguru import logger


class PriceCache:
    """Cache Alpaca price data locally in DuckDB."""

    def __init__(self, cache_dir: Optional[Path] = None):
        if cache_dir is None:
            cache_dir = Path('data/cache')
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.db_path = self.cache_dir / 'price_cache.duckdb'
        self.conn = duckdb.connect(str(self.db_path))
        self._init_tables()

    def _init_tables(self):
        """Initialize cache tables."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS bars (
                symbol VARCHAR,
                timestamp TIMESTAMP,
                open DOUBLE,
                high DOUBLE,
                low DOUBLE,
                close DOUBLE,
                volume DOUBLE,
                timeframe VARCHAR,
                fetched_at TIMESTAMP,
                PRIMARY KEY (symbol, timestamp, timeframe)
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS quotes (
                symbol VARCHAR PRIMARY KEY,
                bid DOUBLE,
                ask DOUBLE,
                bid_size DOUBLE,
                ask_size DOUBLE,
                timestamp TIMESTAMP,
                fetched_at TIMESTAMP
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS bar_ranges (
                symbol VARCHAR,
                timeframe VARCHAR,
                start_date DATE,
                end_date DATE,
                fetched_at TIMESTAMP,
                PRIMARY KEY (symbol, timeframe, start_date, end_date)
            )
        """)

    def get_bars(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: str = '1Day',
    ) -> Optional[pd.DataFrame]:
        """
        Retrieve cached bars if the full date range exists.

        Returns:
            DataFrame of bars or None if cache miss / partial range.
        """
        # Check if we have the full range cached
        range_check = self.conn.execute(
            """
            SELECT COUNT(*) FROM bar_ranges
            WHERE symbol = ? AND timeframe = ?
              AND start_date <= ?::DATE AND end_date >= ?::DATE
            """,
            [symbol, timeframe, start.date(), end.date()],
        ).fetchone()

        if range_check[0] == 0:
            return None

        df = self.conn.execute(
            """
            SELECT symbol, timestamp, open, high, low, close, volume
            FROM bars
            WHERE symbol = ? AND timeframe = ?
              AND timestamp >= ? AND timestamp <= ?
            ORDER BY timestamp
            """,
            [symbol, timeframe, start, end],
        ).df()

        if df.empty:
            return None

        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.set_index('timestamp')

        logger.debug(f"Cache hit: {symbol} bars {start.date()} to {end.date()}")
        return df

    def save_bars(
        self,
        symbol: str,
        df: pd.DataFrame,
        start: datetime,
        end: datetime,
        timeframe: str = '1Day',
    ):
        """Save bars to cache."""
        if df.empty:
            return

        # Normalize column names to lower case
        df = df.copy()
        df.columns = [c.lower() for c in df.columns]

        # Ensure required columns exist
        required = {'open', 'high', 'low', 'close', 'volume'}
        if not required.issubset(set(df.columns)):
            logger.warning(f"Cannot cache bars for {symbol}: missing required columns")
            return

        # Ensure timestamp column exists
        if 'timestamp' not in df.columns:
            if df.index.name == 'timestamp' or isinstance(df.index, pd.DatetimeIndex):
                df = df.reset_index()
                df.rename(columns={df.columns[0]: 'timestamp'}, inplace=True)
            else:
                logger.warning(f"Cannot cache bars for {symbol}: no timestamp column")
                return

        # Insert bars
        for _, row in df.iterrows():
            self.conn.execute(
                """
                INSERT OR REPLACE INTO bars
                (symbol, timestamp, open, high, low, close, volume, timeframe, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    symbol,
                    row['timestamp'],
                    float(row['open']),
                    float(row['high']),
                    float(row['low']),
                    float(row['close']),
                    float(row['volume']),
                    timeframe,
                    datetime.utcnow(),
                ],
            )

        # Record range
        self.conn.execute(
            """
            INSERT OR REPLACE INTO bar_ranges
            (symbol, timeframe, start_date, end_date, fetched_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            [symbol, timeframe, start.date(), end.date(), datetime.utcnow()],
        )

        logger.debug(f"Cached {len(df)} bars for {symbol}")

    def get_quote(self, symbol: str, max_age_seconds: int = 60) -> Optional[Dict[str, Any]]:
        """Retrieve cached quote if not stale."""
        row = self.conn.execute(
            """
            SELECT bid, ask, bid_size, ask_size, timestamp, fetched_at
            FROM quotes
            WHERE symbol = ? AND fetched_at >= ?
            """,
            [symbol, datetime.utcnow() - timedelta(seconds=max_age_seconds)],
        ).fetchone()

        if row is None:
            return None

        logger.debug(f"Cache hit: {symbol} quote")
        return {
            'symbol': symbol,
            'bid': row[0],
            'ask': row[1],
            'bid_size': row[2],
            'ask_size': row[3],
            'timestamp': row[4],
        }

    def save_quote(self, symbol: str, quote: Dict[str, Any]):
        """Save quote to cache."""
        self.conn.execute(
            """
            INSERT OR REPLACE INTO quotes
            (symbol, bid, ask, bid_size, ask_size, timestamp, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                symbol,
                quote.get('bid'),
                quote.get('ask'),
                quote.get('bid_size'),
                quote.get('ask_size'),
                quote.get('timestamp', datetime.utcnow()),
                datetime.utcnow(),
            ],
        )

    def clear(self):
        """Clear all cached data."""
        self.conn.execute("DELETE FROM bars")
        self.conn.execute("DELETE FROM quotes")
        self.conn.execute("DELETE FROM bar_ranges")
        logger.info("Price cache cleared")

    def close(self):
        """Close database connection."""
        self.conn.close()
