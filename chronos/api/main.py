from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, select, desc
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv
import plotly.graph_objects as go
import plotly.io as pio
from chronos.models.schema import Trade, Strategy, PortfolioHistory

load_dotenv()
DB_USER = os.getenv("POSTGRES_USER", "chronos_user")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "yoursecurepassword")
DB_NAME = os.getenv("POSTGRES_DB", "chronos_db")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

app = FastAPI(title="Chronos Dashboard")
templates = Jinja2Templates(directory="chronos/api/templates")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    db = SessionLocal()
    try:
        trades_query = select(Trade).order_by(desc(Trade.executed_at)).limit(20)
        recent_trades = db.execute(trades_query).scalars().all()

        strategies_query = select(Strategy)
        all_strategies = db.execute(strategies_query).scalars().all()

        history_query = select(PortfolioHistory).order_by(PortfolioHistory.timestamp)
        portfolio_history = db.execute(history_query).scalars().all()

        if portfolio_history:
            timestamps = [h.timestamp for h in portfolio_history]
            equities = [h.total_equity for h in portfolio_history]
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=timestamps, y=equities, mode='lines+markers', name='Equity'))
            fig.update_layout(
                title='Portfolio Equity Curve',
                xaxis_title='Time',
                yaxis_title='Equity (USD)',
                template='plotly_dark'
            )
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
            "graph_json": graph_json
        }
    )