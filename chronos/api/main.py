# chronos/api/main.py

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, select, desc
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv
import plotly.graph_objects as go
import plotly.io as pio
from chronos.models.schema import Trade, Strategy, PortfolioHistory # <-- Přidat PortfolioHistory
import json

# Importujeme naše databázové modely
from chronos.models.schema import Trade, Strategy

# Načtení proměnných prostředí
load_dotenv()
DB_USER = os.getenv("POSTGRES_USER", "chronos_user")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "yoursecurepassword")
DB_NAME = os.getenv("POSTGRES_DB", "chronos_db")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Vytvoření FastAPI aplikace
app = FastAPI(title="Chronos Dashboard")

# Nastavení šablon
templates = Jinja2Templates(directory="chronos/api/templates")

# Vytvoření připojení k databázi
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """
    Hlavní endpoint, který načte data a zobrazí je v HTML šabloně.
    """
    db = SessionLocal()
    try:
        # Načtení posledních 20 obchodů seřazených od nejnovějšího
        trades_query = select(Trade).order_by(desc(Trade.executed_at)).limit(20)
        recent_trades = db.execute(trades_query).scalars().all()

        # Načtení všech strategií
        strategies_query = select(Strategy)
        all_strategies = db.execute(strategies_query).scalars().all()

        # Načtení historického portfolia
        history_query = select(PortfolioHistory).order_by(PortfolioHistory.timestamp)
        portfolio_history = db.execute(history_query).scalars().all()

        # Vytvoření grafu pomocí Plotly
        if portfolio_history:
            timestamps = [h.timestamp for h in portfolio_history]
            equities = [h.total_equity for h in portfolio_history]
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=timestamps, y=equities, mode='lines+markers', name='Equity'))
            fig.update_layout(
                title='Portfolio Equity Curve',
                xaxis_title='Time',
                yaxis_title='Equity (USD)',
                template='plotly_dark' # Tmavé téma, aby ladilo se stránkou
            )
            # Převedeme graf na JSON, který může být vykreslen v HTML
            graph_json = pio.to_json(fig)
        else:
            graph_json = "{}" 

    finally:
        db.close()

    return templates.TemplateResponse(
        "index.html", 
        {
            "request": request,
            "trades": recent_trades,
            "strategies": all_strategies,
            # Nyní vždy posíláme validní JSON string
            "graph_json": graph_json
        }
    )