"""
Fundamental data processing and financial statement analysis
"""

import re
from typing import Dict, Any, Optional
import pandas as pd
from loguru import logger


class FundamentalsProcessor:
    """Process fundamental data from SEC filings"""

    def __init__(self):
        pass

    @staticmethod
    def _extract_number_near_label(text: str, label: str, patterns: list) -> Optional[float]:
        """Extract a number near a label using multiple regex patterns."""
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    val_str = match.group(1).replace(',', '').replace('(', '-').replace(')', '')
                    val = float(val_str)
                    return val
                except (ValueError, IndexError):
                    continue
        return None

    def parse_income_statement(self, filing_content: str) -> Optional[Dict[str, Any]]:
        """
        Parse income statement from filing content using regex heuristics.

        Args:
            filing_content: Filing text content

        Returns:
            Dictionary of income statement items
        """
        text = filing_content.lower()
        data = {}

        patterns = {
            'revenue': [
                r'revenues?\s*[,;]?\s*\$?\s*([\d,]+(?:\.\d+)?)\s*(million|billion)?',
                r'total\s+revenues?\s*[,;]?\s*\$?\s*([\d,]+(?:\.\d+)?)',
            ],
            'cogs': [
                r'cost\s+of\s+(?:revenue|sales|goods)\s*[,;]?\s*\$?\s*([\d,]+(?:\.\d+)?)',
            ],
            'operating_income': [
                r'operating\s+(?:income|profit)\s*[,;]?\s*\$?\s*([\d,]+(?:\.\d+)?)',
            ],
            'net_income': [
                r'net\s+income\s*[,;]?\s*\$?\s*([\d,]+(?:\.\d+)?)',
                r'net\s+earnings\s*[,;]?\s*\$?\s*([\d,]+(?:\.\d+)?)',
            ],
        }

        for key, pats in patterns.items():
            val = self._extract_number_near_label(text, key, pats)
            if val is not None:
                data[key] = val

        if not data:
            logger.debug("No income statement data extracted from filing")
            return None
        return data

    def parse_balance_sheet(self, filing_content: str) -> Optional[Dict[str, Any]]:
        """
        Parse balance sheet from filing content using regex heuristics.

        Args:
            filing_content: Filing text content

        Returns:
            Dictionary of balance sheet items
        """
        text = filing_content.lower()
        data = {}

        patterns = {
            'total_assets': [
                r'total\s+assets\s*[,;]?\s*\$?\s*([\d,]+(?:\.\d+)?)',
            ],
            'total_debt': [
                r'total\s+(?:debt|liabilities)\s*[,;]?\s*\$?\s*([\d,]+(?:\.\d+)?)',
            ],
            'current_assets': [
                r'current\s+assets\s*[,;]?\s*\$?\s*([\d,]+(?:\.\d+)?)',
            ],
            'current_liabilities': [
                r'current\s+liabilities\s*[,;]?\s*\$?\s*([\d,]+(?:\.\d+)?)',
            ],
            'cash': [
                r'cash\s+and\s+cash\s+equivalents\s*[,;]?\s*\$?\s*([\d,]+(?:\.\d+)?)',
            ],
        }

        for key, pats in patterns.items():
            val = self._extract_number_near_label(text, key, pats)
            if val is not None:
                data[key] = val

        if not data:
            logger.debug("No balance sheet data extracted from filing")
            return None
        return data

    def parse_cash_flow(self, filing_content: str) -> Optional[Dict[str, Any]]:
        """
        Parse cash flow statement from filing content using regex heuristics.

        Args:
            filing_content: Filing text content

        Returns:
            Dictionary of cash flow items
        """
        text = filing_content.lower()
        data = {}

        patterns = {
            'free_cash_flow': [
                r'free\s+cash\s+flow\s*[,;]?\s*\$?\s*([\d,]+(?:\.\d+)?)',
            ],
            'operating_cash_flow': [
                r'net\s+cash\s+(?:provided\s+by|from)\s+operating\s+activities\s*[,;]?\s*\$?\s*([\d,]+(?:\.\d+)?)',
            ],
            'capital_expenditures': [
                r'capital\s+expenditures?\s*[,;]?\s*\$?\s*([\d,]+(?:\.\d+)?)',
            ],
        }

        for key, pats in patterns.items():
            val = self._extract_number_near_label(text, key, pats)
            if val is not None:
                data[key] = val

        if not data:
            logger.debug("No cash flow data extracted from filing")
            return None
        return data
    
    def calculate_metrics(self, financial_data: Dict[str, Any]) -> Dict[str, float]:
        """
        Calculate financial metrics from raw data.
        
        Args:
            financial_data: Raw financial data
        
        Returns:
            Dictionary of calculated metrics
        """
        metrics = {}
        
        # Revenue growth
        if 'revenue_current' in financial_data and 'revenue_prior' in financial_data:
            if financial_data['revenue_prior'] > 0:
                metrics['revenue_growth'] = (
                    (financial_data['revenue_current'] - financial_data['revenue_prior']) /
                    financial_data['revenue_prior']
                )
        
        # Gross margin
        if 'revenue' in financial_data and 'cogs' in financial_data:
            if financial_data['revenue'] > 0:
                metrics['gross_margin'] = (
                    (financial_data['revenue'] - financial_data['cogs']) /
                    financial_data['revenue']
                )
        
        # Operating margin
        if 'operating_income' in financial_data and 'revenue' in financial_data:
            if financial_data['revenue'] > 0:
                metrics['operating_margin'] = (
                    financial_data['operating_income'] / financial_data['revenue']
                )
        
        # FCF margin
        if 'free_cash_flow' in financial_data and 'revenue' in financial_data:
            if financial_data['revenue'] > 0:
                metrics['fcf_margin'] = (
                    financial_data['free_cash_flow'] / financial_data['revenue']
                )
        
        # ROA
        if 'net_income' in financial_data and 'total_assets' in financial_data:
            if financial_data['total_assets'] > 0:
                metrics['roa'] = (
                    financial_data['net_income'] / financial_data['total_assets']
                )
        
        # ROIC
        if 'net_income' in financial_data and 'invested_capital' in financial_data:
            if financial_data['invested_capital'] > 0:
                metrics['roic'] = (
                    financial_data['net_income'] / financial_data['invested_capital']
                )
        
        # Debt ratio
        if 'total_debt' in financial_data and 'total_assets' in financial_data:
            if financial_data['total_assets'] > 0:
                metrics['debt_ratio'] = (
                    financial_data['total_debt'] / financial_data['total_assets']
                )
        
        # Current ratio
        if 'current_assets' in financial_data and 'current_liabilities' in financial_data:
            if financial_data['current_liabilities'] > 0:
                metrics['current_ratio'] = (
                    financial_data['current_assets'] / financial_data['current_liabilities']
                )
        
        # Interest coverage
        if 'operating_income' in financial_data and 'interest_expense' in financial_data:
            if financial_data['interest_expense'] > 0:
                metrics['interest_coverage'] = (
                    financial_data['operating_income'] / financial_data['interest_expense']
                )
        
        return metrics
    
    def compare_periods(
        self,
        current_data: Dict[str, Any],
        prior_data: Dict[str, Any],
    ) -> Dict[str, float]:
        """
        Compare financial data between periods.
        
        Args:
            current_data: Current period data
            prior_data: Prior period data
        
        Returns:
            Dictionary of period-over-period changes
        """
        changes = {}
        
        for key in current_data:
            if key in prior_data:
                if prior_data[key] != 0:
                    changes[f'{key}_change'] = (
                        (current_data[key] - prior_data[key]) / prior_data[key]
                    )
                else:
                    changes[f'{key}_change'] = 0.0
        
        return changes
