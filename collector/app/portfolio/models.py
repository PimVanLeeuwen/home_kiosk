"""Response models for the Portfolio page (the /api/portfolio summary is in app.models)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from ..models import Envelope


class ChartPoint(BaseModel):
    d: str  # ISO date
    v: float  # value in the base currency
    invested: float | None = None


class PortfolioCharts(Envelope):
    """Value over time per range: month, ytd, year, max."""

    ranges: dict[str, list[ChartPoint]]


class PricePoint(BaseModel):
    d: str
    price: float
    average: float | None = None  # your average purchase price on that day


class HoldingActivity(BaseModel):
    date: datetime
    type: str  # BUY, SELL, DIVIDEND, FEE, ...
    quantity: float
    unit_price: float
    fee: float
    currency: str
    value: float | None = None  # in the base currency


class HoldingDetail(BaseModel):
    symbol: str
    data_source: str
    name: str
    isin: str | None = None
    currency: str | None = None
    quantity: float
    average_price: float
    price: float
    price_min: float | None = None
    price_max: float | None = None
    value: float
    invested: float | None = None
    gain_abs: float | None = None
    gain_pct: float | None = None
    dividends: float | None = None
    fees: float | None = None
    first_activity: str | None = None
    history: list[PricePoint] = []
    activities: list[HoldingActivity] = []


class IndexQuote(BaseModel):
    symbol: str
    label: str
    currency: str | None = None
    price: float
    day_pct: float
    at: datetime | None = None  # the time of the last price


class Indices(Envelope):
    indices: list[IndexQuote]
