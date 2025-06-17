# chronos/execution/simulator.py

import json
import logging
import os
import uuid
import datetime
from kafka import KafkaConsumer
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from chronos.models.schema import Trade, PortfolioHistory

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

# Definice Kafka tématu
TOPIC_ORDERS = 'orders.to_execute'

class ExecutionSimulator:
    def __init__(self):
        self.kafka_consumer = KafkaConsumer(
            TOPIC_ORDERS,
            bootstrap_servers=KAFKA_BROKER_URL,
            auto_offset_reset='latest',
            group_id='chronos-execution-simulator-group',
            value_deserializer=lambda v: json.loads(v.decode('utf-8'))
        )
        engine = create_engine(DATABASE_URL)
        self.db_session = sessionmaker(bind=engine)()

        self.equity = 10000.0  # Počáteční kapitál, stejný jako v Risk Manageru
        self.realized_pnl = 0.0
        # Slovník pro sledování pozic, klíč je symbol (např. 'BTCUSDT')
        self.positions = {} 
        
        logger.info(f"Execution Simulator initialized with starting equity ${self.equity:.2f}")
        # Zapíšeme počáteční stav portfolia do historie
        self._log_portfolio_state(datetime.datetime.now(datetime.timezone.utc))

    def _log_portfolio_state(self, timestamp: datetime.datetime, trade_id: int = None):
        """Uloží aktuální stav portfolia do databáze."""
        # TODO: V budoucnu počítat nerealizovaný P&L na základě aktuální ceny trhu
        unrealized_pnl = 0.0 
        
        history_record = PortfolioHistory(
            timestamp=timestamp,
            total_equity=self.equity,
            unrealized_pnl=unrealized_pnl,
            realized_pnl=self.realized_pnl,
            trade_id=trade_id
        )
        self.db_session.add(history_record)
        self.db_session.commit()
        logger.info(f"Portfolio state logged. Equity: ${self.equity:.2f}")

    def run(self):
        """Spustí hlavní smyčku simulátoru."""
        logger.info("Execution Simulator is running. Waiting for orders to execute...")

        for message in self.kafka_consumer:
            order = message.value
            logger.warning("="*50)
            logger.warning(f"  SIMULATING EXECUTION of order: {order}")
            
            # Simulace slippage a poplatků
            price = order['signal_price']
            slippage = 0.0005
            executed_price = price * (1 + slippage) if order['side'] == 'BUY' else price * (1 - slippage)
            fee = order['quantity'] * executed_price * 0.001
            
            # Aktualizace equity o poplatek
            self.equity -= fee

            # Zpracování logiky pozic
            symbol = order['symbol']
            side = order['side']
            quantity = order['quantity']
            
            current_position = self.positions.get(symbol)
            trade_pnl = 0.0

            # Zjištění, zda je obchod opačný k současné pozici
            is_closing_trade = (current_position and 
                               ((side == 'SELL' and current_position['quantity'] > 0) or 
                                (side == 'BUY' and current_position['quantity'] < 0)))

            if is_closing_trade:
                # 1. UZAVŘENÍ A PŘEKLOPENÍ POZICE
                closed_quantity = current_position['quantity']
                entry_price = current_position['avg_price']
                
                trade_pnl = (executed_price - entry_price) * closed_quantity
                self.realized_pnl += trade_pnl
                self.equity += trade_pnl
                
                logger.warning(f"  CLOSED position of {closed_quantity:.4f} {symbol}. P&L for this trade: ${trade_pnl:.2f}")
                logger.warning(f"  New Realized P&L: ${self.realized_pnl:.2f}. New Equity: ${self.equity:.2f}")

            # Otevření nové pozice nebo překlopení
            new_quantity = -quantity if side == 'SELL' else quantity
            self.positions[symbol] = {'quantity': new_quantity, 'avg_price': executed_price}
            log_action = "FLIPPED to" if is_closing_trade else "OPENED"
            logger.info(f"  {log_action} new position: {side} {quantity} {symbol} at ${executed_price:.2f}")

            # Zápis obchodu do databáze
            trade_record = Trade(
                strategy_id=order['strategy_id'],
                exchange='binance_simulated',
                symbol=order['symbol'],
                exchange_order_id=str(uuid.uuid4()),
                side=order['side'],
                amount=order['quantity'],
                price=executed_price,
                fee=fee,
                fee_currency='USDT',
                executed_at=datetime.datetime.now(datetime.timezone.utc)
            )
            
            try:
                self.db_session.add(trade_record)
                self.db_session.commit()
                
                # Zápis do historie portfolia, POUZE pokud došlo k realizaci zisku/ztráty
                if trade_pnl != 0:
                    self._log_portfolio_state(trade_record.executed_at, trade_id=trade_record.id)
                
                logger.warning(f"  SUCCESSFULLY LOGGED TRADE to DB. ID: {trade_record.exchange_order_id}")
            except Exception as e:
                logger.error(f"  Failed to log trade to DB: {e}", exc_info=True)
                self.db_session.rollback()
            
            logger.warning("="*50)

if __name__ == "__main__":
    try:
        simulator = ExecutionSimulator()
        simulator.run()
    except Exception as e:
        logger.error(f"A critical error occurred in the Execution Simulator: {e}", exc_info=True)