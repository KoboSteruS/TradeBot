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
    price: str = Field(..., description="Цена")
    size: str = Field(..., description="Размер")
    side: str = Field(..., description="Сторона (bid/ask)")


class Candle(BaseModel):
    """Свеча OHLCV."""
    timestamp: str = Field(..., description="Временная метка")
    open: str = Field(..., description="Цена открытия")
    high: str = Field(..., description="Максимальная цена")
    low: str = Field(..., description="Минимальная цена")
    close: str = Field(..., description="Цена закрытия")
    volume: str = Field(..., description="Объем")


class Balance(BaseModel):
    """Баланс валюты."""
    USDT: float = Field(default=0.0, description="Баланс USDT")
    BTC: float = Field(default=0.0, description="Баланс BTC")


class ActiveOrder(BaseModel):
    """Активный ордер."""
    instId: str = Field(..., description="Идентификатор инструмента")
    ordId: str = Field(..., description="ID ордера")
    px: str = Field(..., description="Цена")
    sz: str = Field(..., description="Размер")
    side: str = Field(..., description="Сторона (buy/sell)")
    ordType: str = Field(..., description="Тип ордера")
    state: str = Field(..., description="Состояние ордера")
    cTime: str = Field(..., description="Время создания")
    uTime: str = Field(..., description="Время обновления")


class Indicators(BaseModel):
    """Рыночные индикаторы."""
    current_price: str = Field(default="0", description="Текущая цена")
    volume_24h: str = Field(default="0", description="Объем за 24 часа")
    change_24h: str = Field(default="0", description="Изменение за 24 часа")
    high_24h: str = Field(default="0", description="Максимум за 24 часа")
    low_24h: str = Field(default="0", description="Минимум за 24 часа")


class MarketData(BaseModel):
    """Полные рыночные данные."""
    success: bool = Field(..., description="Успешность запроса")
    inst_id: str = Field(..., description="Идентификатор инструмента (например, BTC-USDT)")
    market_data: Dict[str, Any] = Field(..., description="Рыночные данные (стакан, свечи)")
    user_data: Dict[str, Any] = Field(..., description="Пользовательские данные (балансы, активные ордера)")
    indicators: Dict[str, Any] = Field(..., description="Текущие индикаторы рынка")
    timestamp: str = Field(..., description="Временная метка данных")
    message: Optional[str] = Field(None, description="Сообщение от API")


class OrdersResponse(BaseModel):
    """Ответ с активными ордерами."""
    success: bool = Field(..., description="Успешность запроса")
    message: str = Field(..., description="Сообщение")
    orders: List[ActiveOrder] = Field(default=[], description="Список активных ордеров")


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
