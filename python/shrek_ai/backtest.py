"""
Backtesting system for Shrek using the actual decision pipeline.

Derives proxy fundamental signals from price data to feed the mathematical
scoring and decision functions (entry, trim, sell, position sizing).
"""

from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from loguru import logger

from .alpaca_data import AlpacaDataSource
from .math import (
    expected_return,
    downside,
    upside,
    upside_downside_ratio,
    timing_score,
    risk_penalty,
    shrek_score,
    entry_decision,
    trim_decision,
    sell_decision,
    forward_expected_return,
    starter_position_size,
    trim_amount,
    max_drawdown,
)


def _compute_price_signals(prices: pd.Series) -> Dict[str, float]:
    """Compute price-derived proxy signals for Shrek scoring."""
    if len(prices) < 50:
        return {}

    current = float(prices.iloc[-1])
    sma50 = float(prices.iloc[-50:].mean())
    sma200 = float(prices.iloc[-200:].mean()) if len(prices) >= 200 else sma50
    high_52w = float(prices.max())
    low_52w = float(prices.min())
    returns = prices.pct_change().dropna()
    vol_20d = float(returns.iloc[-20:].std() * np.sqrt(252)) if len(returns) >= 20 else 0.25

    # Valuation scenarios from price history
    bear = max(low_52w, current - 2 * vol_20d * current)
    base = sma50
    bull = high_52w

    # Expected return from scenario blend
    exp_ret = expected_return(bear, base, bull, current, 0.30, 0.50, 0.20)

    # Upside / downside
    up = upside(base, current)
    down = downside(bear, current)
    ud = upside_downside_ratio(up, down)

    # Quality proxy: trend strength (0 to 1)
    if sma200 > 0:
        trend_ratio = sma50 / sma200
        quality = max(0.0, min(1.0, 0.5 + (trend_ratio - 1.0) * 2.0))
    else:
        quality = 0.5

    # Risk penalty proxy: volatility
    risk_pen = min(1.0, vol_20d * 2.0)

    # Timing proxy
    trend_200d = 1.0 if current > sma200 else 0.0
    trend_50d = 1.0 if current > sma50 else 0.0
    pullback = 1.0 if current >= high_52w * 0.95 else 0.5 if current >= high_52w * 0.90 else 0.0
    volume_conf = 0.5  # No volume data in price-only backtest
    timing = timing_score(
        trend_200d=trend_200d,
        trend_50d=trend_50d,
        relative_strength=0.5,
        pullback_quality=pullback,
        volume_confirmation=volume_conf,
    )

    # Thesis probability: anchored to 0.70, adjusted by trend
    thesis_prob = 0.70
    if trend_200d > 0.5 and trend_50d > 0.5:
        thesis_prob = min(0.90, thesis_prob + 0.10)
    elif trend_200d < 0.5:
        thesis_prob = max(0.50, thesis_prob - 0.10)

    # Shrek score
    expected_ret_score = max(0.0, min(1.0, (exp_ret - 0.05) / 0.35))
    shrek = shrek_score(
        expected_return_score=expected_ret_score,
        quality=quality,
        revision=0.5,  # Neutral revision in price-only backtest
        timing=timing,
        risk_penalty=risk_pen,
        secular_conviction=0.0,
    )

    return {
        'current_price': current,
        'bear_value': bear,
        'base_value': base,
        'bull_value': bull,
        'expected_return': exp_ret,
        'upside': up,
        'downside': down,
        'upside_downside': ud,
        'quality': quality,
        'risk_penalty': risk_pen,
        'timing': timing,
        'thesis_probability': thesis_prob,
        'shrek_score': shrek,
        'volatility': vol_20d,
    }


