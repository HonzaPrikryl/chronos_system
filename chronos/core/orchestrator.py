# chronos/core/orchestrator.py

import json
import logging
import os
import pandas as pd
from kafka import KafkaConsumer, KafkaProducer
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from collections import deque
from typing import Optional # <-- PŘIDAT TENTO ŘÁDEK

# Importujeme modely a strategie
from chronos.models.schema import Strategy as StrategyModel
from chronos.strategies.ma_cross import MACrossStrategy

# Nastavení logování
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Načtení proměnných prostředí
load_dotenv()
KAFKA_BROKER_URL = os.getenv('KAFKA_BROKER_URL', 'localhost:9092')
DB_USER = os.getenv("POSTGRES_USER", "chronos_user")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "yoursecurepassword")
DB_NAME = os.getenv("POSTGRES_DB", "chronos_db")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
# Definice Kafka témat
TOPIC_CANDLES = 'market.data.candles.binance.btcusdt.1m'
TOPIC_SIGNALS = 'signals.generated'

# Mapa, která přiřadí název třídy z databáze ke skutečné třídě v kódu
STRATEGY_MAPPING = {
    'MACrossStrategy': MACrossStrategy
}

class Orchestrator:
    def __init__(self):
        self.strategies = {}
        self.kafka_producer = self._create_kafka_producer()
        self.db_session = self._create_db_session()
        
        self.market_history = {}
        self.load_strategies()

    def _create_kafka_producer(self):
        try:
            return KafkaProducer(
                bootstrap_servers=KAFKA_BROKER_URL,
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
        except Exception as e:
            logger.error(f"Failed to create Kafka producer: {e}")
            raise

    def _create_db_session(self):
        engine = create_engine(DATABASE_URL)
        return sessionmaker(bind=engine)()

    def load_strategies(self):
        """Načte aktivní strategie z databáze a vytvoří jejich instance."""
        logger.info("Loading active strategies from database...")
        active_strategies = self.db_session.query(StrategyModel).filter(StrategyModel.is_active == True).all()
        
        for strat_model in active_strategies:
            if strat_model.symbol not in self.market_history:
                self.market_history[strat_model.symbol] = deque(maxlen=50)
                logger.info(f"Initialized market history buffer for symbol {strat_model.symbol}")
            if strat_model.class_name in STRATEGY_MAPPING:
                strategy_class = STRATEGY_MAPPING[strat_model.class_name]
                instance = strategy_class(
                    strategy_id=strat_model.id,
                    symbol=strat_model.symbol,
                    timeframe=strat_model.timeframe,
                    params=strat_model.parameters
                )
                self.strategies[strat_model.id] = instance
                logger.info(f"Loaded strategy '{strat_model.name}' (ID: {strat_model.id})")
            else:
                logger.warning(f"Strategy class '{strat_model.class_name}' not found in STRATEGY_MAPPING.")
        
        if not self.strategies:
            logger.error("No active strategies were loaded. Exiting.")
            exit()

    def calculate_atr(self, symbol: str, period: int = 14) -> Optional[float]:
        """Vypočítá Average True Range (ATR) pro daný symbol."""
        history = self.market_history.get(symbol)
        if not history or len(history) < period + 1:
            return None # Nemáme dost dat

        # Převedeme deque na DataFrame pro snadnější výpočty s pandas
        df = pd.DataFrame(list(history))
        
        # Výpočet True Range (TR)
        high_low = df['high'] - df['low']
        high_close = (df['high'] - df['close'].shift()).abs()
        low_close = (df['low'] - df['close'].shift()).abs()
        
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        
        # Výpočet ATR jako exponenciální klouzavý průměr TR
        atr = tr.ewm(alpha=1/period, adjust=False).mean()
        
        return atr.iloc[-1] # Vrátíme poslední hodnotu ATR

    def run(self):
        """Spustí hlavní smyčku Orchestratoru."""
        logger.info("Orchestrator is running. Waiting for market data...")
        consumer = KafkaConsumer(
            TOPIC_CANDLES,
            bootstrap_servers=KAFKA_BROKER_URL,
            auto_offset_reset='latest',
            group_id='chronos-orchestrator-group',
            value_deserializer=lambda v: json.loads(v.decode('utf-8'))
        )

        for message in consumer:
            candle_data = message.value
            candle_series = pd.Series(candle_data)
            symbol = candle_series['symbol']

            # NOVÉ: Aktualizujeme historii trhu pro výpočet ATR
            if symbol in self.market_history:
                self.market_history[symbol].append(candle_series)
            
            # Projdi všechny načtené strategie a pošli jim svíčku, pokud na ni naslouchají
            for strategy in self.strategies.values():
                if strategy.listens_to(symbol, candle_series['timeframe']):
                    strategy.on_candle(candle_series)
                    signal_instruction = strategy.generate_signal()
                    
                    if signal_instruction:
                        logger.warning(f"INSTRUCTION from Strategy {signal_instruction['strategy_id']}: {signal_instruction}")
                        
                        final_signal = None
                        signal_type = signal_instruction.get('signal_type')

                        # Překlad instrukce na finální signál
                        if signal_type == 'GO_LONG':
                            final_signal = {**signal_instruction, 'side': 'BUY'}
                        elif signal_type == 'GO_SHORT':
                            final_signal = {**signal_instruction, 'side': 'SELL'}
                        
                        if final_signal:
                            del final_signal['signal_type'] # Odstraníme pomocný klíč

                            current_atr = self.calculate_atr(symbol)
                            if current_atr:
                                final_signal['atr'] = current_atr
                                logger.warning(f"FINAL SIGNAL to Risk Manager: {final_signal}")
                                self.kafka_producer.send(TOPIC_SIGNALS, final_signal)
                                self.kafka_producer.flush()
                            else:
                                logger.warning(f"Instruction generated but ATR is not available yet.")

if __name__ == "__main__":
    try:
        orchestrator = Orchestrator()
        orchestrator.run()
    except Exception as e:
        logger.error(f"A critical error occurred in the Orchestrator: {e}", exc_info=True)