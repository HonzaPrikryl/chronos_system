from typing import Dict, Any, Optional
import pandas as pd
from collections import deque
from .base import BaseStrategy

class MACrossStrategy(BaseStrategy):
    """
    Strategie založená na křížení dvou jednoduchých klouzavých průměrů (SMA).
    """
    def __init__(self, strategy_id: int, symbol: str, timeframe: str, params: Dict[str, Any]):
        super().__init__(strategy_id, symbol, params)
        self.timeframe = timeframe
        self.fast_ma_period = self.params.get('fast_ma', 10)
        self.slow_ma_period = self.params.get('slow_ma', 20)
        self.history_length = self.slow_ma_period 
        self.close_prices = deque(maxlen=self.history_length)
        self.last_fast_ma = None
        self.last_slow_ma = None
        self.state = 'FLAT'

    def listens_to(self, symbol: str, timeframe: str) -> bool:
        """Vrátí True, pokud tato strategie naslouchá na daném trhu."""
        return self.symbol == symbol and self.timeframe == timeframe

    def on_candle(self, candle: pd.Series):
        """Přidá zavírací cenu nové svíčky do historie."""
        close_price = candle['close']
        self.close_prices.append(close_price)
        print(f"[{self.strategy_id}:{self.symbol}] Received candle. Close: {close_price}. History: {len(self.close_prices)}/{self.history_length}")

    def generate_signal(self) -> Optional[Dict[str, Any]]:
        """Zkontroluje, zda došlo ke křížení klouzavých průměrů."""
        if len(self.close_prices) < self.history_length:
            return None

        current_fast_ma = sum(list(self.close_prices)[-self.fast_ma_period:]) / self.fast_ma_period
        current_slow_ma = sum(self.close_prices) / self.history_length
        print(f"[{self.strategy_id}:{self.symbol}] FastMA: {current_fast_ma:.2f}, SlowMA: {current_slow_ma:.2f}, State: {self.state}")

        signal_type = None
        
        is_bullish_cross = self.last_fast_ma is not None and self.last_fast_ma <= self.last_slow_ma and current_fast_ma > current_slow_ma
        is_bearish_cross = self.last_fast_ma is not None and self.last_fast_ma >= self.last_slow_ma and current_fast_ma < current_slow_ma

        if self.state == 'FLAT':
            if is_bullish_cross:
                signal_type = 'GO_LONG'
                self.state = 'LONG'
            elif is_bearish_cross:
                signal_type = 'GO_SHORT'
                self.state = 'SHORT'
        
        elif self.state == 'LONG':
            if is_bearish_cross:
                signal_type = 'GO_SHORT'
                self.state = 'SHORT'
        
        elif self.state == 'SHORT':
            if is_bullish_cross:
                signal_type = 'GO_LONG'
                self.state = 'LONG'

        self.last_fast_ma = current_fast_ma
        self.last_slow_ma = current_slow_ma
        
        if signal_type:
            return {
                'signal_type': signal_type,
                'strategy_id': self.strategy_id,
                'symbol': self.symbol,
                'price_at_signal': self.close_prices[-1]
            }
        
        return None