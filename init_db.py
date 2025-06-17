# init_db.py

import os
from sqlalchemy import create_engine, text
from chronos.models.schema import Base
from dotenv import load_dotenv

# Načtení proměnných z .env souboru (doporučený postup pro citlivé údaje)
load_dotenv()

# Načtení připojovacích údajů k databázi z proměnných prostředí
# Tyto proměnné jsou nastaveny v docker-compose.yml
DB_USER = os.getenv("POSTGRES_USER", "chronos_user")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "yoursecurepassword")
DB_NAME = os.getenv("POSTGRES_DB", "chronos_db")
DB_HOST = os.getenv("DB_HOST", "localhost") # Použij 'db' pokud běžíš v Dockeru, 'localhost' pro lokální spuštění
DB_PORT = os.getenv("DB_PORT", "5432")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

def initialize_database():
    """
    Připojí se k databázi, vytvoří všechny tabulky a nastaví hypertable.
    """
    print(f"Connecting to database at {DB_HOST}:{DB_PORT}...")
    try:
        engine = create_engine(DATABASE_URL)
        connection = engine.connect()
        print("Connection successful.")
    except Exception as e:
        print(f"Error connecting to the database: {e}")
        return

    print("Creating tables...")
    # Vytvoří všechny tabulky, které dědí z Base (pokud neexistují)
    Base.metadata.create_all(engine)
    print("Tables created (if they didn't exist).")

    # SQL příkaz pro vytvoření hypertable v TimescaleDB
    hypertable_sql = "SELECT create_hypertable('market_data_candles', 'time', if_not_exists => TRUE);"

    print("Creating hypertable for 'market_data_candles'...")
    try:
        with engine.connect() as connection:
            # Musíme použít text() pro raw SQL dotazy v SQLAlchemy 2.0+
            connection.execute(text(hypertable_sql))
            # Potvrzení transakce
            connection.commit()
        print("Hypertable 'market_data_candles' is set up.")
    except Exception as e:
        # Chyba může nastat, pokud hypertable již existuje, což je v pořádku díky `if_not_exists`
        if "already a hypertable" in str(e):
             print("Hypertable 'market_data_candles' already exists.")
        else:
            print(f"An error occurred while creating hypertable: {e}")

    print("Database initialization complete.")

if __name__ == "__main__":
    initialize_database()