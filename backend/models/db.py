"""Persistência local SQLite via SQLAlchemy — arquitetura.md §3 (SQLite v1).

Tabela `candles`: cache persistente de OHLCV por (symbol, timeframe, timestamp).
Usado pelo BinanceProvider para evitar bater na API externa repetidamente
e servir dado stale em caso de falha de rede.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    String,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


class CandleRow(Base):
    __tablename__ = "candles"
    __table_args__ = (UniqueConstraint("symbol", "timeframe", "timestamp", name="uq_candle"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(16), nullable=False, index=True)
    timeframe = Column(String(16), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, nullable=False, default=0.0)


def default_db_path() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    # backend/models/db.py -> backend/data/orus_quant.db
    backend_dir = os.path.dirname(here)
    return os.path.join(backend_dir, "data", "orus_quant.db")


def get_engine(db_path: str | None = None):
    path = db_path or os.getenv("ORUS_DB_PATH", default_db_path())
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return create_engine(f"sqlite:///{path}", future=True)


def init_db(db_path: str | None = None) -> None:
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)


def save_candles(symbol: str, timeframe: str, candles: list, db_path: str | None = None) -> int:
    """Persiste lista de schemas Candle. Retorna nº de linhas inseridas/atualizadas."""
    from models.schemas import Candle

    items: list[Candle] = list(candles)
    if not items:
        return 0
    init_db(db_path)
    engine = get_engine(db_path)
    Session = sessionmaker(bind=engine, future=True)
    count = 0
    with Session() as session:
        for c in items:
            ts = c.timestamp
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            row = (
                session.query(CandleRow)
                .filter_by(symbol=symbol.upper(), timeframe=timeframe, timestamp=ts)
                .one_or_none()
            )
            if row is None:
                row = CandleRow(
                    symbol=symbol.upper(),
                    timeframe=timeframe,
                    timestamp=ts,
                    open=c.open,
                    high=c.high,
                    low=c.low,
                    close=c.close,
                    volume=c.volume,
                )
                session.add(row)
            else:
                row.open, row.high, row.low, row.close, row.volume = (
                    c.open,
                    c.high,
                    c.low,
                    c.close,
                    c.volume,
                )
            count += 1
        session.commit()
    return count


def load_candles(
    symbol: str, timeframe: str, limit: int = 500, db_path: str | None = None
) -> list:
    """Carrega últimos `limit` candles do SQLite, ordenados por timestamp."""
    from models.schemas import Candle

    init_db(db_path)
    engine = get_engine(db_path)
    Session = sessionmaker(bind=engine, future=True)
    with Session() as session:
        rows = (
            session.query(CandleRow)
            .filter_by(symbol=symbol.upper(), timeframe=timeframe)
            .order_by(CandleRow.timestamp.desc())
            .limit(max(0, limit))
            .all()
        )
    rows = list(reversed(rows))
    return [
        Candle(
            timestamp=r.timestamp if r.timestamp.tzinfo else r.timestamp.replace(tzinfo=timezone.utc),
            open=r.open,
            high=r.high,
            low=r.low,
            close=r.close,
            volume=r.volume,
        )
        for r in rows
    ]
