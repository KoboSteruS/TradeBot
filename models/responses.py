"""Модели ответов от OpenAI."""
from typing import Literal, Optional
from pydantic import Field
from .base import Base


class TradingStatus:
    PAUSE = "pause"
    BUY = "buy"
    SELL = "sell"
    CANCEL = "cancel"


class PauseDecision(Base):
    status: Literal[TradingStatus.PAUSE] = Field(..., description="Статус решения: pause")
    response: str = Field(..., description="Краткое объяснение решения")


class BuyDecision(Base):
    status: Literal[TradingStatus.BUY] = Field(..., description="Статус решения: buy")
    response: str = Field(..., description="Краткое объяснение решения")
    buy_amount: float = Field(..., gt=0, description="Сумма покупки в USDT")
    take_profit_percent: float = Field(..., gt=0, description="Процент тейк-профита")
    stop_loss_percent: float = Field(..., gt=0, description="Процент стоп-лосса")


class SellDecision(Base):
    status: Literal[TradingStatus.SELL] = Field(..., description="Статус решения: sell")
    response: str = Field(..., description="Краткое объяснение решения")
    sell_amount: float = Field(..., gt=0, description="Количество BTC для продажи")


class CancelDecision(Base):
    status: Literal[TradingStatus.CANCEL] = Field(..., description="Статус решения: cancel")
    response: str = Field(..., description="Краткое объяснение решения")
    order_id: str = Field(..., description="ID ордера для отмены")


class OrdersCancelDecision(Base):
    status: Literal[TradingStatus.CANCEL] = Field(..., description="Статус решения: cancel")
    response: str = Field(..., description="Краткое объяснение решения")
    order_id: str = Field(..., description="ID ордера для отмены")


class OrdersSellDecision(Base):
    status: Literal[TradingStatus.SELL] = Field(..., description="Статус решения: sell")
    response: str = Field(..., description="Краткое объяснение решения")
    sell_amount: Optional[float] = Field(None, gt=0, description="Количество BTC для продажи (если None - продать все)")


# Union типы для всех возможных решений
TradingDecision = PauseDecision | BuyDecision | SellDecision | CancelDecision
OrdersDecision = PauseDecision | OrdersCancelDecision | OrdersSellDecision
