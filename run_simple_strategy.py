import json
import logging
import os
import pandas as pd
from kafka import KafkaConsumer
from dotenv import load_dotenv

from chronos.strategies.ma_cross import MACrossStrategy

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

load_dotenv()
KAFKA_BROKER_URL = os.getenv('KAFKA_BROKER_URL', 'localhost:9092')
KAFKA_TOPIC = os.getenv('KAFKA_TOPIC', 'market.data.candles.binance.btcusdt.1m')

def run_strategy_on_live_data():
    strategy_params = {'fast_ma': 5, 'slow_ma': 10}
    strategy = MACrossStrategy(strategy_id=1, symbol='BTCUSDT', params=strategy_params)
    logging.info(f"Starting strategy '{type(strategy).__name__}' on symbol '{strategy.symbol}' with params: {strategy_params}")

    try:
        consumer = KafkaConsumer(
            KAFKA_TOPIC,
            bootstrap_servers=KAFKA_BROKER_URL,
            auto_offset_reset='latest',
            group_id='chronos-strategy-runner-group',
            value_deserializer=lambda v: json.loads(v.decode('utf-8'))
        )
        logging.info(f"Successfully connected to Kafka and subscribed to topic '{KAFKA_TOPIC}'")
    except Exception as e:
        logging.error(f"Failed to connect to Kafka: {e}")
        return

    logging.info("Strategy runner is waiting for new candles...")
    for message in consumer:
        candle_data = message.value
        candle_series = pd.Series(candle_data)
        strategy.on_candle(candle_series)
        
        signal = strategy.generate_signal()
        
        if signal:
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