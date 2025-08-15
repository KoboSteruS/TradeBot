"""Модели ответов от OpenAI."""
from typing import Optional
from pydantic import Field, validator
from .base import BaseModel
from .trading import TradingStatus


class OpenAIResponse(BaseModel):
    """Базовый ответ от OpenAI."""
    status: TradingStatus = Field(..., description="Статус торгового решения")
    response: str = Field(..., description="Объяснение решения")


class BuyDecision(OpenAIResponse):
    """Решение о покупке."""
    buy_amount: float = Field(..., gt=0, description="Сумма для покупки в USDT")
    take_profit_percent: float = Field(..., gt=0, le=100, description="Take Profit в процентах")
    stop_loss_percent: float = Field(..., gt=0, le=100, description="Stop Loss в процентах")
    
    @validator('status')
    def validate_status(cls, v):
        """Проверяет, что статус соответствует типу решения."""
        if v != TradingStatus.BUY:
            raise ValueError(f"Статус должен быть '{TradingStatus.BUY}' для решения о покупке")
        return v


class SellDecision(OpenAIResponse):
    """Решение о продаже."""
    sell_amount: float = Field(..., gt=0, description="Количество BTC для продажи")
    
    @validator('status')
    def validate_status(cls, v):
        """Проверяет, что статус соответствует типу решения."""
        if v != TradingStatus.SELL:
            raise ValueError(f"Статус должен быть '{TradingStatus.SELL}' для решения о продаже")
        return v


class CancelDecision(OpenAIResponse):
    """Решение об отмене ордера."""
    order_id: str = Field(..., description="ID ордера для отмены")
    
    @validator('status')
    def validate_status(cls, v):
        """Проверяет, что статус соответствует типу решения."""
        if v != TradingStatus.CANCEL:
            raise ValueError(f"Статус должен быть '{TradingStatus.CANCEL}' для решения об отмене")
        return v


class PauseDecision(OpenAIResponse):
    """Решение о паузе."""
    
    @validator('status')
    def validate_status(cls, v):
        """Проверяет, что статус соответствует типу решения."""
        if v != TradingStatus.PAUSE:
            raise ValueError(f"Статус должен быть '{TradingStatus.PAUSE}' для решения о паузе")
        return v
