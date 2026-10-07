"""Endpoints de ativos — spec.md §3."""

from fastapi import APIRouter, HTTPException, Query

from data.provider import get_provider
from models.schemas import Candle, PriceSnapshot
from strategy.config import ASSETS

router = APIRouter(prefix="/assets", tags=["assets"])


@router.get("", response_model=list[str])
def list_assets() -> list[str]:
    return ASSETS


@router.get("/{symbol}/price", response_model=PriceSnapshot)
def get_price(symbol: str) -> PriceSnapshot:
    try:
        return get_provider().get_current_price(symbol)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{symbol}/ohlc", response_model=list[Candle])
def get_ohlc(
    symbol: str,
    interval: str = Query(default="1d"),
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[Candle]:
    try:
        return get_provider().get_ohlc(symbol, interval, limit)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
