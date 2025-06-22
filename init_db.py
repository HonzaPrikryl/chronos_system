import os
from sqlalchemy import create_engine, text
from chronos.models.schema import Base
from dotenv import load_dotenv

load_dotenv()

DB_USER = os.getenv("POSTGRES_USER", "chronos_user")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "yoursecurepassword")
DB_NAME = os.getenv("POSTGRES_DB", "chronos_db")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

def initialize_database():
    print(f"Connecting to database at {DB_HOST}:{DB_PORT}...")
    try:
        engine = create_engine(DATABASE_URL)
        connection = engine.connect()
        print("Connection successful.")
    except Exception as e:
        print(f"Error connecting to the database: {e}")
        return

    print("Creating tables...")
    Base.metadata.create_all(engine)
    print("Tables created (if they didn't exist).")

    hypertable_sql = "SELECT create_hypertable('market_data_candles', 'time', if_not_exists => TRUE);"

    print("Creating hypertable for 'market_data_candles'...")
    try:
        with engine.connect() as connection:
            connection.execute(text(hypertable_sql))
            connection.commit()
        print("Hypertable 'market_data_candles' is set up.")
    except Exception as e:
        if "already a hypertable" in str(e):
             print("Hypertable 'market_data_candles' already exists.")
        else:
            print(f"An error occurred while creating hypertable: {e}")

    print("Database initialization complete.")

if __name__ == "__main__":
    initialize_database()