class Backtest:
    """Backtesting engine for Shrek using the real decision pipeline."""

    def __init__(
        self,
        start_date: str,
        end_date: str,
        initial_capital: float = 100000.0,
        max_single_position_pct: float = 0.20,
        starter_position_pct: float = 0.05,
        normal_position_pct: float = 0.10,
        target_cash_reserve_pct: float = 0.15,
        limit_buy_discount_bps: int = 20,
        limit_sell_premium_bps: int = 10,
    ):
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        self.max_single_position_pct = max_single_position_pct
        self.starter_position_pct = starter_position_pct
        self.normal_position_pct = normal_position_pct
        self.target_cash_reserve_pct = target_cash_reserve_pct
        self.limit_buy_discount_bps = limit_buy_discount_bps
        self.limit_sell_premium_bps = limit_sell_premium_bps
        self.alpaca = AlpacaDataSource()

        # Portfolio state
        self.cash = initial_capital
        self.positions: Dict[str, Dict[str, Any]] = {}
        self.trades: List[Dict[str, Any]] = []
        self.portfolio_values: List[float] = []
        self.timestamps: List[str] = []

        # Pre-fetch all historical price data
        self.price_history: Dict[str, pd.Series] = {}

    def run_backtest(
        self,
        symbols: List[str],
        rebalance_frequency: str = 'monthly',
    ) -> Dict[str, Any]:
        """
        Run backtest over the specified period using the Shrek decision pipeline.

        Args:
            symbols: List of symbols to trade
            rebalance_frequency: Rebalancing frequency (daily, weekly, monthly)

        Returns:
            Backtest results
        """
        logger.info(f"Running backtest from {self.start_date} to {self.end_date}")

        # Pre-fetch price history for all symbols
        for symbol in symbols:
            try:
                bars = self.alpaca.get_bars(
                    symbol,
                    timeframe='1Day',
                    start=datetime.fromisoformat(self.start_date) - timedelta(days=365),
                    end=datetime.fromisoformat(self.end_date),
                )
                if not bars.empty:
                    self.price_history[symbol] = bars['close']
            except Exception as e:
                logger.warning(f"Failed to fetch history for {symbol}: {e}")

        # Get trading calendar
        calendar = self.alpaca.get_calendar(
            start=datetime.fromisoformat(self.start_date),
            end=datetime.fromisoformat(self.end_date),
        )
        trading_days = [str(d['date']) for d in calendar]
        logger.info(f"Found {len(trading_days)} trading days for {len(self.price_history)} symbols")

        # Simulate day by day
        for date in trading_days:
            self._simulate_day(date, symbols, rebalance_frequency)

        results = self._calculate_results()
        logger.info(f"Backtest complete. Final value: ${results['final_value']:,.2f}")
        return results

    def _simulate_day(self, date: str, symbols: List[str], rebalance_frequency: str):
        """Simulate a single trading day."""
        prices = {}
        for symbol in symbols:
            hist = self.price_history.get(symbol)
            if hist is None:
                continue
            mask = hist.index.strftime('%Y-%m-%d') == date
            if mask.any():
                prices[symbol] = float(hist[mask].iloc[-1])

        # Mark-to-market portfolio
        portfolio_value = self.cash
        for symbol, pos in self.positions.items():
            if symbol in prices:
                portfolio_value += pos['shares'] * prices[symbol]

        self.portfolio_values.append(portfolio_value)
        self.timestamps.append(date)

        # Rebalance on schedule
        if self._should_rebalance(date, rebalance_frequency):
            self._rebalance(date, prices, symbols)

    def _should_rebalance(self, date: str, frequency: str) -> bool:
        """Check if should rebalance on this date."""
        dt = datetime.fromisoformat(date)
        if frequency == 'daily':
            return True
        elif frequency == 'weekly':
            return dt.weekday() == 0
        elif frequency == 'monthly':
            return dt.day == 1
        return False

    def _rebalance(self, date: str, prices: Dict[str, float], symbols: List[str]):
        """Run Shrek entry/trim/exit decisions on each symbol."""
        equity = self.portfolio_values[-1] if self.portfolio_values else self.initial_capital

        # --- EXIT DECISIONS (existing positions first) ---
        for symbol in list(self.positions.keys()):
            if symbol not in prices:
                continue

            pos = self.positions[symbol]
            current_price = prices[symbol]
            hist = self.price_history.get(symbol)
            if hist is None or len(hist) < 50:
                continue

            # Slice history up to current date
            mask = hist.index.strftime('%Y-%m-%d') <= date
            past_prices = hist[mask]
            if len(past_prices) < 50:
                continue

            signals = _compute_price_signals(past_prices)
            if not signals:
                continue

            # Forward expected return for trim/sell logic
            fwd_return = forward_expected_return(
                bear_value=signals['bear_value'],
                base_value=signals['base_value'],
                bull_value=signals['bull_value'],
                current_price=current_price,
                p_bear=0.30,
                p_base=0.50,
                p_bull=0.20,
            )

            position_value = pos['shares'] * current_price
            position_pct = position_value / equity if equity > 0 else 0.0
            position_gain = (current_price / pos['entry_price']) - 1 if pos['entry_price'] > 0 else 0.0

            # Check sell
            should_sell, sell_reason = sell_decision(
                forward_return=fwd_return,
                thesis_probability=signals['thesis_probability'],
                shrek_score=signals['shrek_score'],
                risk_penalty=signals['risk_penalty'],
                thesis_break_events=[],
            )

            if should_sell:
                self._execute_sell(date, symbol, current_price, pos['shares'], sell_reason)
                continue

            # Check trim
            should_trim, trim_reason = trim_decision(
                forward_return=fwd_return,
                current_price=current_price,
                base_value=signals['base_value'],
                upside_downside=signals['upside_downside'],
                current_position_pct=position_pct,
                max_single_position_pct=self.max_single_position_pct,
                position_gain=position_gain,
                risk_penalty=signals['risk_penalty'],
            )

            if should_trim:
                trim_notional = trim_amount(position_value)
                shares_to_trim = int(trim_notional / current_price)
                shares_to_trim = min(shares_to_trim, pos['shares'])
                if shares_to_trim > 0:
                    self._execute_sell(date, symbol, current_price, shares_to_trim, trim_reason, is_trim=True)

        # --- ENTRY DECISIONS (for symbols without a position) ---
        for symbol in symbols:
            if symbol in self.positions or symbol not in prices:
                continue

            hist = self.price_history.get(symbol)
            if hist is None or len(hist) < 50:
                continue

            mask = hist.index.strftime('%Y-%m-%d') <= date
            past_prices = hist[mask]
            if len(past_prices) < 50:
                continue

            signals = _compute_price_signals(past_prices)
            if not signals:
                continue

            current_price = prices[symbol]

            decision, reason = entry_decision(
                position_exists=False,
                shrek_score=signals['shrek_score'],
                expected_return=signals['expected_return'],
                upside_downside=signals['upside_downside'],
                quality=signals['quality'],
                risk_penalty=signals['risk_penalty'],
                thesis_probability=signals['thesis_probability'],
                timing=signals['timing'],
                is_speculative=False,
                secular_conviction=0.0,
                narrative_conviction=0.0,
            )

            if decision in ('BUY_STARTER', 'CONVICTION_BUY'):
                # Simulate limit order fill at close price with discount
                fill_price = current_price * (1 - self.limit_buy_discount_bps / 10000)
                notional = starter_position_size(
                    equity=equity,
                    starter_position_pct=self.starter_position_pct,
                    expected_return=signals['expected_return'],
                    quality=signals['quality'],
                    risk_penalty=signals['risk_penalty'],
                    thesis_probability=signals['thesis_probability'],
                    upside_downside=signals['upside_downside'],
                    volatility=signals['volatility'],
                    max_single_position_pct=self.max_single_position_pct,
                )

                # Respect cash reserve target
                max_cash_to_use = self.cash - (equity * self.target_cash_reserve_pct)
                notional = min(notional, max(0, max_cash_to_use))

                if notional >= 1.0:
                    shares = int(notional / fill_price)
                    cost = shares * fill_price
                    if cost <= self.cash and shares > 0:
                        self.cash -= cost
                        self.positions[symbol] = {
                            'shares': shares,
                            'entry_price': fill_price,
                            'entry_date': date,
                        }
                        self.trades.append({
                            'date': date,
                            'symbol': symbol,
                            'action': 'buy',
                            'shares': shares,
                            'price': fill_price,
                            'value': cost,
                            'reason': reason,
                        })
                        logger.debug(f"Bought {shares} {symbol} @ ${fill_price:.2f}: {reason}")

    def _execute_sell(
        self,
        date: str,
        symbol: str,
        price: float,
        shares: int,
        reason: str,
        is_trim: bool = False,
    ):
        """Execute a sell/trade."""
        pos = self.positions.get(symbol)
        if pos is None or shares <= 0:
            return

        # Simulate limit order fill at close price with premium
        fill_price = price * (1 + self.limit_sell_premium_bps / 10000)
        shares = min(shares, pos['shares'])
        proceeds = shares * fill_price
        self.cash += proceeds

        pos['shares'] -= shares
        if pos['shares'] <= 0:
            del self.positions[symbol]

        self.trades.append({
            'date': date,
            'symbol': symbol,
            'action': 'trim' if is_trim else 'sell',
            'shares': shares,
            'price': fill_price,
            'value': proceeds,
            'reason': reason,
        })
        logger.debug(f"Sold {shares} {symbol} @ ${fill_price:.2f}: {reason}")

    def _calculate_results(self) -> Dict[str, Any]:
        """Calculate backtest performance metrics."""
        final_value = self.portfolio_values[-1] if self.portfolio_values else self.initial_capital
        total_return = (final_value / self.initial_capital) - 1

        returns = pd.Series(self.portfolio_values).pct_change().dropna()
        n_days = len(self.portfolio_values)
        annualized_return = (1 + total_return) ** (252 / max(1, n_days)) - 1
        volatility = returns.std() * (252 ** 0.5) if len(returns) > 1 else 0.0
        sharpe = annualized_return / volatility if volatility > 0 else 0.0
        max_dd = max_drawdown(self.portfolio_values)

        # Win rate
        trades_df = pd.DataFrame(self.trades)
        win_rate = 0.0
        if not trades_df.empty and 'action' in trades_df.columns:
            sells = trades_df[trades_df['action'].isin(['sell', 'trim'])]
            if not sells.empty:
                # Approximate: count sells with positive value vs buy value
                # Backtest doesn't track cost basis per lot, so we skip detailed P&L
                pass

        return {
            'initial_capital': self.initial_capital,
            'final_value': final_value,
            'total_return': total_return,
            'annualized_return': annualized_return,
            'volatility': volatility,
            'sharpe_ratio': sharpe,
            'max_drawdown': max_dd,
            'num_trades': len(self.trades),
            'num_buys': len([t for t in self.trades if t['action'] == 'buy']),
            'num_sells': len([t for t in self.trades if t['action'] == 'sell']),
            'num_trims': len([t for t in self.trades if t['action'] == 'trim']),
            'portfolio_values': self.portfolio_values,
            'timestamps': self.timestamps,
            'trades': self.trades,
        }

    def save_results(self, results: Dict[str, Any], output_path: Path):
        """Save backtest results to JSON."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
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
            'num_buys': results['num_buys'],
            'num_sells': results['num_sells'],
            'num_trims': results['num_trims'],
            'timestamps': results['timestamps'],
            'portfolio_values': results['portfolio_values'],
            'trades': results['trades'],
        }

        with open(output_path, 'w') as f:
            json.dump(save_data, f, indent=2, default=str)

        logger.info(f"Saved backtest results to {output_path}")
