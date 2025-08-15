"""Модели для торговых данных."""
from typing import List, Dict, Any, Optional
from enum import Enum
from pydantic import Field
from .base import BaseModel


class TradingStatus(str, Enum):
    """Статусы торговых решений."""
    PAUSE = "pause"
    BUY = "buy"
    SELL = "sell"
    CANCEL = "cancel"


class OrderType(str, Enum):
    """Типы ордеров."""
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"


class OrderStatus(str, Enum):
    """Статусы ордеров."""
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"
    PARTIALLY_FILLED = "partially_filled"


class OrderBookEntry(BaseModel):
    """Запись в стакане ордеров."""
    price: float = Field(..., description="Цена")
    amount: float = Field(..., description="Объем")
    count: int = Field(..., description="Количество ордеров")
    change: float = Field(default=0.0, description="Изменение")


class OrderBook(BaseModel):
    """Стакан ордеров."""
    asks: List[OrderBookEntry] = Field(..., description="Ордера на продажу")
    bids: List[OrderBookEntry] = Field(..., description="Ордера на покупку")
    timestamp: str = Field(..., description="Временная метка")


class CandleData(BaseModel):
    """Данные свечи."""
    timestamp: str = Field(..., description="Временная метка")
    open: float = Field(..., description="Цена открытия")
    high: float = Field(..., description="Максимальная цена")
    low: float = Field(..., description="Минимальная цена")
    close: float = Field(..., description="Цена закрытия")
    volume: float = Field(..., description="Объем торгов")
    volume_currency: float = Field(..., description="Объем в валюте")
    volume_currency_quote: float = Field(..., description="Объем в котируемой валюте")
    confirm: int = Field(..., description="Подтверждение")


class MarketIndicators(BaseModel):
    """Рыночные индикаторы."""
    current_price: float = Field(..., description="Текущая цена")
    volume_24h: float = Field(..., description="Объем за 24 часа")
    change_24h: float = Field(..., description="Изменение за 24 часа в %")
    high_24h: float = Field(..., description="Максимум за 24 часа")
    low_24h: float = Field(..., description="Минимум за 24 часа")


class UserBalance(BaseModel):
    """Баланс пользователя."""
    USDT: float = Field(..., description="Баланс USDT")
    BTC: float = Field(..., description="Баланс BTC")


class UserData(BaseModel):
    """Пользовательские данные."""
    active_orders: List[Dict[str, Any]] = Field(..., description="Активные ордера")
    balances: UserBalance = Field(..., description="Балансы")


class MarketData(BaseModel):
    """Полные рыночные данные."""
    inst_id: str = Field(..., description="Идентификатор инструмента")
    market_data: Dict[str, Any] = Field(..., description="Рыночные данные")
    user_data: UserData = Field(..., description="Пользовательские данные")
    indicators: MarketIndicators = Field(..., description="Индикаторы")
    timestamp: str = Field(..., description="Временная метка")
    message: str = Field(..., description="Сообщение")


class OrderData(BaseModel):
    """Данные ордера."""
    order_id: str = Field(..., description="ID ордера")
    symbol: str = Field(..., description="Торговая пара")
    side: str = Field(..., description="Сторона сделки (buy/sell)")
    amount: float = Field(..., description="Количество")
    price: Optional[float] = Field(None, description="Цена")
    order_type: OrderType = Field(..., description="Тип ордера")
    status: OrderStatus = Field(..., description="Статус ордера")
    take_profit: Optional[float] = Field(None, description="Take Profit")
    stop_loss: Optional[float] = Field(None, description="Stop Loss")


class TradingDecision(BaseModel):
    """Торговое решение."""
    status: TradingStatus = Field(..., description="Статус решения")
    response: str = Field(..., description="Объяснение решения")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Уверенность в решении (0-1)")
    risk_level: str = Field(default="medium", description="Уровень риска (low/medium/high)")
