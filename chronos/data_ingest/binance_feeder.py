# chronos/data_ingest/binance_feeder.py

import asyncio
import websockets
import json
import logging
import os
from kafka import KafkaProducer

# Nastavení logování
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Konfigurace z proměnných prostředí
KAFKA_BROKER_URL = os.getenv('KAFKA_BROKER_URL', 'localhost:9092')
KAFKA_TOPIC = os.getenv('KAFKA_TOPIC', 'market.data.candles.binance.btcusdt.1m')
BINANCE_WS_URL = "wss://stream.binance.com:9443/ws/btcusdt@kline_1m"

def create_kafka_producer():
    """Vytvoří a vrátí instanci Kafka producenta."""
    try:
        producer = KafkaProducer(
            bootstrap_servers=KAFKA_BROKER_URL,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        logging.info(f"Successfully connected to Kafka Broker at {KAFKA_BROKER_URL}")
        return producer
    except Exception as e:
        logging.error(f"Failed to connect to Kafka: {e}")
        return None

async def binance_websocket_listener(producer):
    """Naslouchá na Binance WebSocketu a posílá data do Kafky."""
    logging.info(f"Connecting to Binance WebSocket: {BINANCE_WS_URL}")
    async for websocket in websockets.connect(BINANCE_WS_URL):
        try:
            async for message in websocket:
                data = json.loads(message)
                
                # Zprávy o pingu/pongu a jiné ignorujeme, zajímá nás 'k' (kline)
                if 'e' in data and data['e'] == 'kline':
                    kline = data['k']
                    
                    # Zpracováváme pouze uzavřené svíčky
                    if kline['x']:
                        normalized_data = {
                            "time": kline['T'],  # Čas v milisekundách
                            "symbol": kline['s'],
                            "open": float(kline['o']),
                            "high": float(kline['h']),
                            "low": float(kline['l']),
                            "close": float(kline['c']),
                            "volume": float(kline['v']),
                            "exchange": "binance",
                            "timeframe": "1m"
                        }
                        
                        # Odeslání do Kafky
                        producer.send(KAFKA_TOPIC, value=normalized_data)
                        logging.info(f"Sent {kline['s']} kline for {kline['T']} to Kafka.")
        except websockets.ConnectionClosed as e:
            logging.error(f"Binance WebSocket connection closed: {e}. Reconnecting...")
            await asyncio.sleep(5) # Počkat 5 sekund před pokusem o nové připojení
        except Exception as e:
            logging.error(f"An unexpected error occurred: {e}. Reconnecting...")
            await asyncio.sleep(5)


if __name__ == "__main__":
    kafka_producer = create_kafka_producer()
    if kafka_producer:
        try:
            asyncio.run(binance_websocket_listener(kafka_producer))
        except KeyboardInterrupt:
            logging.info("Shutting down Binance feeder...")
        finally:
            kafka_producer.flush()
            kafka_producer.close()
            logging.info("Kafka producer closed.")