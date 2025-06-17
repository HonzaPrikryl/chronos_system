from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import pandas as pd

class BaseStrategy(ABC):
    """
    Abstraktní základní třída pro všechny obchodní strategie.
    Definuje rozhraní, které musí každá strategie implementovat.
    """
    def __init__(self, strategy_id: int, symbol: str, params: Dict[str, Any]):
        """
        Inicializace strategie.
        
        :param strategy_id: Unikátní ID strategie z databáze.
        :param symbol: Symbol, na kterém strategie operuje (např. 'BTCUSDT').
        :param params: Slovník s parametry strategie (např. {'fast_ma': 10, 'slow_ma': 20}).
        """
        self.strategy_id = strategy_id
        self.symbol = symbol
        self.params = params

    @abstractmethod
    def on_candle(self, candle: pd.Series):
        """
        Metoda volaná pro každou novou svíčku. Zde probíhá hlavní logika
        výpočtu indikátorů a aktualizace stavu strategie.
        
        :param candle: Nová svíčka jako pandas Series (s indexy 'time', 'open', 'high', 'low', 'close', 'volume').
        """
        pass

    @abstractmethod
    def generate_signal(self) -> Optional[Dict[str, Any]]:
        """
        Na základě vnitřního stavu generuje nebo negeneruje signál.
        Tato metoda je volána po `on_candle`.
        
        :return: Slovník se signálem nebo None.
                 Příklad výstupu: {'side': 'BUY', 'reason': 'MA 10 crossed above MA 20'}
        """
        pass