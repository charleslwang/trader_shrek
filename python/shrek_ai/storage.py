"""
Storage layer for Python analytics using DuckDB/Parquet
"""

from typing import List, Dict, Any, Optional
from pathlib import Path
import duckdb
import pandas as pd
from datetime import datetime
from loguru import logger


class StorageManager:
    """Manage storage using DuckDB and Parquet"""
    
    def __init__(self, storage_dir: Path):
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        (self.storage_dir / 'features').mkdir(exist_ok=True)
        (self.storage_dir / 'decisions').mkdir(exist_ok=True)
        (self.storage_dir / 'reports').mkdir(exist_ok=True)
        
        # Initialize DuckDB
        self.db_path = self.storage_dir / 'shrek_analytics.duckdb'
        self.conn = duckdb.connect(str(self.db_path))
        
        # Initialize tables
        self._initialize_tables()
    
    def _initialize_tables(self):
        """Initialize DuckDB tables"""
        # Decisions table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS decisions (
                decision_id VARCHAR PRIMARY KEY,
                date DATE,
                symbol VARCHAR,
                current_price DOUBLE,
                v_bear DOUBLE,
                v_base DOUBLE,
                v_bull DOUBLE,
                p_bear DOUBLE,
                p_base DOUBLE,
                p_bull DOUBLE,
                expected_return DOUBLE,
                downside DOUBLE,
                upside_downside DOUBLE,
                thesis_probability DOUBLE,
                quality_score DOUBLE,
                piotroski_score DOUBLE,
                revision_score DOUBLE,
                timing_score DOUBLE,
                risk_penalty DOUBLE,
                shrek_score DOUBLE,
                decision VARCHAR,
                notional DOUBLE,
                order_sent BOOLEAN,
                rust_accept BOOLEAN,
                rust_reject_reason VARCHAR,
                source_docs VARCHAR,
                memo_path VARCHAR,
                secular_conviction DOUBLE,
                narrative_conviction DOUBLE,
                is_conviction BOOLEAN,
                multi_agent BOOLEAN,
                consensus_score DOUBLE,
                debate_rounds INTEGER,
                decision_confidence DOUBLE,
                decision_reasoning VARCHAR
            )
        """)
        
        # Features table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS features (
                id VARCHAR PRIMARY KEY,
                date DATE,
                symbol VARCHAR,
                feature_name VARCHAR,
                feature_value DOUBLE,
                layer VARCHAR
            )
        """)
        
        logger.info("Initialized DuckDB tables")
    
    def save_decision(self, decision: Dict[str, Any]) -> None:
        """
        Save a decision to storage.
        
        Args:
            decision: Decision data
        """
        self.conn.execute("""
            INSERT INTO decisions VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """, (
            decision.get('decision_id'),
            decision.get('date'),
            decision.get('symbol'),
            decision.get('current_price'),
            decision.get('v_bear'),
            decision.get('v_base'),
            decision.get('v_bull'),
            decision.get('p_bear'),
            decision.get('p_base'),
            decision.get('p_bull'),
            decision.get('expected_return'),
            decision.get('downside'),
            decision.get('upside_downside'),
            decision.get('thesis_probability'),
            decision.get('quality_score'),
            decision.get('piotroski_score'),
            decision.get('revision_score'),
            decision.get('timing_score'),
            decision.get('risk_penalty'),
            decision.get('shrek_score'),
            decision.get('decision'),
            decision.get('notional'),
            decision.get('order_sent'),
            decision.get('rust_accept'),
            decision.get('rust_reject_reason'),
            decision.get('source_docs'),
            decision.get('memo_path'),
            decision.get('secular_conviction'),
            decision.get('narrative_conviction'),
            decision.get('is_conviction'),
            decision.get('multi_agent'),
            decision.get('consensus_score'),
            decision.get('debate_rounds'),
            decision.get('decision_confidence'),
            decision.get('decision_reasoning'),
        ))
        
        logger.debug(f"Saved decision {decision.get('decision_id')}")

    def update_decision_execution(
        self,
        decision_id: str,
        *,
        order_sent: bool,
        rust_accept: bool,
        rust_reject_reason: Optional[str] = None,
    ) -> None:
        """Update execution status for a stored decision."""
        self.conn.execute(
            """
            UPDATE decisions
            SET order_sent = ?, rust_accept = ?, rust_reject_reason = ?
            WHERE decision_id = ?
            """,
            (order_sent, rust_accept, rust_reject_reason, decision_id),
        )
        logger.debug(f"Updated execution status for decision {decision_id}")
    
    def get_decisions(
        self,
        symbol: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 1000,
    ) -> pd.DataFrame:
        """
        Retrieve decisions from storage.
        
        Args:
            symbol: Filter by symbol
            start_date: Start date
            end_date: End date
            limit: Maximum number of records
        
        Returns:
            DataFrame of decisions
        """
        query = "SELECT * FROM decisions WHERE 1=1"
        params = []
        
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
        
        query += " ORDER BY date DESC LIMIT ?"
        params.append(limit)
        
        return self.conn.execute(query, params).df()
    
    def save_feature(
        self,
        feature_id: str,
        date: str,
        symbol: str,
        feature_name: str,
        feature_value: float,
        layer: str = 'intermediate',
    ) -> None:
        """
        Save a feature to storage.
        
        Args:
            feature_id: Feature ID
            date: Date
            symbol: Symbol
            feature_name: Feature name
            feature_value: Feature value
            layer: Memory layer
        """
        self.conn.execute("""
            INSERT INTO features VALUES (?, ?, ?, ?, ?, ?)
        """, (feature_id, date, symbol, feature_name, feature_value, layer))
    
    def get_features(
        self,
        symbol: str,
        feature_name: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Retrieve features from storage.
        
        Args:
            symbol: Symbol
            feature_name: Feature name filter
            start_date: Start date
            end_date: End date
        
        Returns:
            DataFrame of features
        """
        query = "SELECT * FROM features WHERE symbol = ?"
        params = [symbol]
        
        if feature_name:
            query += " AND feature_name = ?"
            params.append(feature_name)
        
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
        
        query += " ORDER BY date DESC"
        
        return self.conn.execute(query, params).df()
    
    def get_latest_decisions(self) -> pd.DataFrame:
        """
        Retrieve the latest decision for each symbol across all time.
        
        Returns:
            DataFrame with one row per symbol (the most recent research for that symbol)
        """
        query = """
            SELECT d.*
            FROM decisions d
            INNER JOIN (
                SELECT symbol, MAX(date) as max_date
                FROM decisions
                GROUP BY symbol
            ) latest ON d.symbol = latest.symbol AND d.date = latest.max_date
        """
        return self.conn.execute(query).df()
    
    def export_to_parquet(self, table_name: str, output_path: Optional[Path] = None) -> Path:
        """
        Export table to Parquet.
        
        Args:
            table_name: Table name
            output_path: Output path (defaults to storage_dir)
        
        Returns:
            Path to exported file
        """
        if output_path is None:
            output_path = self.storage_dir / f"{table_name}.parquet"
        
        self.conn.execute(f"COPY {table_name} TO '{output_path}' (FORMAT PARQUET)")
        
        logger.info(f"Exported {table_name} to {output_path}")
        return output_path
    
    def close(self):
        """Close database connection"""
        self.conn.close()
