# chronos/risk_management/manager.py

import json
import logging
import os
from kafka import KafkaConsumer, KafkaProducer
from dotenv import load_dotenv

# Nastavení logování
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Načtení proměnných prostředí
load_dotenv()
KAFKA_BROKER_URL = os.getenv('KAFKA_BROKER_URL', 'localhost:9092')

# Definice Kafka témat
TOPIC_SIGNALS = 'signals.generated'
TOPIC_ORDERS = 'orders.to_execute'

class RiskManager:
    def __init__(self):
        self.total_equity = 10000.0  # $10,000 celkový kapitál (prozatím fixní)
        self.risk_per_trade_percentage = 0.01 # Riskujeme 1% kapitálu na obchod
        self.stop_loss_atr_multiplier = 2.0 # Stop loss umístíme na 2 * ATR
        
        self.kafka_producer = KafkaProducer(
            bootstrap_servers=KAFKA_BROKER_URL,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        self.kafka_consumer = KafkaConsumer(
            TOPIC_SIGNALS,
            bootstrap_servers=KAFKA_BROKER_URL,
            auto_offset_reset='latest',
            group_id='chronos-risk-manager-group',
            value_deserializer=lambda v: json.loads(v.decode('utf-8'))
        )
        logger.info("Risk Manager initialized and connected to Kafka.")

    def calculate_position_size(self, signal: dict) -> float:
        """
        Vypočítá velikost pozice na základě ATR a řízení rizika.
        """
        atr = signal.get('atr')
        if not atr:
            logger.warning(f"Cannot calculate position size for signal {signal.get('strategy_id')}: ATR is missing.")
            return 0.0

        # 1. Kolik USD jsme ochotni riskovat na tento obchod?
        risk_amount_usd = self.total_equity * self.risk_per_trade_percentage
        
        # 2. Jak daleko v USD je náš stop loss od vstupní ceny?
        stop_loss_distance_usd = self.stop_loss_atr_multiplier * atr
        
        if stop_loss_distance_usd == 0:
            logger.warning("Cannot calculate position size: ATR is zero.")
            return 0.0
            
        # 3. Jakou velikost pozice (v kryptoměně) si můžeme dovolit?
        position_size = risk_amount_usd / stop_loss_distance_usd
        
        logger.info(f"Position size calculation: Risk Amount ${risk_amount_usd:.2f} / Stop Distance ${stop_loss_distance_usd:.2f} = {position_size:.4f} {signal.get('symbol')}")
        
        return position_size

    def run(self):
        """Spustí hlavní smyčku Risk Managera."""
        logger.info("Risk Manager is running. Waiting for signals...")
        
        for message in self.kafka_consumer:
            signal = message.value
            logger.info(f"Received signal: {signal}")
            
            # Výpočet velikosti pozice se nyní děje pomocí nové, chytřejší metody
            position_size = self.calculate_position_size(signal)
            
            if position_size > 0:
                # Ořízneme na rozumný počet desetinných míst (např. 5 pro BTC)
                quantity = round(position_size, 5)

                order = {
                    'strategy_id': signal['strategy_id'],
                    'symbol': signal['symbol'],
                    'side': signal['side'],
                    'quantity': quantity,
                    'order_type': 'MARKET',
                    'signal_price': signal['price_at_signal']
                }
                
                logger.warning(f"Generated Order with ATR-based size: {order}")
                
                self.kafka_producer.send(TOPIC_ORDERS, order)
                self.kafka_producer.flush()
            else:
                logger.warning(f"Signal for symbol {signal.get('symbol')} ignored (position size is zero or could not be calculated).")


if __name__ == "__main__":
    try:
        risk_manager = RiskManager()
        risk_manager.run()
    except Exception as e:
        logger.error(f"A critical error occurred in the Risk Manager: {e}", exc_info=True)