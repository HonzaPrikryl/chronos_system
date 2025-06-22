import json
import logging
import os
import datetime
from kafka import KafkaConsumer
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from chronos.models.schema import MarketDataCandle
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

load_dotenv()
KAFKA_BROKER_URL = os.getenv('KAFKA_BROKER_URL', 'localhost:9092')
KAFKA_TOPIC = os.getenv('KAFKA_TOPIC', 'market.data.candles.binance.btcusdt.1m')

DB_USER = os.getenv("POSTGRES_USER", "chronos_user")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "yoursecurepassword")
DB_NAME = os.getenv("POSTGRES_DB", "chronos_db")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"    

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

def create_kafka_consumer():
    try:
        consumer = KafkaConsumer(
            KAFKA_TOPIC,
            bootstrap_servers=KAFKA_BROKER_URL,
            auto_offset_reset='earliest',
            group_id='chronos-db-writer-group',
            value_deserializer=lambda v: json.loads(v.decode('utf-8'))
        )
        logging.info(f"Successfully connected to Kafka and subscribed to topic '{KAFKA_TOPIC}'")
        return consumer
    except Exception as e:
        logging.error(f"Failed to connect to Kafka: {e}")
        return None

def run_writer():
    consumer = create_kafka_consumer()
    if not consumer:
        return

    logging.info("DB Writer is running and waiting for messages...")
    
    session = Session()
    try:
        for message in consumer:
            data = message.value
            logging.info(f"Received message: {data['symbol']} @ {data['close']}")

            candle = MarketDataCandle(
                time=datetime.datetime.fromtimestamp(data['time'] / 1000.0, tz=datetime.timezone.utc),
                exchange=data['exchange'],
                symbol=data['symbol'],
                timeframe=data['timeframe'],
                open=data['open'],
                high=data['high'],
                low=data['low'],
                close=data['close'],
                volume=data['volume']
            )
            
            session.add(candle)
            session.commit()
            logging.info(f"Successfully wrote candle for {candle.time} to DB.")

    except KeyboardInterrupt:
        logging.info("Shutting down DB writer...")
    except Exception as e:
        logging.error(f"An error occurred in the writer loop: {e}")
        session.rollback()
    finally:
        session.close()
        consumer.close()
        logging.info("DB session and Kafka consumer closed.")


if __name__ == "__main__":
    run_writer()