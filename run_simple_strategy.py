# run_simple_strategy.py

import json
import logging
import os
import pandas as pd
from kafka import KafkaConsumer
from dotenv import load_dotenv

# Importujeme naši konkrétní strategii
from chronos.strategies.ma_cross import MACrossStrategy

# Nastavení logování
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Načtení proměnných
load_dotenv()
KAFKA_BROKER_URL = os.getenv('KAFKA_BROKER_URL', 'localhost:9092')
KAFKA_TOPIC = os.getenv('KAFKA_TOPIC', 'market.data.candles.binance.btcusdt.1m')

def run_strategy_on_live_data():
    """
    Hlavní funkce, která poslouchá Kafku a aplikuje na data strategii.
    """
    # 1. Nastavení strategie
    strategy_params = {'fast_ma': 5, 'slow_ma': 10} # Použijeme kratší periody pro rychlejší signály
    strategy = MACrossStrategy(strategy_id=1, symbol='BTCUSDT', params=strategy_params)
    logging.info(f"Starting strategy '{type(strategy).__name__}' on symbol '{strategy.symbol}' with params: {strategy_params}")

    # 2. Nastavení Kafka konzumenta
    try:
        consumer = KafkaConsumer(
            KAFKA_TOPIC,
            bootstrap_servers=KAFKA_BROKER_URL,
            auto_offset_reset='latest', # Chceme jen nejnovější data, ne starou historii
            group_id='chronos-strategy-runner-group',
            value_deserializer=lambda v: json.loads(v.decode('utf-8'))
        )
        logging.info(f"Successfully connected to Kafka and subscribed to topic '{KAFKA_TOPIC}'")
    except Exception as e:
        logging.error(f"Failed to connect to Kafka: {e}")
        return

    # 3. Hlavní smyčka pro zpracování dat
    logging.info("Strategy runner is waiting for new candles...")
    for message in consumer:
        candle_data = message.value
        
        # Převod na pandas Series pro snadnější práci
        candle_series = pd.Series(candle_data)
        
        # "Nakrmíme" strategii novou svíčkou
        strategy.on_candle(candle_series)
        
        # Zeptáme se strategie, zda chce vygenerovat signál
        signal = strategy.generate_signal()
        
        if signal:
            # Našli jsme signál!
            logging.warning("="*50)
            logging.warning(f"  SIGNAL DETECTED!  ")
            logging.warning(f"  Strategy ID: {strategy.strategy_id}")
            logging.warning(f"  Symbol: {strategy.symbol}")
            logging.warning(f"  Side: {signal['side']}")
            logging.warning(f"  Reason: {signal['reason']}")
            logging.warning(f"  Candle Close Price: {candle_series['close']}")
            logging.warning("="*50)

if __name__ == "__main__":
    try:
        run_strategy_on_live_data()
    except KeyboardInterrupt:
        logging.info("Strategy runner shut down by user.")