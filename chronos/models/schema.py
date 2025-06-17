# chronos/models/schema.py

import datetime
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Float,
    DateTime,
    Boolean,
    JSON,
    MetaData,
)
from sqlalchemy.orm import declarative_base

# Vytvoření deklarativní základny, od které budou dědit všechny modely
Base = declarative_base()

class Strategy(Base):
    """
    Tabulka pro ukládání konfigurací jednotlivých strategií.
    Chronos bude tuto tabulku číst, aby věděl, které strategie má spouštět.
    """
    __tablename__ = "strategies"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False, comment="Unikátní název instance strategie, např. MACD_Cross_ETHUSDT_1h")
    class_name = Column(String(100), nullable=False, comment="Název třídy v kódu, např. MACDCrossover")
    symbol = Column(String(20), nullable=False, comment="Symbol, na kterém strategie operuje, např. BTCUSDT")
    timeframe = Column(String(10), nullable=False, comment="Časový rámec, který strategie sleduje, např. 1m, 1h")
    parameters = Column(JSON, comment="Parametry strategie ve formátu JSON, např. {'fast_ma': 12}")
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    def __repr__(self):
        return f"<Strategy(name='{self.name}', symbol='{self.symbol}', is_active={self.is_active})>"

class Trade(Base):
    """
    Tabulka pro záznamy o všech provedených obchodech.
    Toto je klíčový zdroj dat pro analýzu výkonnosti.
    """
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True)
    strategy_id = Column(Integer, nullable=False, index=True) # Zde by měl být cizí klíč na strategies.id
    exchange = Column(String(50), nullable=False)
    symbol = Column(String(20), nullable=False, index=True)
    exchange_order_id = Column(String(255), unique=True)
    side = Column(String(4), nullable=False)  # 'BUY' nebo 'SELL'
    amount = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    fee = Column(Float)
    fee_currency = Column(String(10))
    executed_at = Column(DateTime, nullable=False, index=True)

    def __repr__(self):
        return f"<Trade(symbol='{self.symbol}', side='{self.side}', amount={self.amount}, price={self.price})>"

class MarketDataCandle(Base):
    """
    Tabulka pro ukládání historických i real-time svíčkových dat.
    Tato tabulka bude převedena na TimescaleDB hypertable pro efektivní práci s časovými řadami.
    """
    __tablename__ = "market_data_candles"
    
    time = Column(DateTime, primary_key=True)
    exchange = Column(String(50), primary_key=True)
    symbol = Column(String(20), primary_key=True)
    timeframe = Column(String(10), primary_key=True)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)

    def __repr__(self):
        return f"<Candle({self.symbol} {self.time} O:{self.open} C:{self.close})>"

class PortfolioHistory(Base):
    """
    Tabulka pro ukládání historického vývoje hodnoty portfolia (equity).
    Každý záznam reprezentuje stav portfolia po uzavření obchodu.
    """
    __tablename__ = "portfolio_history"

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    total_equity = Column(Float, nullable=False)
    unrealized_pnl = Column(Float, nullable=False)
    realized_pnl = Column(Float, nullable=False)
    trade_id = Column(Integer) # Volitelný odkaz na obchod, který způsobil změnu

    def __repr__(self):
        return f"<PortfolioHistory(time='{self.timestamp}', equity={self.total_equity})>"

