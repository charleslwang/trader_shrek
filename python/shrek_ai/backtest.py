"""
Backtesting system for Shrek
"""

from typing import List, Dict, Any, Optional
from pathlib import Path
import pandas as pd
from datetime import datetime, timedelta
from loguru import logger

from .alpaca_data import AlpacaDataSource
from .math import (
    expected_return,
    downside,
    upside,
    upside_downside_ratio,
    margin_of_safety,
    business_quality_score,
    piotroski_score,
    revision_score,
    timing_score,
    risk_penalty,
    shrek_score,
    investability_gate,
    entry_decision,
    trim_decision,
    sell_decision,
    drawdown,
    max_drawdown,
)


class Backtest:
    """Backtesting engine for Shrek"""
    
    def __init__(self, start_date: str, end_date: str, initial_capital: float = 100000.0):
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        self.alpaca = AlpacaDataSource()
        
        # Track portfolio state
        self.cash = initial_capital
        self.positions = {}  # symbol -> (shares, entry_price)
        self.trades = []
        self.portfolio_values = []
        self.timestamps = []
    
    def run_backtest(
        self,
        symbols: List[str],
        rebalance_frequency: str = 'monthly',
    ) -> Dict[str, Any]:
        """
        Run backtest over the specified period.
        
        Args:
            symbols: List of symbols to trade
            rebalance_frequency: Rebalancing frequency (daily, weekly, monthly)
        
        Returns:
            Backtest results
        """
        logger.info(f"Running backtest from {self.start_date} to {self.end_date}")
        
        # Get trading calendar
        calendar = self.alpaca.get_calendar(start=self.start_date, end=self.end_date)
        trading_days = [d['date'] for d in calendar]
        
        logger.info(f"Found {len(trading_days)} trading days")
        
        # Simulate day by day
        for date in trading_days:
            self._simulate_day(date, symbols, rebalance_frequency)
        
        # Calculate final results
        results = self._calculate_results()
        
        logger.info(f"Backtest complete. Final portfolio value: ${results['final_value']:,.2f}")
        
        return results
    
    def _simulate_day(self, date: str, symbols: List[str], rebalance_frequency: str):
        """Simulate a single trading day"""
        # Get prices for all symbols
        prices = {}
        for symbol in symbols:
            try:
                bars = self.alpaca.get_bars(symbol, timeframe='day', start=date, end=date, limit=1)
                if len(bars) > 0:
                    prices[symbol] = bars.iloc[0]['close']
            except Exception as e:
                logger.warning(f"Failed to get price for {symbol} on {date}: {e}")
        
        # Calculate portfolio value
        portfolio_value = self.cash
        for symbol, (shares, entry_price) in self.positions.items():
            if symbol in prices:
                portfolio_value += shares * prices[symbol]
        
        self.portfolio_values.append(portfolio_value)
        self.timestamps.append(date)
        
        # Rebalance based on frequency
        if self._should_rebalance(date, rebalance_frequency):
            self._rebalance(date, prices, symbols)
    
    def _should_rebalance(self, date: str, frequency: str) -> bool:
        """Check if should rebalance on this date"""
        dt = datetime.fromisoformat(date)
        
        if frequency == 'daily':
            return True
        elif frequency == 'weekly':
            return dt.weekday() == 0  # Monday
        elif frequency == 'monthly':
            return dt.day == 1  # First of month
        
        return False
    
    def _rebalance(self, date: str, prices: Dict[str, float], symbols: List[str]):
        """Rebalance portfolio"""
        # This is a simplified rebalancing logic
        # In a real backtest, this would use the full Shrek decision pipeline
        
        # For now, just implement a simple equal-weight strategy
        target_value_per_symbol = (self.cash + sum(
            shares * prices.get(symbol, 0)
            for symbol, (shares, _) in self.positions.items()
        )) / len(symbols)
        
        for symbol in symbols:
            if symbol not in prices:
                continue
            
            current_value = 0
            if symbol in self.positions:
                shares, entry_price = self.positions[symbol]
                current_value = shares * prices[symbol]
            
            # Adjust position
            diff = target_value_per_symbol - current_value
            
            if abs(diff) > 100:  # Minimum trade size
                shares_to_trade = int(diff / prices[symbol])
                
                if shares_to_trade > 0:
                    # Buy
                    cost = shares_to_trade * prices[symbol]
                    if cost <= self.cash:
                        self.cash -= cost
                        if symbol in self.positions:
                            self.positions[symbol] = (
                                self.positions[symbol][0] + shares_to_trade,
                                self.positions[symbol][1],
                            )
                        else:
                            self.positions[symbol] = (shares_to_trade, prices[symbol])
                        
                        self.trades.append({
                            'date': date,
                            'symbol': symbol,
                            'action': 'buy',
                            'shares': shares_to_trade,
                            'price': prices[symbol],
                            'value': cost,
                        })
                
                elif shares_to_trade < 0:
                    # Sell
                    shares_to_sell = min(-shares_to_trade, self.positions.get(symbol, (0, 0))[0])
                    proceeds = shares_to_sell * prices[symbol]
                    self.cash += proceeds
                    
                    if symbol in self.positions:
                        new_shares = self.positions[symbol][0] - shares_to_sell
                        if new_shares > 0:
                            self.positions[symbol] = (new_shares, self.positions[symbol][1])
                        else:
                            del self.positions[symbol]
                    
                    self.trades.append({
                        'date': date,
                        'symbol': symbol,
                        'action': 'sell',
                        'shares': shares_to_sell,
                        'price': prices[symbol],
                        'value': proceeds,
                    })
    
    def _calculate_results(self) -> Dict[str, Any]:
        """Calculate backtest results"""
        final_value = self.portfolio_values[-1] if self.portfolio_values else self.initial_capital
        total_return = (final_value / self.initial_capital) - 1
        
        # Calculate daily returns
        returns = pd.Series(self.portfolio_values).pct_change().dropna()
        
        # Calculate metrics
        annualized_return = (1 + total_return) ** (252 / len(self.portfolio_values)) - 1
        volatility = returns.std() * (252 ** 0.5)
        sharpe_ratio = annualized_return / volatility if volatility > 0 else 0
        
        max_dd = max_drawdown(self.portfolio_values)
        
        return {
            'initial_capital': self.initial_capital,
            'final_value': final_value,
            'total_return': total_return,
            'annualized_return': annualized_return,
            'volatility': volatility,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_dd,
            'num_trades': len(self.trades),
            'portfolio_values': self.portfolio_values,
            'timestamps': self.timestamps,
            'trades': self.trades,
        }
    
    def save_results(self, results: Dict[str, Any], output_path: Path):
        """
        Save backtest results to file.
        
        Args:
            results: Backtest results
            output_path: Output file path
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save as JSON
        import json
        
        save_data = {
            'initial_capital': results['initial_capital'],
            'final_value': results['final_value'],
            'total_return': results['total_return'],
            'annualized_return': results['annualized_return'],
            'volatility': results['volatility'],
            'sharpe_ratio': results['sharpe_ratio'],
            'max_drawdown': results['max_drawdown'],
            'num_trades': results['num_trades'],
            'timestamps': results['timestamps'],
            'portfolio_values': results['portfolio_values'],
            'trades': results['trades'],
        }
        
        with open(output_path, 'w') as f:
            json.dump(save_data, f, indent=2, default=str)
        
        logger.info(f"Saved backtest results to {output_path}")
